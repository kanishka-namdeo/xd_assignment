---
name: e2e-testing
description: End-to-end testing guide for the Social Support Application system. Covers preflight checks, infrastructure startup, test data generation, Emirates ID creation, the 7-phase applicant flow (auth through enablement), API and UI testing patterns, document uploads, interrupt/resume, session recovery, error handling, and expected outcomes per profile. Use when testing the application end-to-end, debugging phase transitions, verifying document processing, or validating the full applicant pipeline.
---

# E2E Testing Guide

## Preflight Checklist

Run these in order before any test. Fix failures before proceeding.

```
1. Docker services       → docker compose ps              (all 9 containers healthy)
2. Ollama                → curl http://localhost:11434     (200 OK)
3. Ollama model pulled   → ollama list | findstr qwen      (qwen3.5:14b present)
4. LLM health            → GET http://localhost:8000/api/v1/health/llm  (status: healthy)
5. DB migrations         → alembic current                 (matches latest migration)
6. Fresh account ready   → data\fresh_accounts\            (or run generate_fresh_account.py)
7. .env configured       → verify LLM_PROVIDER, DB creds, Langfuse keys
```

### Start Infrastructure

```powershell
docker compose up -d
# Wait ~30s, then verify
docker compose ps
```

Expected containers: `xd_postgres`, `xd_neo4j`, `xd_qdrant`, `xd_langfuse_web`, `xd_langfuse_worker`, `xd_langfuse_postgres`, `xd_langfuse_clickhouse`, `xd_langfuse_redis`, `xd_langfuse_minio`.

### Start Application

```powershell
# Terminal 1: FastAPI backend (port 8000)
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000

# Terminal 2: Streamlit frontend (port 8501)
.\.venv\Scripts\streamlit.exe run ui/streamlit_app.py --server.port 8501
```

### Generate Test Data

```powershell
.\.venv\Scripts\python.exe scripts/generate_fresh_account.py
# For a specific seed:
.\.venv\Scripts\python.exe scripts/generate_fresh_account.py --seed 42
```

Produces a fresh random applicant in `data/fresh_accounts/applicant_{seed}/`:

Each profile contains: `profile.json`, `emirates_id_front.png`, `emirates_id_back.png`, `bank_statement.pdf`, `credit_report.pdf`, `application_form.png`, `resume.docx`, `assets_liabilities.xlsx`, and `consistency_report.json`.

The script prints the Emirates ID and key fields in a copy-paste-friendly block at the end.

**Note**: `scripts/generate_test_data.py` is still available for generating the 3 fixed scenario profiles (approved, manual_review, soft_decline) in `data/test_applicants/`. Use `generate_fresh_account.py` for fresh, random test accounts.

## Emirates ID

**Format**: `784-YYYY-NNNNNNN-C` (15 digits). Must pass Luhn checksum.

**Generate a valid random ID**:

```python
import sys; sys.path.insert(0, ".")
from src.utils.emirates_id import luhn_check_digit
import random

year = random.randint(1970, 2000)
seq = random.randint(1000000, 9999999)
digits = f"784{year}{seq}"
check = luhn_check_digit(digits)
emirates_id = f"{digits}{check}"
```

**Use a profile's ID**: Read `data/test_applicants/{profile_name}/profile.json` → `applicant.identity_number`.

## API Quick Reference

Base URL: `http://localhost:8000/api/v1`

### Core Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/login` | Auth with `{"emirates_id": "..."}` → returns `applicant_id`, `application_id`, `is_new_applicant`, `current_phase`, `state_snapshot` |
| POST | `/applications/{id}/chat` | Send text + files (multipart) → returns `message`, `phase`, `uploaded_documents`, `decision`, `decision_card`, `interrupt` |
| POST | `/applications/{id}/chat/stream` | SSE streaming variant of chat (JSON body: `text`, `file_paths`) |
| GET | `/applications/{id}` | Application status, decision, eligibility score |
| GET | `/applications/{id}/documents` | List uploaded documents |
| GET | `/eligibility/{id}` | `eligibility_score` and `factors` |
| POST | `/eligibility/{id}/compute` | Trigger eligibility computation → returns score, factors, features_used |
| GET | `/eligibility/{id}/explanation` | Human-readable explanation + score |
| GET | `/health/llm` | LLM connectivity: provider, model, latency, tokens |

