# API-Only Agent Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Cursor Agent Skill and companion CLI script that enables full application interaction via the FastAPI backend — covering auth, intake, document upload, processing, review, decision, and enablement.

**Architecture:** A single async Python script (`scripts/api_client.py`) with argparse subcommands, each mapping to an application phase. A 3-file skill package (SKILL.md, reference.md, examples.md) in `.cursor/skills/api-only-interaction/` teaches the agent when and how to invoke the script.

**Tech Stack:** Python 3.11.12, httpx (async HTTP), argparse, subprocess (for generate-account), pathlib, json.

## Global Constraints

- Script must use the project venv: `.\.venv\Scripts\python.exe`
- All output must be structured JSON to stdout; progress logs to stderr
- No Windows-style paths in skill files (use forward slashes)
- SKILL.md must be under 500 lines
- Skill description must be third-person, include WHAT and WHEN
- Follow existing script patterns from `scripts/e2e_test.py` and `tests/e2e_api_test.py`

---

### Task 1: Script Skeleton and Login Subcommand

**Files:**
- Create: `scripts/api_client.py`
- Test: Manual verification via backend

**Interfaces:**
- Consumes: None (first task)
- Produces: `scripts/api_client.py` with `login()` function, argparse setup, base URL constant

- [ ] **Step 1: Create script skeleton with argparse and base infrastructure**

```python
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


def output(command: str, success: bool, data: Any = None, error: str = None, latency_ms: float = 0.0) -> None:
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
```

- [ ] **Step 2: Add argparse setup with login subcommand**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Social Support Application API client")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress to stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    p = sub.add_parser("login", help="Authenticate with Emirates ID")
    p.add_argument("--emirates-id", required=True, help="Emirates ID number")
    return parser
```

- [ ] **Step 3: Add main() entry point**

```python
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
```

- [ ] **Step 4: Verify script runs**

```bash
.\.venv\Scripts\python.exe scripts/api_client.py --help
.\.venv\Scripts\python.exe scripts/api_client.py login --help
```

Expected: help text for both commands.

- [ ] **Step 5: Commit**

```bash
git add scripts/api_client.py
git commit -m "feat: add api_client.py skeleton with login subcommand"
```

---

### Task 2: Status and Generate-Account Subcommands

**Files:**
- Modify: `scripts/api_client.py`

**Interfaces:**
- Consumes: `output()`, `log_verbose()`, `BASE_URL`, `httpx.AsyncClient` from Task 1
- Produces: `status()` and `generate_account()` functions, argparse subcommands

- [ ] **Step 1: Add `status()` function**

```python
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
```

- [ ] **Step 2: Add `generate_account()` function**

```python
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
```

- [ ] **Step 3: Register subcommands in argparse**

```python
# In build_parser(), add to subparsers:

# status
p = sub.add_parser("status", help="Get application status")
p.add_argument("--app-id", required=True, help="Application UUID")

# generate-account
p = sub.add_parser("generate-account", help="Generate a fresh test account")
p.add_argument("--seed", type=int, help="Random seed for reproducibility")
p.add_argument("--output-dir", help="Output directory")
```

- [ ] **Step 4: Wire into main()**

```python
# In main(), add branches:
elif args.command == "status":
    async with httpx.AsyncClient(timeout=30.0) as client:
        await status(client, args.app_id, verbose)
elif args.command == "generate-account":
    generate_account(args.seed, args.output_dir, verbose)
```

- [ ] **Step 5: Verify**

```bash
.\.venv\Scripts\python.exe scripts/api_client.py --help
```

Expected: all 3 subcommands listed.

- [ ] **Step 6: Commit**

```bash
git add scripts/api_client.py
git commit -m "feat: add status and generate-account subcommands"
```

---

### Task 3: Intake Subcommand

**Files:**
- Modify: `scripts/api_client.py`

**Interfaces:**
- Consumes: `output()`, `log_verbose()`, `BASE_URL`, `httpx.AsyncClient`
- Produces: `intake()` function with interrupt loop

- [ ] **Step 1: Add `intake()` function**

```python
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
```

- [ ] **Step 2: Register in argparse**

```python
p = sub.add_parser("intake", help="Send personal details and advance to document collection")
p.add_argument("--app-id", required=True, help="Application UUID")
p.add_argument("--profile-dir", required=True, help="Path to profile directory")
p.add_argument("--max-loops", type=int, default=5, help="Max interrupt resolution attempts")
```

- [ ] **Step 3: Wire into main()**

```python
elif args.command == "intake":
    async with httpx.AsyncClient(timeout=120.0) as client:
        await intake(client, args.app_id, args.profile_dir, args.max_loops, verbose)
