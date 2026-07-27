#!/usr/bin/env python3
"""API client for the Social Support Application — backend-only interaction."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

BASE_URL = "http://127.0.0.1:8000/api/v1"
UPLOAD_DIR = Path("data/uploads")

logger = structlog.get_logger(__name__)


def output(command: str, success: bool, data: Any = None, error: str | None = None, latency_ms: float = 0.0) -> None:
    """Print structured JSON to stdout."""
    result = {
        "command": command,
        "success": success,
        "latency_ms": round(latency_ms, 2),
    }
    if data is not None:
        result["data"] = data
    if error is not None:
        result["error"] = error
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def log_verbose(message: str, **kwargs: Any) -> None:
    """Print human-readable progress to stderr."""
    parts = [message]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    print(" ".join(parts), file=sys.stderr)


async def login(client: httpx.AsyncClient, emirates_id: str, verbose: bool = False) -> dict:
    """POST /auth/login — returns application_id and phase."""
    start = time.perf_counter()
    if verbose:
        log_verbose("login", emirates_id=emirates_id)
    resp = await client.post(f"{BASE_URL}/auth/login", json={"emirates_id": emirates_id})
    latency = (time.perf_counter() - start) * 1000
    if resp.status_code != 200:
        if verbose:
            log_verbose("login_failed", status=resp.status_code, error=resp.text[:200])
        output("login", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
        return {}
    data = resp.json()
    if verbose:
        log_verbose("login_ok", application_id=data.get("application_id"), phase=data.get("current_phase"))
    output("login", True, data=data, latency_ms=latency)
    return data


async def status(client: httpx.AsyncClient, app_id: str, verbose: bool = False) -> dict:
    """GET /applications/{id} — returns current phase, decision, score."""
    start = time.perf_counter()
    if verbose:
        log_verbose("status", application_id=app_id)
    resp = await client.get(f"{BASE_URL}/applications/{app_id}")
    latency = (time.perf_counter() - start) * 1000
    if resp.status_code != 200:
        if verbose:
            log_verbose("status_failed", status=resp.status_code, error=resp.text[:200])
        output("status", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
        return {}
    data = resp.json()
    if verbose:
        log_verbose("status_ok", phase=data.get("current_phase"), decision=data.get("decision"))
    output("status", True, data=data, latency_ms=latency)
    return data


def generate_account(seed: int | None = None, output_dir: str | None = None, verbose: bool = False) -> dict:
    """Subprocess generate_fresh_account.py and parse output."""
    start = time.perf_counter()
    cmd = [sys.executable, "scripts/generate_fresh_account.py"]
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    if output_dir is not None:
        cmd.extend(["--output-dir", output_dir])

    if verbose:
        log_verbose("generate_account", cmd=" ".join(cmd))

    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    latency = (time.perf_counter() - start) * 1000

    if result.returncode != 0:
        if verbose:
            log_verbose("generate_account_failed", stderr=result.stderr[:200])
        output("generate-account", False, error=result.stderr[:200], latency_ms=latency)
        return {}

    # Parse "FRESH ACCOUNT READY" block from stdout
    emirates_id = None
    profile_path = None
    for line in result.stdout.splitlines():
        if "Emirates ID:" in line:
            emirates_id = line.split("Emirates ID:")[1].strip()
        if "Profile:" in line:
            profile_path = Path(line.split("Profile:")[1].strip())

    data = {"emirates_id": emirates_id, "profile_path": str(profile_path) if profile_path else None}
    if verbose:
        log_verbose("generate_account_ok", emirates_id=emirates_id, profile_path=profile_path)
    output("generate-account", True, data=data, latency_ms=latency)
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Social Support Application API client")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress to stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    p = sub.add_parser("login", help="Authenticate with Emirates ID")
    p.add_argument("--emirates-id", required=True, help="Emirates ID number")

    # status
    p = sub.add_parser("status", help="Get application status")
    p.add_argument("--app-id", required=True, help="Application UUID")

    # generate-account
    p = sub.add_parser("generate-account", help="Generate a fresh test account")
    p.add_argument("--seed", type=int, help="Random seed for reproducibility")
    p.add_argument("--output-dir", help="Output directory")

    return parser


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    verbose = args.verbose

    async with httpx.AsyncClient(timeout=120.0) as client:
        if args.command == "login":
            await login(client, args.emirates_id, verbose)
        elif args.command == "status":
            async with httpx.AsyncClient(timeout=30.0) as client:
                await status(client, args.app_id, verbose)
        elif args.command == "generate-account":
            generate_account(args.seed, args.output_dir, verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