### Application CRUD

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/applications` | Create application |
| PATCH | `/applications/{id}/status` | Update status/phase |
| POST | `/applications/{id}/documents` | Upload document (multipart) |
| DELETE | `/applications/{id}/documents/{doc_id}` | Delete document |

### Error Responses

| Status | Condition | Response |
|---|---|---|
| 400 | Invalid Emirates ID checksum | `{"detail": "Invalid Emirates ID format or checksum"}` |
| 404 | Application not found | `{"detail": "Application not found"}` |
| 404 | Eligibility not computed | `{"detail": "Eligibility not computed for this application"}` |
| 500 | Chat processing error | `{"detail": "Chat processing error: {error_message}"}` |

## Graph Topology

Understanding phase transitions is critical for testing.

```
START → route_by_phase → [any of the 7 nodes]

authentication → intake                          (fixed edge)
intake         → "intake" | "document_collection" (conditional: loops until all fields captured)
document_collection → "document_collection" | "processing" (conditional: loops until all docs uploaded)
processing     → review                          (fixed edge)
review         → "document_collection" | "review" | "decision" (conditional: new docs → reprocess, loop, or advance)
decision       → enablement                      (fixed edge)
enablement     → END
```

All routing is driven by nodes setting `current_phase` in their return dict. The routing functions in `src/agents/orchestrator/routes.py` simply return `state["current_phase"]`.

## 7-Phase Flow

### Phase 0: Authentication

```python
import requests

resp = requests.post("http://localhost:8000/api/v1/auth/login",
                     json={"emirates_id": emirates_id})
data = resp.json()
application_id = data["application_id"]
# Response shape:
# {
#   "applicant_id": "uuid",
#   "application_id": "uuid",
#   "is_new_applicant": true/false,
#   "current_phase": "authentication" | "intake" | ...,
#   "state_snapshot": {...} | null   # full persisted state for returning applicants
# }
# 400 if Emirates ID fails Luhn checksum
```

**UI**: Enter Emirates ID on landing page → "Start Application" → redirected to `/application`. Max 3 attempts before lockout. Client-side Luhn validation before API call.

### Phase 1: Intake

Send applicant's personal information via chat:

```python
resp = requests.post(
    f"http://localhost:8000/api/v1/applications/{application_id}/chat",
    data={"text": "I'm Ahmed Hassan, born 1990-05-15. Emirati, divorced, 2 children. Employed at ADNOC, 15000 AED/month. Rent in Abu Dhabi. Need financial support."}
)
# phase transitions to "document_collection" when support_category is set
# interrupt set if info incomplete — bot asks follow-up questions
```

**Intake fields** (all captured before advancing to document_collection):
`full_name`, `date_of_birth`, `nationality`, `contact_phone`, `contact_email`, `address`, `marital_status`, `family_size`, `employment_status`, `employer_name`, `occupation`, `housing_status`, `support_category`

**Support category values**: `divorced`, `abandoned`, `unknown_parentage`, `health_disability`

### Phase 2: Document Collection

Upload documents via chat with files:

```python
from pathlib import Path

doc_dir = Path("data/test_applicants/divorced_employed_good_credit")
files = []
for fname in ["emirates_id_front.png", "emirates_id_back.png",
              "bank_statement.pdf", "credit_report.pdf", "application_form.png"]:
    fpath = doc_dir / fname
    mime = "image/png" if fname.endswith(".png") else "application/pdf"
    files.append(("files", (fname, open(fpath, "rb"), mime)))