```

- [ ] **Step 4: Verify argparse**

```bash
.\.venv\Scripts\python.exe scripts/api_client.py intake --help
```

- [ ] **Step 5: Commit**

```bash
git add scripts/api_client.py
git commit -m "feat: add intake subcommand with interrupt loop"
```

---

### Task 4: Upload-Docs Subcommand

**Files:**
- Modify: `scripts/api_client.py`

**Interfaces:**
- Consumes: `output()`, `log_verbose()`, `BASE_URL`, `httpx.AsyncClient`
- Produces: `upload_docs()` function

- [ ] **Step 1: Add `upload_docs()` function**

```python
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

    resp = await client.post(
        f"{BASE_URL}/applications/{app_id}/chat",
        data={"text": "Here are my supporting documents."},
        files=files,
    )
    latency = (time.perf_counter() - start) * 1000

    # Close file handles
    for _, (_, _, f) in files:
        f.close()

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
```

- [ ] **Step 2: Register in argparse**

```python
p = sub.add_parser("upload-docs", help="Upload all documents from a profile directory")
p.add_argument("--app-id", required=True, help="Application UUID")
p.add_argument("--profile-dir", required=True, help="Path to profile directory")
```

- [ ] **Step 3: Wire into main()**

```python
elif args.command == "upload-docs":
    async with httpx.AsyncClient(timeout=120.0) as client:
        await upload_docs(client, args.app_id, args.profile_dir, verbose)
```

- [ ] **Step 4: Verify argparse**

```bash
.\.venv\Scripts\python.exe scripts/api_client.py upload-docs --help
```

- [ ] **Step 5: Commit**

```bash
git add scripts/api_client.py
git commit -m "feat: add upload-docs subcommand"
```

---

### Task 5: Process, Review, Decision, Enablement Subcommands

**Files:**
- Modify: `scripts/api_client.py`

**Interfaces:**
- Consumes: `output()`, `log_verbose()`, `BASE_URL`, `httpx.AsyncClient`
- Produces: `process()`, `review()`, `decision()`, `enablement()` functions

- [ ] **Step 1: Add `process()` function**

```python
async def process(client: httpx.AsyncClient, app_id: str, timeout_seconds: int = 90, verbose: bool = False) -> dict:
    """Trigger processing and poll until phase exits 'processing'."""
    # Trigger processing
    start = time.perf_counter()
    if verbose:
        log_verbose("process_trigger", app_id=app_id)

    resp = await client.post(
        f"{BASE_URL}/applications/{app_id}/chat",
        data={"text": "I have uploaded all required documents. Please proceed with processing."},
    )
    if resp.status_code != 200 and verbose:
        log_verbose("process_trigger_failed", status=resp.status_code)

    # Poll
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
```

- [ ] **Step 2: Add `review()` function**

```python
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
```

- [ ] **Step 3: Add `decision()` function**

```python
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
```

- [ ] **Step 4: Add `enablement()` function**

```python
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
```

- [ ] **Step 5: Register all 4 subcommands in argparse**

```python
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
```

- [ ] **Step 6: Wire into main()**

```python
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
```

- [ ] **Step 7: Verify argparse**

```bash
.\.venv\Scripts\python.exe scripts/api_client.py --help
```

Expected: all 8 subcommands listed.

- [ ] **Step 8: Commit**

```bash
git add scripts/api_client.py
git commit -m "feat: add process, review, decision, enablement subcommands"
```

---

### Task 6: Full-Flow and Eligibility Subcommands

**Files:**
- Modify: `scripts/api_client.py`

**Interfaces:**
- Consumes: all previous subcommand functions
- Produces: `full_flow()` orchestrator, `eligibility()` function

- [ ] **Step 1: Add `full_flow()` function**

```python
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
```

- [ ] **Step 2: Add `eligibility()` function**

```python
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
```

- [ ] **Step 3: Register in argparse**

```python
# full-flow
p = sub.add_parser("full-flow", help="Run complete 7-phase flow end-to-end")
p.add_argument("--emirates-id", required=True, help="Emirates ID number")
p.add_argument("--profile-dir", required=True, help="Path to profile directory")

