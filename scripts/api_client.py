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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Social Support Application API client")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress to stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    p = sub.add_parser("login", help="Authenticate with Emirates ID")
    p.add_argument("--emirates-id", required=True, help="Emirates ID number")
    return parser


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    verbose = args.verbose

    async with httpx.AsyncClient(timeout=120.0) as client:
        if args.command == "login":
            await login(client, args.emirates_id, verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