resp = requests.post(
    f"http://localhost:8000/api/v1/applications/{application_id}/chat",
    data={"text": "Here are my documents"},
    files=files,
)
# resp.json()["uploaded_documents"] lists classified documents
# files saved to data/uploads/{application_id}/
```

**Chat response shape**:

```python
{
    "message": str,               # Last assistant message content
    "phase": str,                 # Current phase after processing
    "uploaded_documents": [       # List of classified documents
        {"doc_type": str, "file_path": str, "status": "uploaded"}
    ],
    "decision": str | None,       # "approved" | "manual_review" | "soft_decline" | None
    "decision_card": dict | None, # Formatted decision card (from decision_formatting_tool)
    "interrupt": {                # Present when graph paused at interrupt()
        "question": str,
        "phase": str,
        "missing_fields": list[str] | None,
        "missing_documents": list[str] | None,
        "discrepancies": list[dict] | None,
        "recommendations": list[str] | None
    } | None
}
```

**Required documents by category** (fallback: `DEFAULT_REQUIRED = ["emirates_id", "bank_statement", "credit_report", "application_form"]`):

| Category | Required |
|---|---|
| divorced | emirates_id, bank_statement, credit_report, application_form |
| abandoned | emirates_id, bank_statement, credit_report, application_form |
| unknown_parentage | emirates_id, bank_statement, application_form |
| health_disability | emirates_id, bank_statement, credit_report, application_form, resume |

**Document classification** rules (from `src/domain/document_classifier.py`):

| Document Type | Classification Rules |
|---|---|
| `emirates_id` | `.png/.jpg/.jpeg` (default for images without other hints) |
| `application_form` | Images/PDF with "application" or "form" in filename |
| `bank_statement` | Images/PDF with "bank" or "statement" in filename; PDF default |
| `credit_report` | Images/PDF with "credit", "aecb", or "report" in filename |
| `resume` | `.docx`; images with "resume" or "cv" in filename |
| `assets_liabilities` | `.xlsx` |
| `unknown` | Any unrecognized extension |

Name files with type hints for correct classification: `bank_statement.pdf`, `credit_report.pdf`, `application_form.png`, `emirates_id_front.png`.

**UI file types**: `["pdf", "png", "jpg", "jpeg", "xlsx", "docx"]`

### Phase 3: Processing (automated)

Transitions automatically after all documents collected. Runs OCR, PDF parsing, extraction, per-document validation, cross-document validation, confidence scoring.

```python
resp = requests.get(f"http://localhost:8000/api/v1/applications/{application_id}")
# current_phase advances to "review" or "decision" (skips review if no discrepancies)
```

### Phase 4: Review (if discrepancies found)

Bot asks clarifying questions via `interrupt`. Respond or upload corrected docs:

```python
# Answer a clarification question
resp = requests.post(
    f"http://localhost:8000/api/v1/applications/{application_id}/chat",
    data={"text": "The income difference is because of a quarterly bonus."}
)

# Re-upload corrected documents triggers re-processing
# (graph routes: review → "document_collection" → "processing" → "review")
```

**Interrupt/resume mechanism**:
- When graph hits `interrupt()`, response includes interrupt data with question/missing fields/documents
- Chat endpoint sets `_pending_interrupt = True` and persists state
- On next request, if `_pending_interrupt` is True, the user's text is passed as `graph_input["resume"]`
- Agent runner uses `Command(resume=payload, update=state_update)` to resume the graph

### Phase 5: Decision

Eligibility computed, decision rendered:

```python
# Compute eligibility
resp = requests.post(f"http://localhost:8000/api/v1/eligibility/{application_id}/compute")
score = resp.json()["eligibility_score"]

# Get explanation
resp = requests.get(f"http://localhost:8000/api/v1/eligibility/{application_id}/explanation")
explanation = resp.json()["explanation"]

# Get application decision
resp = requests.get(f"http://localhost:8000/api/v1/applications/{application_id}")
decision = resp.json()["decision"]  # "approved" | "soft_decline" | "manual_review"
```

**Decision logic** (from `src/services/decision_service.py`):

| Condition | Decision |
|---|---|
| `score >= 0.7` AND no critical issues | `approved` |
| `score >= 0.5` OR (unresolved validations AND no critical issues) | `manual_review` |
| `score < 0.5` OR critical issues exist | `soft_decline` |

**Critical issue** = validation with `status == "discrepancies_found"` AND `confidence_score < 0.5`.

**Fallback thresholds** (from decision node): `score >= 0.7` → approved, `>= 0.5` → manual_review, `< 0.5` → soft_decline. Eligibility gate failure with `score < 0.40` → soft_decline.

### Phase 6: Enablement

Personalized recommendations delivered via chat. Conversation continues until applicant satisfied.

## Session Recovery

```python
# 1. Auth, complete intake, upload some docs
# 2. "Close browser" — stop sending requests
# 3. Re-auth with same Emirates ID
resp = requests.post("http://localhost:8000/api/v1/auth/login",
                     json={"emirates_id": emirates_id})