# eligibility
p = sub.add_parser("eligibility", help="Compute and print eligibility score + explanation")
p.add_argument("--app-id", required=True, help="Application UUID")
```

- [ ] **Step 4: Wire into main()**

```python
elif args.command == "full-flow":
    async with httpx.AsyncClient(timeout=300.0) as client:
        await full_flow(client, args.emirates_id, args.profile_dir, verbose)
elif args.command == "eligibility":
    async with httpx.AsyncClient(timeout=60.0) as client:
        await eligibility(client, args.app_id, verbose)
```

- [ ] **Step 5: Verify all 11 subcommands**

```bash
.\.venv\Scripts\python.exe scripts/api_client.py --help
```

Expected: login, status, generate-account, intake, upload-docs, process, review, decision, enablement, full-flow, eligibility.

- [ ] **Step 6: Commit**

```bash
git add scripts/api_client.py
git commit -m "feat: add full-flow and eligibility subcommands"
```

---

### Task 7: SKILL.md

**Files:**
- Create: `.cursor/skills/api-only-interaction/SKILL.md`

**Interfaces:**
- Consumes: `scripts/api_client.py` (from Task 6)
- Produces: Cursor Agent Skill

- [ ] **Step 1: Create SKILL.md**

```markdown
---
name: api-only-interaction
description: Interact with the Social Support Application entirely through its FastAPI backend. Use when testing the application end-to-end without the Streamlit UI, running automated validation, generating test data, smoke testing before demos, or collecting decision/eligibility data. Covers all 7 phases: auth, intake, document collection, processing, review, decision, and enablement.
---

# API-Only Interaction

Interact with the Social Support Application entirely through the FastAPI backend — no Streamlit UI needed.

## Quick Start

```powershell
# Generate a fresh test account
.\.venv\Scripts\python.exe scripts/api_client.py generate-account --seed 42

# Run the full 7-phase flow
.\.venv\Scripts\python.exe scripts/api_client.py full-flow `
  --emirates-id 784-1990-1234567-1 `
  --profile-dir data/fresh_accounts/applicant_42
```

## Preflight Checklist

Run these before any interaction. Fix failures before proceeding.

```
1. Docker services       → docker compose ps              (all 9 containers healthy)
2. Ollama                → curl http://localhost:11434     (200 OK)
3. LLM health            → curl http://localhost:8000/api/v1/health/llm  (status: healthy)
4. DB migrations         → .\.venv\Scripts\python.exe -m alembic current  (matches latest)
5. Fresh account ready   → data\fresh_accounts\            (or run generate-account)
6. .env configured       → verify LLM_PROVIDER, DB creds
7. Backend running       → curl http://localhost:8000/api/v1/health/langgraph
```

Start backend:
```powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000
```

## Commands

| Command | Purpose |
|---|---|
| `generate-account [--seed N]` | Generate fresh test account |
| `login --emirates-id <eid>` | Authenticate, get application_id |
| `status --app-id <id>` | Get current phase, decision, score |
| `intake --app-id <id> --profile-dir <path>` | Send personal details, advance to document_collection |
| `upload-docs --app-id <id> --profile-dir <path>` | Upload all documents from profile |
| `process --app-id <id> [--timeout-seconds N]` | Trigger processing, poll until complete |
| `review --app-id <id>` | Answer clarifications, advance to decision |
| `decision --app-id <id>` | Poll until decision rendered |
| `enablement --app-id <id>` | Query enablement recommendations |
| `eligibility --app-id <id>` | Compute score + explanation |
| `full-flow --emirates-id <eid> --profile-dir <path>` | Run all 7 phases end-to-end |

## Output Format

All commands print JSON to stdout:
```json
{
  "command": "login",
  "success": true,
  "data": { "application_id": "...", "current_phase": "intake" },
  "latency_ms": 45.2
}
```

On failure:
```json
{
  "command": "login",
  "success": false,
  "error": "Invalid Emirates ID checksum",
  "latency_ms": 12.1
}
```

