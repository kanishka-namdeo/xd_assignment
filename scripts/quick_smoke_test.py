"""Quick API smoke test for the 7-phase flow."""
import random
import sys
import time
from pathlib import Path

import requests
import structlog

sys.path.insert(0, ".")
from src.infrastructure.observability.logging import configure_logging
from src.utils.emirates_id import luhn_check_digit

configure_logging()
logger = structlog.get_logger(__name__)

BASE = "http://localhost:8000/api/v1"

# Generate a fresh Emirates ID
random.seed(998877)
year = random.randint(1970, 2000)
seq = random.randint(1000000, 9999999)
digits = f"784{year}{seq}"
check = luhn_check_digit(digits)
eid_raw = f"{digits}{check}"
eid = f"{eid_raw[:3]}-{eid_raw[3:7]}-{eid_raw[7:14]}-{eid_raw[14]}"
logger.info("smoke_test_started")

# Phase 0: Auth
t0 = time.time()
resp = requests.post(f"{BASE}/auth/login", json={"emirates_id": eid})
duration_ms = (time.time() - t0) * 1000
logger.info("auth_attempted", status_code=resp.status_code, duration_ms=round(duration_ms, 1))
if resp.status_code != 200:
    logger.error("auth_failed", error=resp.text[:200])
    sys.exit(1)
data = resp.json()
app_id = data["application_id"]
phase = data["current_phase"]
logger.info("auth_complete", phase=phase, application_id=str(app_id))

# Phase 1: Intake
t0 = time.time()
resp = requests.post(
    f"{BASE}/applications/{app_id}/chat",
    data={
        "text": "I am applying for financial support. I am divorced, have 2 children, employed, monthly salary 15000 AED, renting in Abu Dhabi."
    },
)
duration_ms = (time.time() - t0) * 1000
logger.info("intake_completed", status_code=resp.status_code, duration_ms=round(duration_ms, 1))
if resp.status_code == 200:
    r = resp.json()
    msg = r.get("message", "")
    logger.info("intake_response_received", phase=r.get("phase"))
else:
    logger.error("intake_failed", error=resp.text[:500])
    sys.exit(1)

# Phase 2: Upload docs
profile_dir = Path("data/test_applicants/divorced_employed_good_credit")
files = []
for fname in ["emirates_id_front.png", "emirates_id_back.png", "bank_statement.pdf", "credit_report.pdf", "application_form.png"]:
    fpath = profile_dir / fname
    if fpath.exists():
        mime = "image/png" if fname.endswith(".png") else "application/pdf"
        files.append(("files", (fname, open(fpath, "rb"), mime)))

logger.info("uploading_documents", document_count=len(files))
t0 = time.time()
resp = requests.post(
    f"{BASE}/applications/{app_id}/chat",
    data={"text": "Here are my documents"},
    files=files,
    timeout=120,
)
duration_ms = (time.time() - t0) * 1000
for _, (_, fh, _) in files:
    fh.close()
logger.info("upload_completed", status_code=resp.status_code, duration_ms=round(duration_ms, 1))
if resp.status_code == 200:
    r = resp.json()
    docs = r.get("uploaded_documents", [])
    logger.info("upload_response_received", phase=r.get("phase"), document_types=[d.get("doc_type") for d in docs])
else:
    logger.error("upload_failed", error=resp.text[:500])
    sys.exit(1)

# Phase 3-5: Poll for decision
logger.info("polling_for_decision", application_id=str(app_id))
decision_reached = None
for i in range(60):
    time.sleep(2)
    t0 = time.time()
    resp = requests.get(f"{BASE}/applications/{app_id}")
    duration_ms = (time.time() - t0) * 1000
    if resp.status_code != 200:
        logger.warning("poll_error", poll_number=i + 1, status_code=resp.status_code, duration_ms=round(duration_ms, 1))
        continue
    app = resp.json()
    cur_phase = app.get("current_phase")
    decision = app.get("decision")
    score = app.get("eligibility_score")
    logger.info("poll_result", poll_number=i + 1, phase=cur_phase, decision=decision, score=score, duration_ms=round(duration_ms, 1))
    if decision:
        decision_reached = decision
        logger.info("decision_reached", decision=decision, score=score)
        break
    if cur_phase == "enablement":
        logger.info("enablement_phase_reached")
        break

logger.info("smoke_test_completed", decision=decision_reached)
