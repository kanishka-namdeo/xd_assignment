"""API smoke test using the freshly generated account (seed 2026) with real LLM calls."""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, ".")

BASE = "http://localhost:8000/api/v1"
PROFILE_DIR = Path("data/fresh_accounts/applicant_2026")


def log_event(event: str, **kwargs):
    """Structured logging for smoke test events."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    kv_str = " ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"[{timestamp}] {event} {kv_str}", flush=True)


def log_error(event: str, error: Exception, **kwargs):
    """Structured error logging."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    kv_str = " ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"[{timestamp}] ERROR {event} error={error} {kv_str}", flush=True)


def verify_server_health():
    """Verify server is running and healthy before starting tests."""
    log_event("server_health_check", status="starting")
    try:
        resp = requests.get(f"{BASE}/health/langgraph", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            log_event("server_health_check", status="healthy", components=data.get("components", {}))
            return True
        else:
            log_error("server_health_check", Exception(f"HTTP {resp.status_code}"), response=resp.text[:200])
            return False
    except requests.exceptions.ConnectionError as e:
        log_error("server_health_check", e, message="Server not reachable")
        return False
    except Exception as e:
        log_error("server_health_check", e)
        return False


def main():
    start_time = time.time()
    log_event("smoke_test_start")

    # Pre-flight: Verify server health
    if not verify_server_health():
        log_event("smoke_test_abort", reason="Server health check failed")
        sys.exit(1)

    # Load profile
    try:
        profile = json.loads((PROFILE_DIR / "profile.json").read_text())
        eid = profile["identity_number"]
        log_event(
            "profile_loaded",
            name=profile.get("full_name_en", "unknown"),
            emirates_id=eid,
            category=profile.get("support_category"),
            employment=profile.get("employment_status"),
        )
    except Exception as e:
        log_error("profile_load_failed", e, path=str(PROFILE_DIR))
        sys.exit(1)

    # Phase 0: Auth - use a fresh identity number
    import random
    random.seed(int(time.time()))
    from src.utils.emirates_id import generate_emirates_id_number

    fresh_eid = generate_emirates_id_number()
    log_event("phase_0_auth_start", emirates_id=fresh_eid)

    try:
        resp = requests.post(f"{BASE}/auth/login", json={"emirates_id": fresh_eid}, timeout=30)
        if resp.status_code != 200:
            log_error("phase_0_auth_failed", Exception(f"HTTP {resp.status_code}"), response=resp.text[:500])
            sys.exit(1)

        data = resp.json()
        app_id = data["application_id"]
        phase = data["current_phase"]
        log_event("phase_0_auth_complete", app_id=app_id, phase=phase)
    except Exception as e:
        log_error("phase_0_auth_exception", e)
        sys.exit(1)

    # Phase 1: Intake - provide personal info
    intake_text = (
        f"My name is {profile['full_name_en']}. "
        f"I am {profile['support_category']}. "
        f"I have 2 children. "
        f"I am {profile['employment_status']}. "
        f"My monthly salary is {profile['monthly_salary']} AED. "
        f"I am renting in Abu Dhabi. "
        f"My phone is 0501234567 and email is test@test.com. "
        f"My family size is 4."
    )
    log_event("phase_1_intake_start", message_length=len(intake_text))

    try:
        resp = requests.post(
            f"{BASE}/applications/{app_id}/chat",
            data={"text": intake_text},
            timeout=120,
        )
        if resp.status_code != 200:
            log_error("phase_1_intake_failed", Exception(f"HTTP {resp.status_code}"), response=resp.text[:500])
            sys.exit(1)

        r = resp.json()
        log_event(
            "phase_1_intake_complete",
            phase=r.get("phase"),
            message_preview=r.get("message", "")[:100],
        )
    except Exception as e:
        log_error("phase_1_intake_exception", e)
        sys.exit(1)

    # Phase 2: Upload documents
    log_event("phase_2_upload_start")
    doc_files = []
    for fname in PROFILE_DIR.iterdir():
        if fname.suffix.lower() in (".png", ".pdf", ".xlsx", ".docx"):
            suffix = fname.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".pdf": "application/pdf",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }
            mime = mime_map.get(suffix)
            if mime:
                doc_files.append(("files", (fname.name, open(fname, "rb"), mime)))

    doc_names = [f[1][0] for f in doc_files]
    log_event("phase_2_upload_files_prepared", count=len(doc_files), files=doc_names)

    try:
        log_event("phase_2_upload_sending", timeout=600)
        resp = requests.post(
            f"{BASE}/applications/{app_id}/chat",
            data={"text": "Here are all my required documents."},
            files=doc_files,
            timeout=600,
        )

        for _, (_, fh, _) in doc_files:
            fh.close()

        if resp.status_code != 200:
            log_error("phase_2_upload_failed", Exception(f"HTTP {resp.status_code}"), response=resp.text[:500])
            sys.exit(1)

        r = resp.json()
        docs = r.get("uploaded_documents", [])
        log_event(
            "phase_2_upload_complete",
            phase=r.get("phase"),
            doc_count=len(docs),
            doc_types=[d.get("doc_type") for d in docs],
        )
    except requests.exceptions.Timeout:
        log_event("phase_2_upload_timeout", timeout=600)
        sys.exit(1)
    except Exception as e:
        log_error("phase_2_upload_exception", e)
        sys.exit(1)

    # Phase 3-6: Poll for completion
    log_event("phase_3_6_polling_start")
    max_polls = 90
    poll_interval = 5

    for i in range(max_polls):
        time.sleep(poll_interval)
        try:
            resp = requests.get(f"{BASE}/applications/{app_id}", timeout=10)
            if resp.status_code != 200:
                log_event("poll_error", iteration=i + 1, status=resp.status_code)
                continue

            app = resp.json()
            cur_phase = app.get("current_phase")
            decision = app.get("decision")
            score = app.get("eligibility_score")

            log_event(
                "poll_status",
                iteration=i + 1,
                phase=cur_phase,
                decision=decision,
                score=score,
            )

            if decision:
                log_event("decision_reached", decision=decision, score=score)
                break
            if cur_phase == "enablement":
                log_event("enablement_reached")
                break
        except Exception as e:
            log_error("poll_exception", e, iteration=i + 1)

    # Check document status endpoint
    log_event("document_status_check_start")
    try:
        resp = requests.get(f"{BASE}/documents/status?application_id={app_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("documents", [])
            log_event("document_status_check_complete", doc_count=len(docs))
            for doc in docs:
                log_event(
                    "document_status",
                    doc_type=doc.get("document_type"),
                    status=doc.get("status"),
                    confidence=doc.get("confidence"),
                )
        else:
            log_error("document_status_check_failed", Exception(f"HTTP {resp.status_code}"))
    except Exception as e:
        log_error("document_status_check_exception", e)

    elapsed = time.time() - start_time
    log_event("smoke_test_complete", elapsed_seconds=round(elapsed, 2))


if __name__ == "__main__":
    main()