Use `--verbose` / `-v` for human-readable progress on stderr.

## 7-Phase Workflow

### Phase 0: Auth
```powershell
result = .\.venv\Scripts\python.exe scripts/api_client.py login --emirates-id <eid>
app_id = (ConvertFrom-Json $result).data.application_id
```

### Phase 1: Intake
```powershell
.\.venv\Scripts\python.exe scripts/api_client.py intake --app-id $app_id --profile-dir <path>
```
Loops through interrupts automatically. Requires `support_category` in profile.

### Phase 2: Document Upload
```powershell
.\.venv\Scripts\python.exe scripts/api_client.py upload-docs --app-id $app_id --profile-dir <path>
```
Uploads all files with supported extensions (`.png`, `.pdf`, `.docx`, `.xlsx`).

### Phase 3: Processing
```powershell
.\.venv\Scripts\python.exe scripts/api_client.py process --app-id $app_id
```
Polls every 3s until phase exits `processing`. Default timeout: 90s.

### Phase 4: Review (if discrepancies)
```powershell
.\.venv\Scripts\python.exe scripts/api_client.py review --app-id $app_id
```
Only needed if phase is `review` after processing. Loops through clarifications.

### Phase 5: Decision
```powershell
.\.venv\Scripts\python.exe scripts/api_client.py decision --app-id $app_id
```
Polls until `decision` is non-null. Returns: `approved`, `manual_review`, or `soft_decline`.

### Phase 6: Enablement
```powershell
.\.venv\Scripts\python.exe scripts/api_client.py enablement --app-id $app_id
```

## Decision Thresholds

| Condition | Decision |
|---|---|
| `score >= 0.7` AND no critical issues | `approved` |
| `score >= 0.5` OR unresolved validations | `manual_review` |
| `score < 0.5` OR critical issues | `soft_decline` |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Luhn fails on login | Use `generate-account` or `src/utils/emirates_id.py` for checksum |
| Docs classified as `unknown` | Name files with type hints: `bank_statement.pdf`, `credit_report.pdf` |
| Phase stuck at processing | `curl http://localhost:8000/api/v1/health/llm`; check Ollama |
| Phase stuck at intake | Ensure `support_category` in profile (divorced/abandoned/unknown_parentage/health_disability) |
| Interrupt not resuming | Script handles automatically — check `_pending_interrupt` in logs |
| Port 8000 in use | `$pid = (Get-NetTCPConnection -LocalPort 8000).OwningProcess; Stop-Process -Id $pid -Force` |
| Docker services down | `docker compose up -d && docker compose ps` |

## Session Recovery

Re-auth with the same Emirates ID to resume a prior session:
```powershell
result = .\.venv\Scripts\python.exe scripts/api_client.py login --emirates-id <eid>
# is_new_applicant will be false, same application_id returned
```

## Additional Resources

- For full API reference, see [reference.md](reference.md)
- For common scenarios and examples, see [examples.md](examples.md)
```

- [ ] **Step 2: Verify line count**

```bash
(Get-Content .cursor/skills/api-only-interaction/SKILL.md).Count
```

Expected: under 500 lines.

- [ ] **Step 3: Commit**

```bash
git add .cursor/skills/api-only-interaction/SKILL.md
git commit -m "feat: add API-only interaction skill (SKILL.md)"
```

---

### Task 8: Reference.md and Examples.md

**Files:**
- Create: `.cursor/skills/api-only-interaction/reference.md`
- Create: `.cursor/skills/api-only-interaction/examples.md`

**Interfaces:**
- Consumes: API endpoint details from source code
- Produces: reference and example files

- [ ] **Step 1: Create reference.md**

```markdown
# API Reference

Base URL: `http://localhost:8000/api/v1`

## Auth

### POST /auth/login
```json
// Request
{"emirates_id": "784-1990-1234567-1"}

// Response 200
{
  "applicant_id": "uuid",
  "application_id": "uuid",
  "is_new_applicant": true,
  "current_phase": "authentication",
  "state_snapshot": null
}
```

## Applications

### GET /applications/{id}
Returns: `id`, `applicant_id`, `status`, `current_phase`, `eligibility_score`, `validation_confidence`, `decision`, `decision_explanation`, `created_at`, `updated_at`