data = resp.json()
assert data["is_new_applicant"] == False
assert data["application_id"] == application_id  # same application
assert data["state_snapshot"] is not None         # full state restored

# 4. state_snapshot contains: messages, current_phase, applicant_info,
#    uploaded_documents, extracted_data, and all other state fields
# 5. Continue from saved phase — next chat request resumes graph
```

**UI handling**: If `state_snapshot` exists and `is_new_applicant` is false, the landing page restores messages from snapshot, shows "Welcome back" banner with phase and document count.

## ApplicantState Fields

Reference for state inspection during testing:

```
messages, current_phase, applicant_id, application_id,
uploaded_files, eligibility_score, decision, decision_explanation,
uploaded_documents, discrepancies, extracted_data, validation_errors,
identity_number, support_category, extraction_confidence,
validation_results, eligibility_factors, gate_status, gate_errors,
retry_count, escalation_reason, applicant_info, extraction_results,
_next_action, _clarification_questions, enablement_recommendations,
new_documents_uploaded
```

## Quick Start Test Script

Complete runnable test for the happy path (divorced_employed_good_credit → approved):

```python
import requests
from pathlib import Path

BASE = "http://localhost:8000/api/v1"
# Use the path printed by generate_fresh_account.py, e.g.:
PROFILE = Path("data/fresh_accounts/applicant_7329")

# Phase 0: Auth
# The Emirates ID is printed by generate_fresh_account.py in the FRESH ACCOUNT READY block.
# Alternatively, read it from profile.json:
# profile_json = __import__("json").loads((PROFILE / "profile.json").read_text())
# eid = profile_json["identity_number"]
resp = requests.post(f"{BASE}/auth/login", json={"emirates_id": eid})
app_id = resp.json()["application_id"]
print(f"Auth OK: phase={resp.json()['current_phase']}")

# Phase 1: Intake
resp = requests.post(f"{BASE}/applications/{app_id}/chat",
    data={"text": "I'm the applicant, born 1985-03-20. Emirati, divorced, 2 children. "
                  "Employed at ADNOC as engineer, 15000 AED/month. Renting in Abu Dhabi. "
                  "Need financial support."})
print(f"Intake: phase={resp.json()['phase']}")

# Phase 2: Upload docs
files = []
for fname in ["emirates_id_front.png", "emirates_id_back.png",
              "bank_statement.pdf", "credit_report.pdf", "application_form.png"]:
    fpath = PROFILE / fname
    if fpath.exists():
        mime = "image/png" if fname.endswith(".png") else "application/pdf"
        files.append(("files", (fname, open(fpath, "rb"), mime)))

resp = requests.post(f"{BASE}/applications/{app_id}/chat",
    data={"text": "Here are my documents"}, files=files)
for f in files: f[1][1].close()
print(f"Upload: phase={resp.json()['phase']}, docs={[d['doc_type'] for d in resp.json().get('uploaded_documents', [])]}")

# Phase 3-5: Wait for processing → decision
import time
for _ in range(30):
    time.sleep(2)
    resp = requests.get(f"{BASE}/applications/{app_id}")
    app = resp.json()
    if app.get("decision"):
        print(f"Decision: {app['decision']}, score={app.get('eligibility_score')}")
        break
    if app["current_phase"] in ("review", "decision"):
        print(f"Phase: {app['current_phase']} (waiting for decision...)")
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Luhn fails on login | Generate ID with `luhn_check_digit()` |
| Docs not classified | Name files with type hints (`bank_statement.pdf`) |
| Docs classified as `unknown` | Check extension: `.xlsx` → assets_liabilities, `.docx` → resume |
| Phase stuck at processing | Check `GET /health/llm`, review logs |
| Phase stuck at intake | Ensure `support_category` is mentioned (divorced/abandoned/unknown_parentage/health_disability) |
| Decision mismatch | Verify score thresholds + critical issues in `decision_service` |
| Interrupt not resuming | Check `_pending_interrupt` state; next chat must include resume text |
| Session recovery fails | Run `alembic upgrade head`; verify `state_snapshot` in auth response |
| Docker services down | `docker compose up -d && docker compose ps` |
| Port in use (8000) | `$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess; Stop-Process -Id $pid -Force` |
| Port in use (8501) | `$pid = (Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue).OwningProcess; Stop-Process -Id $pid -Force` |
