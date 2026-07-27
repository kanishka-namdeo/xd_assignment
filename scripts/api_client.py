#!/usr/bin/env python3
"""API client for the Social Support Application — backend-only interaction."""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
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


async def intake(client: httpx.AsyncClient, app_id: str, profile_dir: str, max_loops: int = 5, verbose: bool = False) -> dict:
    """Send personal details, loop through interrupts until document_collection phase."""
    profile_path = Path(profile_dir) / "profile.json"
    if not profile_path.exists():
        output("intake", False, error=f"Profile not found: {profile_path}")
        return {}

    import json
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    applicant = profile["applicant"]

    message = (
        f"My name is {applicant['full_name_en']}, "
        f"DOB {applicant['date_of_birth']}, "
        f"nationality {applicant['nationality']}, "
        f"phone {applicant['contact_phone']}, "
        f"email {applicant['contact_email']}, "
        f"marital status {applicant['marital_status']}, "
        f"family size {applicant['family_size']}, "
        f"employment {applicant['employment_status']}, "
        f"employer {applicant['employer_name']}, "
        f"occupation {applicant['occupation']}, "
        f"housing {applicant['housing_status']}, "
        f"support category {applicant['support_category']}"
    )

    for attempt in range(max_loops):
        start = time.perf_counter()
        if verbose:
            log_verbose("intake_attempt", attempt=attempt + 1, app_id=app_id)

        resp = await client.post(
            f"{BASE_URL}/applications/{app_id}/chat",
            data={"text": message},
        )
        latency = (time.perf_counter() - start) * 1000

        if resp.status_code != 200:
            if verbose:
                log_verbose("intake_failed", status=resp.status_code, error=resp.text[:200])
            output("intake", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
            return {}

        data = resp.json()
        phase = data.get("phase") or data.get("current_phase")
        interrupt = data.get("interrupt")

        if verbose:
            log_verbose("intake_response", phase=phase, has_interrupt=interrupt is not None)

        if phase == "document_collection":
            output("intake", True, data=data, latency_ms=latency)
            return data

        if interrupt:
            # Build clarifying response
            discrepancies = interrupt.get("discrepancies", [])
            questions = interrupt.get("questions", []) or interrupt.get("missing_fields", [])
            parts = []
            for d in discrepancies:
                parts.append(f"Regarding {d.get('field', 'the discrepancy')}: the information in my documents is correct.")
            for q in questions:
                parts.append(f"Regarding {q}: provided in my application.")
            message = " ".join(parts) if parts else "All information provided is accurate and complete."
            continue

        # No interrupt, not at document_collection — send a nudge
        message = "I confirm all details are accurate. Please proceed."

    output("intake", False, error=f"Did not reach document_collection after {max_loops} attempts", latency_ms=latency)
    return {}


async def upload_docs(client: httpx.AsyncClient, app_id: str, profile_dir: str, verbose: bool = False) -> dict:
    """Upload all documents from a profile directory via multipart form-data."""
    profile_path = Path(profile_dir)
    if not profile_path.exists():
        output("upload-docs", False, error=f"Profile directory not found: {profile_dir}")
        return {}

    # Discover document files
    doc_extensions = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".xlsx"}
    files = []
    for fpath in sorted(profile_path.iterdir()):
        if fpath.suffix.lower() in doc_extensions:
            mime = _guess_mime(fpath)
            files.append(("files", (fpath.name, open(fpath, "rb"), mime)))
            if verbose:
                log_verbose("upload_doc_queued", filename=fpath.name, mime=mime)

    if not files:
        output("upload-docs", False, error="No document files found in profile directory")
        return {}

    start = time.perf_counter()
    if verbose:
        log_verbose("upload_docs", app_id=app_id, file_count=len(files))

    try:
        resp = await client.post(
            f"{BASE_URL}/applications/{app_id}/chat",
            data={"text": "Here are my supporting documents."},
            files=files,
        )
        latency = (time.perf_counter() - start) * 1000

        if resp.status_code != 200:
            if verbose:
                log_verbose("upload_docs_failed", status=resp.status_code, error=resp.text[:200])
            output("upload-docs", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
            return {}

        data = resp.json()
        if verbose:
            log_verbose("upload_docs_ok", phase=data.get("phase"), docs=len(data.get("uploaded_documents", [])))
        output("upload-docs", True, data=data, latency_ms=latency)
        return data
    finally:
        for _, (_, _, f) in files:
            f.close()


async def process(client: httpx.AsyncClient, app_id: str, timeout_seconds: int = 90, verbose: bool = False) -> dict:
    """Trigger processing and poll until phase exits 'processing'."""
    start = time.perf_counter()
    if verbose:
        log_verbose("process_trigger", app_id=app_id)

    resp = await client.post(
        f"{BASE_URL}/applications/{app_id}/chat",
        data={"text": "I have uploaded all required documents. Please proceed with processing."},
    )
    if resp.status_code != 200 and verbose:
        log_verbose("process_trigger_failed", status=resp.status_code)

    poll_interval = 3
    elapsed = 0
    while elapsed < timeout_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        status_resp = await client.get(f"{BASE_URL}/applications/{app_id}")
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            phase = status_data.get("current_phase", "unknown")
            if verbose:
                log_verbose("process_poll", phase=phase, elapsed_s=elapsed)

            if phase != "processing":
                latency = (time.perf_counter() - start) * 1000
                if phase in ("review", "decision", "enablement"):
                    output("process", True, data=status_data, latency_ms=latency)
                else:
                    output("process", False, error=f"Unexpected phase: {phase}", latency_ms=latency)
                return status_data

    latency = (time.perf_counter() - start) * 1000
    output("process", False, error=f"Timeout after {timeout_seconds}s — still in processing phase", latency_ms=latency)
    return {}


async def review(client: httpx.AsyncClient, app_id: str, max_loops: int = 5, verbose: bool = False) -> dict:
    """Answer clarification questions and loop until decision phase."""
    for attempt in range(max_loops):
        start = time.perf_counter()
        resp = await client.post(
            f"{BASE_URL}/applications/{app_id}/chat",
            data={"text": "All discrepancies are resolved. Please proceed with the decision."},
        )
        latency = (time.perf_counter() - start) * 1000

        if resp.status_code != 200:
            output("review", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
            return {}

        data = resp.json()
        phase = data.get("phase") or data.get("current_phase")

        if verbose:
            log_verbose("review_attempt", attempt=attempt + 1, phase=phase)

        if phase == "decision":
            output("review", True, data=data, latency_ms=latency)
            return data

    output("review", False, error=f"Did not reach decision after {max_loops} attempts")
    return {}


async def decision(client: httpx.AsyncClient, app_id: str, timeout_seconds: int = 60, verbose: bool = False) -> dict:
    """Poll until decision is rendered."""
    poll_interval = 3
    elapsed = 0
    start = time.perf_counter()

    while elapsed < timeout_seconds:
        resp = await client.get(f"{BASE_URL}/applications/{app_id}")
        if resp.status_code == 200:
            data = resp.json()
            decision = data.get("decision")
            phase = data.get("current_phase")
            latency = (time.perf_counter() - start) * 1000

            if verbose:
                log_verbose("decision_poll", phase=phase, decision=decision, elapsed_s=elapsed)

            if phase == "decision" and decision:
                output("decision", True, data=data, latency_ms=latency)
                return data
            elif phase in ("review", "processing"):
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue
            else:
                output("decision", False, error=f"Unexpected phase: {phase}", latency_ms=latency)
                return {}

    output("decision", False, error=f"Timeout after {timeout_seconds}s — no decision reached")
    return {}


async def enablement(client: httpx.AsyncClient, app_id: str, verbose: bool = False) -> dict:
    """Query enablement recommendations."""
    start = time.perf_counter()
    resp = await client.post(
        f"{BASE_URL}/applications/{app_id}/chat",
        data={"text": "What support am I eligible for?"},
    )
    latency = (time.perf_counter() - start) * 1000

    if resp.status_code != 200:
        output("enablement", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
        return {}

    data = resp.json()
    if verbose:
        log_verbose("enablement_ok", phase=data.get("phase"), has_recommendations=bool(data.get("enablement_recommendations")))
    output("enablement", True, data=data, latency_ms=latency)
    return data


async def full_flow(client: httpx.AsyncClient, emirates_id: str, profile_dir: str, verbose: bool = False) -> dict:
    """Orchestrate the complete 7-phase flow."""
    summary = {
        "emirates_id": emirates_id,
        "profile_dir": profile_dir,
        "steps": [],
        "decision": None,
        "eligibility_score": None,
    }
    app_id = None

    # Phase 0: Auth
    auth_data = await login(client, emirates_id, verbose)
    summary["steps"].append({"phase": "auth", "success": bool(auth_data.get("application_id"))})
    if not auth_data.get("application_id"):
        output("full-flow", False, error="Auth failed", data=summary)
        return summary
    app_id = auth_data["application_id"]
    summary["application_id"] = app_id

    # Phase 1: Intake
    intake_data = await intake(client, app_id, profile_dir, verbose=verbose)
    summary["steps"].append({"phase": "intake", "success": bool(intake_data)})
    if not intake_data:
        output("full-flow", False, error="Intake failed", data=summary)
        return summary

    # Phase 2: Upload docs
    upload_data = await upload_docs(client, app_id, profile_dir, verbose=verbose)
    summary["steps"].append({"phase": "upload_docs", "success": bool(upload_data)})
    if not upload_data:
        output("full-flow", False, error="Upload failed", data=summary)
        return summary

    # Phase 3: Processing
    process_data = await process(client, app_id, verbose=verbose)
    summary["steps"].append({"phase": "processing", "success": bool(process_data)})
    if not process_data:
        output("full-flow", False, error="Processing failed", data=summary)
        return summary

    # Phase 4: Review (if applicable)
    current_phase = process_data.get("current_phase") or process_data.get("phase")
    if current_phase == "review":
        review_data = await review(client, app_id, verbose=verbose)
        summary["steps"].append({"phase": "review", "success": bool(review_data)})
        if not review_data:
            output("full-flow", False, error="Review failed", data=summary)
            return summary

    # Phase 5: Decision
    decision_data = await decision(client, app_id, verbose=verbose)
    summary["steps"].append({"phase": "decision", "success": bool(decision_data)})
    if decision_data:
        summary["decision"] = decision_data.get("decision")
        summary["eligibility_score"] = decision_data.get("eligibility_score")

    # Phase 6: Enablement
    enablement_data = await enablement(client, app_id, verbose=verbose)
    summary["steps"].append({"phase": "enablement", "success": bool(enablement_data)})

    output("full-flow", True, data=summary)
    return summary


async def eligibility(client: httpx.AsyncClient, app_id: str, verbose: bool = False) -> dict:
    """Compute eligibility score and get explanation."""
    # Compute
    start = time.perf_counter()
    compute_resp = await client.post(f"{BASE_URL}/eligibility/{app_id}/compute")
    compute_latency = (time.perf_counter() - start) * 1000

    if compute_resp.status_code != 200:
        output("eligibility", False, error=f"Compute HTTP {compute_resp.status_code}: {compute_resp.text[:200]}", latency_ms=compute_latency)
        return {}

    compute_data = compute_resp.json()

    # Explanation
    explain_resp = await client.get(f"{BASE_URL}/eligibility/{app_id}/explanation")
    explain_latency = (time.perf_counter() - start) * 1000

    explanation = ""
    if explain_resp.status_code == 200:
        explanation = explain_resp.json().get("explanation", "")

    data = {
        "eligibility_score": compute_data.get("eligibility_score"),
        "factors": compute_data.get("factors"),
        "features_used": compute_data.get("features_used"),
        "explanation": explanation,
    }
    if verbose:
        log_verbose("eligibility_ok", score=data["eligibility_score"])
    output("eligibility", True, data=data, latency_ms=explain_latency)
    return data


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, "application/octet-stream")


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

    # intake
    p = sub.add_parser("intake", help="Send personal details and advance to document collection")
    p.add_argument("--app-id", required=True, help="Application UUID")
    p.add_argument("--profile-dir", required=True, help="Path to profile directory")
    p.add_argument("--max-loops", type=int, default=5, help="Max interrupt resolution attempts")

    # upload-docs
    p = sub.add_parser("upload-docs", help="Upload all documents from a profile directory")
    p.add_argument("--app-id", required=True, help="Application UUID")
    p.add_argument("--profile-dir", required=True, help="Path to profile directory")

    # process
    p = sub.add_parser("process", help="Trigger processing and poll until complete")
    p.add_argument("--app-id", required=True, help="Application UUID")
    p.add_argument("--timeout-seconds", type=int, default=90, help="Max wait time")

    # review
    p = sub.add_parser("review", help="Answer clarifications and advance to decision")
    p.add_argument("--app-id", required=True, help="Application UUID")
    p.add_argument("--max-loops", type=int, default=5)

    # decision
    p = sub.add_parser("decision", help="Poll until decision is rendered")
    p.add_argument("--app-id", required=True, help="Application UUID")
    p.add_argument("--timeout-seconds", type=int, default=60)

    # enablement
    p = sub.add_parser("enablement", help="Query enablement recommendations")
    p.add_argument("--app-id", required=True, help="Application UUID")

    # full-flow
    p = sub.add_parser("full-flow", help="Run complete 7-phase flow end-to-end")
    p.add_argument("--emirates-id", required=True, help="Emirates ID number")
    p.add_argument("--profile-dir", required=True, help="Path to profile directory")

    # eligibility
    p = sub.add_parser("eligibility", help="Compute and print eligibility score + explanation")
    p.add_argument("--app-id", required=True, help="Application UUID")

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
        elif args.command == "intake":
            async with httpx.AsyncClient(timeout=120.0) as client:
                await intake(client, args.app_id, args.profile_dir, args.max_loops, verbose)
        elif args.command == "upload-docs":
            async with httpx.AsyncClient(timeout=120.0) as client:
                await upload_docs(client, args.app_id, args.profile_dir, verbose)
        elif args.command == "process":
            async with httpx.AsyncClient(timeout=120.0) as client:
                await process(client, args.app_id, args.timeout_seconds, verbose)
        elif args.command == "review":
            async with httpx.AsyncClient(timeout=120.0) as client:
                await review(client, args.app_id, args.max_loops, verbose)
        elif args.command == "decision":
            async with httpx.AsyncClient(timeout=120.0) as client:
                await decision(client, args.app_id, args.timeout_seconds, verbose)
        elif args.command == "enablement":
            async with httpx.AsyncClient(timeout=120.0) as client:
                await enablement(client, args.app_id, verbose)
        elif args.command == "full-flow":
            async with httpx.AsyncClient(timeout=300.0) as client:
                await full_flow(client, args.emirates_id, args.profile_dir, verbose)
        elif args.command == "eligibility":
            async with httpx.AsyncClient(timeout=60.0) as client:
                await eligibility(client, args.app_id, verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