### POST /applications/{id}/chat
Multipart form-data: `text` (string), `files` (list of files)
Returns: `message`, `phase`, `uploaded_documents`, `decision`, `decision_card`, `interrupt`

### GET /applications/{id}/documents
Returns: list of documents with `document_type`, `processing_status`, `uploaded_at`

### POST /applications/{id}/documents
Multipart form-data: `file` (single file), `document_type` (optional string)

### DELETE /applications/{id}/documents/{doc_id}

## Eligibility

### GET /eligibility/{id}
Returns: `eligibility_score`, `factors`

### POST /eligibility/{id}/compute
Returns: `eligibility_score`, `factors`, `features_used`

### GET /eligibility/{id}/explanation
Returns: `explanation` (string), `eligibility_score`

## Health

### GET /health/langgraph
Returns: `status` (healthy/degraded/unhealthy), `components`, `timestamp`

### GET /health/llm
Returns: `status`, `provider`, `model`, `latency_ms`, `tokens`

## Error Responses

| Status | Condition | Response |
|---|---|---|
| 400 | Invalid Emirates ID | `{"detail": "Invalid Emirates ID format or checksum"}` |
| 404 | Application not found | `{"detail": "Application not found"}` |
| 404 | Eligibility not computed | `{"detail": "Eligibility not computed for this application"}` |
```

- [ ] **Step 2: Create examples.md**

```markdown
# Examples

## Happy Path (Approved Profile)

```powershell
# 1. Generate account
.\.venv\Scripts\python.exe scripts/api_client.py generate-account --seed 42

# 2. Run full flow
.\.venv\Scripts\python.exe scripts/api_client.py full-flow `
  --emirates-id 784-1990-1234567-1 `
  --profile-dir data/fresh_accounts/applicant_42 `
  --verbose
```

Expected: decision=`approved`, score > 0.7.

## Step-by-Step (Manual Control)

```powershell
# Auth
$auth = .\.venv\Scripts\python.exe scripts/api_client.py login --emirates-id <eid> | ConvertFrom-Json
$app_id = $auth.data.application_id

# Intake
.\.venv\Scripts\python.exe scripts/api_client.py intake --app-id $app_id --profile-dir <path>

# Upload
.\.venv\Scripts\python.exe scripts/api_client.py upload-docs --app-id $app_id --profile-dir <path>

# Process
.\.venv\Scripts\python.exe scripts/api_client.py process --app-id $app_id

# Review (if needed)
.\.venv\Scripts\python.exe scripts/api_client.py review --app-id $app_id

# Decision
.\.venv\Scripts\python.exe scripts/api_client.py decision --app-id $app_id

# Enablement
.\.venv\Scripts\python.exe scripts/api_client.py enablement --app-id $app_id
```

## Session Recovery

```powershell
# First session: auth + intake + partial docs
# ... then stop

# Later: re-auth with same Emirates ID
$auth = .\.venv\Scripts\python.exe scripts/api_client.py login --emirates-id <eid> | ConvertFrom-Json
# is_new_applicant = false, same application_id
# Continue from saved phase
```

## Eligibility Check

```powershell
.\.venv\Scripts\python.exe scripts/api_client.py eligibility --app-id <app_id>
```

## Status Check

```powershell
.\.venv\Scripts\python.exe scripts/api_client.py status --app-id <app_id>
```
```

- [ ] **Step 3: Commit**

```bash
git add .cursor/skills/api-only-interaction/reference.md .cursor/skills/api-only-interaction/examples.md
git commit -m "feat: add API reference and examples for api-only-interaction skill"
```

---

## Self-Review

**1. Spec coverage:** All 11 subcommands covered (generate-account, login, status, intake, upload-docs, process, review, decision, enablement, full-flow, eligibility). Skill files (SKILL.md, reference.md, examples.md) all created. Preflight, troubleshooting, output format all addressed.

**2. Placeholder scan:** No TBD/TODO. All code blocks complete. All function signatures consistent across tasks.

**3. Type consistency:** `output()` signature consistent (command, success, data, error, latency_ms). `log_verbose()` consistent. All async functions use `httpx.AsyncClient`. Return types consistent (dict).