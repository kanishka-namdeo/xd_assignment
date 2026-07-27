# Demo Readiness Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 8 bugs and architecture violations to make the application demo-ready, then verify the full 7-phase flow end-to-end with real LLM calls and freshly generated synthetic documents.

**Architecture:** Surgical fixes across API, services, and agents layers. No new modules — all changes are localized to existing files. The four-layer architecture (API → Services → Agents → Infrastructure) is preserved.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Streamlit, PostgreSQL, Neo4j, Qdrant, Ollama/StreamLake LLM

## Global Constraints

- Python 3.11.12, use `.venv\Scripts\python.exe` for all commands
- PEP 585/604 type system: `list[str]`, `dict[str, Any]`, `X | None`
- Pydantic v2: `field_validator`, `model_validator`, `ConfigDict`
- structlog for all logging: `structlog.get_logger(__name__)`
- Four-layer architecture: API → Services → Agents → Infrastructure (no upward imports)
- All verification uses real LLM calls (no mocks) and real generated documents

---

### Task 1: Fix `_UUID()` → `UUID()` in extraction_pipeline.py

**Files:**
- Modify: `src/services/extraction_pipeline.py:181,198,240,242`

**Interfaces:**
- Consumes: `UUID` from `uuid` module (already imported at line 8)
- Produces: Working `persist_results()` function that no longer crashes with `NameError`

- [ ] **Step 1: Verify the bug exists**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from src.services.extraction_pipeline import persist_results; print('import ok')"
```
Expected: Import succeeds (the bug is at runtime, not import time)

- [ ] **Step 2: Replace `_UUID` with `UUID` on all 4 lines**

In `src/services/extraction_pipeline.py`, replace all occurrences of `_UUID(` with `UUID(`:

Line 181:
```python
# Before:
_UUID(er["document_id"]) if isinstance(er["document_id"], str) else er["document_id"],
# After:
UUID(er["document_id"]) if isinstance(er["document_id"], str) else er["document_id"],
```

Line 198:
```python
# Before:
applicant_id=_UUID(applicant_id) if applicant_id else uuid4(),
# After:
applicant_id=UUID(applicant_id) if applicant_id else uuid4(),
```

Line 240:
```python
# Before:
applicant_id=_UUID(applicant_id) if applicant_id else uuid4(),
# After:
applicant_id=UUID(applicant_id) if applicant_id else uuid4(),
```

Line 242:
```python
# Before:
id=_UUID(str(er["document_id"])),
# After:
id=UUID(str(er["document_id"])),
```

- [ ] **Step 3: Verify no remaining `_UUID` references**

Run:
```powershell
.\.venv\Scripts\python.exe -c "import ast; tree = ast.parse(open('src/services/extraction_pipeline.py').read()); print('no _UUID found' if '_UUID' not in open('src/services/extraction_pipeline.py').read() else 'STILL HAS _UUID')"
```
Expected: `no _UUID found`

- [ ] **Step 4: Commit**

```bash
git add src/services/extraction_pipeline.py
git commit -m "fix: replace undefined _UUID() with UUID() in extraction_pipeline persist_results"
```

---

### Task 2: Implement Document Status Endpoint

**Files:**
- Modify: `src/api/v1/documents.py`

**Interfaces:**
- Consumes: `ApplicationRepository`, `DocumentRepository` from infrastructure layer
- Produces: `GET /api/v1/documents/status?application_id=<id>` returns real document data

- [ ] **Step 1: Read current stub to understand structure**

Read `src/api/v1/documents.py` — it's a 15-line stub returning `{"status": "ok"}`.

- [ ] **Step 2: Replace stub with real implementation**

Replace the entire contents of `src/api/v1/documents.py` with:

```python
"""Document upload and status endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import AsyncDB
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.db.repositories.document_repo import DocumentRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/status")
async def document_status(
    application_id: str,
    db: AsyncDB,
) -> dict:
    """Return document upload status for an application."""
    logger.info("request_received", application_id=application_id)

    application_repo = ApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    document_repo = DocumentRepository(db)
    documents = await document_repo.get_by_applicant(application.applicant_id)

    return {
        "application_id": application_id,
        "documents": [
            {
                "document_type": doc.document_type,
                "status": doc.processing_status,
                "confidence": doc.overall_confidence,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in documents
        ],
    }
```

- [ ] **Step 3: Verify the endpoint responds**

Start the FastAPI server (if not already running):
```powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000
```

Test the endpoint (will return 404 for non-existent application, which is correct):
```powershell
.\.venv\Scripts\python.exe -c "import requests; r = requests.get('http://localhost:8000/api/v1/documents/status?application_id=00000000-0000-0000-0000-000000000000'); print(r.status_code, r.json())"
```
Expected: `404 {'detail': 'Application not found'}`

- [ ] **Step 4: Commit**

```bash
git add src/api/v1/documents.py
git commit -m "feat: implement real document status endpoint replacing stub"
```

---

### Task 3: Fix `support_category` State Propagation

**Files:**
- Modify: `src/agents/orchestrator/phases/intake.py:156-160`

**Interfaces:**
- Consumes: `applicant_info` dict with `support_category` key
- Produces: Top-level `support_category` state field set when intake completes

- [ ] **Step 1: Read the intake node completion block**

Read `src/agents/orchestrator/phases/intake.py` lines 140-162. The completion block (when `support_category` is truthy) returns a result dict that sets `applicant_info` but NOT the top-level `support_category` field.

- [ ] **Step 2: Add `support_category` to the result dict**

In `src/agents/orchestrator/phases/intake.py`, find the result dict around line 156:

```python
# Before:
result = {
    "messages": [{"role": "assistant", "content": response}],
    "current_phase": "document_collection",
    "applicant_info": applicant_info,
}
```

Replace with:
```python
# After:
result = {
    "messages": [{"role": "assistant", "content": response}],
    "current_phase": "document_collection",
    "applicant_info": applicant_info,
    "support_category": applicant_info.get("support_category"),
}
```

- [ ] **Step 3: Verify the change**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from src.agents.orchestrator.phases.intake import intake_node; print('import ok')"
```
Expected: `import ok`

- [ ] **Step 4: Commit**

```bash
git add src/agents/orchestrator/phases/intake.py
git commit -m "fix: propagate support_category to top-level state in intake node"
```

---

### Task 4: Set `new_documents_uploaded` Flag

**Files:**
- Modify: `src/agents/orchestrator/phases/document_collection.py`

**Interfaces:**
- Consumes: Document classification results
- Produces: `new_documents_uploaded: True` in state when new docs are classified

- [ ] **Step 1: Read the document_collection node**

Read `src/agents/orchestrator/phases/document_collection.py` to find where the result dict is returned after documents are classified.

- [ ] **Step 2: Add `new_documents_uploaded: True` to result dicts**

Find all result dicts returned by the document_collection node when new documents are successfully classified. Add `"new_documents_uploaded": True` to each.

For the main path where documents are classified and the phase advances:
```python
# Add to the result dict:
"new_documents_uploaded": True,
```

For paths where no new documents are found (e.g., user didn't upload anything new):
```python
# Add to the result dict:
"new_documents_uploaded": False,
```

- [ ] **Step 3: Verify the change**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from src.agents.orchestrator.phases.document_collection import document_collection_node; print('import ok')"
```
Expected: `import ok`

- [ ] **Step 4: Commit**

```bash
git add src/agents/orchestrator/phases/document_collection.py
git commit -m "fix: set new_documents_uploaded flag in document_collection node"
```

---

### Task 5: Move `decision_formatting_tool` to DecisionService

**Files:**
- Modify: `src/services/decision_service.py` — add `format_decision_card()` method
- Modify: `src/services/chat_service.py:11,150-158` — replace direct tool import

**Interfaces:**
- Consumes: `decision_formatting_tool` from `src.agents.decision.tools` (now wrapped in service)
- Produces: `DecisionService.format_decision_card()` method that chat_service calls

- [ ] **Step 1: Read current decision_service.py**

Read `src/services/decision_service.py` to understand its current structure.

- [ ] **Step 2: Add `format_decision_card()` method to DecisionService**

Add this method to the `DecisionService` class in `src/services/decision_service.py`:

```python
def format_decision_card(self, decision_data: dict) -> dict:
    """Format a decision for UI display.

    Wraps the agent-layer decision_formatting_tool to keep the service
    layer from importing agent tools directly.
    """
    from src.agents.decision.tools import decision_formatting_tool
    return decision_formatting_tool.invoke(decision_data)
```

- [ ] **Step 3: Update chat_service.py to use DecisionService instead of direct import**

In `src/services/chat_service.py`:

Remove the import at line 11:
```python
# DELETE this line:
from src.agents.decision.tools import decision_formatting_tool
```

Replace the formatting block (lines 148-160) with:
```python
# Before:
formatted_card = None
if result.get("decision"):
    try:
        formatted_card = decision_formatting_tool.invoke({
            "decision": result["decision"],
            "explanation": result.get("decision_explanation", ""),
            "enablement_recommendations": {"recommendations": result.get("enablement_recommendations", [])},
            "applicant_context": {
                "support_category": result.get("applicant_info", {}).get("support_category", "unknown"),
                "family_size": result.get("applicant_info", {}).get("family_size", 1),
            },
        })
    except Exception as e:
        logger.warning("decision_formatting_failed", application_id=application_id, error=str(e))
```

```python
# After:
formatted_card = None
if result.get("decision"):
    try:
        decision_svc = DecisionService(self.session)
        formatted_card = decision_svc.format_decision_card({
            "decision": result["decision"],
            "explanation": result.get("decision_explanation", ""),
            "enablement_recommendations": {"recommendations": result.get("enablement_recommendations", [])},
            "applicant_context": {
                "support_category": result.get("applicant_info", {}).get("support_category", "unknown"),
                "family_size": result.get("applicant_info", {}).get("family_size", 1),
            },
        })
    except Exception as e:
        logger.warning("decision_formatting_failed", application_id=application_id, error=str(e))
```

- [ ] **Step 4: Verify imports resolve**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from src.services.chat_service import ChatService; from src.services.decision_service import DecisionService; print('imports ok')"
```
Expected: `imports ok`

- [ ] **Step 5: Commit**

```bash
git add src/services/decision_service.py src/services/chat_service.py
git commit -m "refactor: move decision_formatting_tool call from chat_service into DecisionService"
```

---

### Task 6: Replace Hardcoded Model Names

**Files:**
- Modify: `src/api/v1/chat.py:42,118`

**Interfaces:**
- Consumes: `settings.STREAMLAKE_MODEL` from `src.config`
- Produces: Configurable model name via environment variable

- [ ] **Step 1: Read current chat.py to find hardcoded strings**

Read `src/api/v1/chat.py` lines 40-45 and 115-120.

- [ ] **Step 2: Add settings import and replace hardcoded strings**

Add import at the top of `src/api/v1/chat.py` (after existing imports):
```python
from src.config import settings
```

Replace line 42:
```python
# Before:
model="kat-coder-pro-v2.5",
# After:
model=settings.STREAMLAKE_MODEL,
```

Replace line 118:
```python
# Before:
async for delta in llm.stream_completion(messages, model="kat-coder-pro-v2.5"):
# After:
async for delta in llm.stream_completion(messages, model=settings.STREAMLAKE_MODEL):
```

- [ ] **Step 3: Verify no hardcoded model names remain**

Run:
```powershell
.\.venv\Scripts\python.exe -c "content = open('src/api/v1/chat.py').read(); print('clean' if 'kat-coder-pro-v2.5' not in content else 'STILL HARDCODED')"
```
Expected: `clean`

- [ ] **Step 4: Commit**

```bash
git add src/api/v1/chat.py
git commit -m "fix: replace hardcoded model name with settings.STREAMLAKE_MODEL"
```

---

### Task 7: Wire Chat Streaming to Orchestrator

**Files:**
- Modify: `src/api/v1/chat.py:104-161`

**Interfaces:**
- Consumes: `run_streaming()` from `src/services/agent_runner.py`
- Produces: SSE-formatted events for phase transitions, extraction, validation, decision

- [ ] **Step 1: Read agent_runner.py to understand run_streaming()**

Read `src/services/agent_runner.py` to understand the event types yielded by `run_streaming()`.

- [ ] **Step 2: Replace the raw LLM stream generator**

Replace the `_stream_generator()` function and `chat_stream()` endpoint in `src/api/v1/chat.py` (lines 104-161) with:

```python
async def _stream_generator(
    application_id: str,
    text: str,
    file_paths: list[str],
    chat_service: ChatService,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted events from the orchestrator graph."""
    import json
    from src.services.agent_runner import run_streaming

    graph_input = {
        "messages": [{"role": "user", "content": text}],
        "application_id": application_id,
        "uploaded_files": file_paths,
    }

    try:
        async for event in run_streaming(graph_input):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        logger.exception("stream_error", application_id=application_id, error=str(e))
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/applications/{application_id}/chat/stream")
async def chat_stream(
    application_id: str,
    fastapi_request: Request,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    text: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> StreamingResponse:
    """Stream orchestrator events as server-sent events."""
    logger.info("request_received", application_id=application_id, endpoint="chat_stream")

    # Save uploaded files to disk
    file_paths: list[str] = []
    if files:
        upload_dir = UPLOAD_DIR / application_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        for upload in files:
            if upload.filename is None:
                continue
            dest = upload_dir / upload.filename
            content = await upload.read()
            dest.write_bytes(content)
            file_paths.append(str(dest))

    return StreamingResponse(
        _stream_generator(
            application_id=application_id,
            text=text,
            file_paths=file_paths,
            chat_service=chat_service,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

- [ ] **Step 3: Verify imports resolve**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from src.api.v1.chat import router; print('import ok')"
```
Expected: `import ok`

- [ ] **Step 4: Commit**

```bash
git add src/api/v1/chat.py
git commit -m "feat: wire chat streaming endpoint to orchestrator graph via run_streaming()"
```

---

### Task 8: Clean Up Unused Imports

**Files:**
- Modify: `src/services/extraction_service.py`
- Modify: `src/services/validation_service.py`
- Modify: `src/services/eligibility_service.py`

**Interfaces:**
- Consumes: Nothing new
- Produces: Cleaner imports, no functional change

- [ ] **Step 1: Remove unused imports from extraction_service.py**

In `src/services/extraction_service.py`, remove:
- `from src.domain.parsers import parse_by_document_type` (unused — pipeline handles parsing)
- `from decimal import Decimal` (unused)

- [ ] **Step 2: Remove unused imports from validation_service.py**

In `src/services/validation_service.py`, remove the module-level `from decimal import Decimal` if it's unused at module level (only used inside methods where it's already imported locally).

- [ ] **Step 3: Remove unused imports from eligibility_service.py**

In `src/services/eligibility_service.py`, remove `from decimal import Decimal` if unused.

- [ ] **Step 4: Verify all imports still resolve**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from src.services.extraction_service import ExtractionService; from src.services.validation_service import ValidationService; from src.services.eligibility_service import EligibilityService; print('all imports ok')"
```
Expected: `all imports ok`

- [ ] **Step 5: Commit**

```bash
git add src/services/extraction_service.py src/services/validation_service.py src/services/eligibility_service.py
git commit -m "chore: remove unused imports from service modules"
```

---

### Task 9: Infrastructure Preflight

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: Docker, Ollama running on host
- Produces: Confirmation that all infrastructure is healthy

- [ ] **Step 1: Check Docker containers**

Run:
```powershell
docker compose ps
```
Expected: All 9 containers show `healthy` or `running`:
- xd_postgres (5432)
- xd_neo4j (7474, 7687)
- xd_qdrant (6333, 6334)
- xd_langfuse_web (4000)
- xd_langfuse_worker (3030)
- xd_langfuse_postgres (5433)
- xd_langfuse_clickhouse (8123, 9000)
- xd_langfuse_redis (6379)
- xd_langfuse_minio (9090, 9091)

If any container is not running:
```powershell
docker compose up -d
```

- [ ] **Step 2: Check Ollama models**

Run:
```powershell
ollama list
```
Expected: At least `qwen3.5:14b` and `nomic-embed-text:v1.5` are listed.

If models are missing:
```powershell
ollama pull qwen3.5:14b
ollama pull nomic-embed-text:v1.5
```

- [ ] **Step 3: Verify Ollama API is responding**

Run:
```powershell
.\.venv\Scripts\python.exe -c "import requests; r = requests.get('http://localhost:11434/api/tags'); print(r.status_code, [m['name'] for m in r.json().get('models', [])])"
```
Expected: `200` with list of model names

- [ ] **Step 4: Verify PostgreSQL connectivity**

Run:
```powershell
.\.venv\Scripts\python.exe -c "import asyncio; from sqlalchemy import text; from src.infrastructure.db.session import get_engine; from src.config import settings; async def check(): e = await get_engine(settings); async with e.connect() as c: r = await c.execute(text('SELECT 1')); print('postgres ok:', r.scalar()); asyncio.run(check())"
```
Expected: `postgres ok: 1`

- [ ] **Step 5: Run Alembic migrations**

Run:
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```
Expected: All migrations applied, no errors

---

### Task 10: Generate Fresh Account + Synthetic Documents

**Files:**
- None (uses existing `scripts/generate_fresh_account.py`)

**Interfaces:**
- Consumes: `src/data_generation/` module
- Produces: Fresh applicant profile with 6 document types in `data/test_applicants/`

- [ ] **Step 1: Generate fresh account**

Run:
```powershell
.\.venv\Scripts\python.exe scripts/generate_fresh_account.py --seed demo_2026
```
Expected: Script completes successfully, outputs the generated Emirates ID number and profile directory path.

Note the generated Emirates ID number — you'll need it for login in Task 13.

- [ ] **Step 2: Verify generated documents exist**

Run:
```powershell
Get-ChildItem -Recurse data/test_applicants/ | Select-Object FullName, Length
```
Expected: Directory contains:
- `profile.json`
- `emirates_id_front.png`
- `emirates_id_back.png`
- `bank_statement.pdf`
- `credit_report.pdf`
- `application_form.png`
- `assets_liabilities.xlsx` (or similar)

- [ ] **Step 3: Verify cross-document consistency**

Run:
```powershell
.\.venv\Scripts\python.exe -c "
import json
from pathlib import Path
profile_dir = max(Path('data/test_applicants').iterdir(), key=lambda p: p.stat().st_mtime)
profile = json.loads((profile_dir / 'profile.json').read_text())
print(f'Name: {profile[\"full_name\"]}')
print(f'ID: {profile[\"identity_number\"]}')
print(f'Category: {profile.get(\"support_category\", \"unknown\")}')
print(f'Expected decision: {profile.get(\"expected_decision\", \"unknown\")}')
"
```
Expected: Profile details printed with all fields populated.

---

### Task 11: Start Application Servers

**Files:**
- None (startup only)

**Interfaces:**
- Consumes: All infrastructure from Task 9
- Produces: FastAPI on port 8000, Streamlit on port 8501

- [ ] **Step 1: Kill any existing FastAPI process on port 8000**

Run:
```powershell
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force; Write-Host "killed PID $pid" } else { Write-Host "port 8000 free" }
```

- [ ] **Step 2: Start FastAPI backend**

Run in a new terminal:
```powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000
```
Expected: Server starts, logs show `Application startup complete`.

- [ ] **Step 3: Verify FastAPI health**

Run:
```powershell
.\.venv\Scripts\python.exe -c "import requests; r = requests.get('http://localhost:8000/api/v1/health/langgraph'); print(r.status_code, r.json())"
```
Expected: `200` with status `healthy` or `degraded` (not `unhealthy`)

- [ ] **Step 4: Kill any existing Streamlit process on port 8501**

Run:
```powershell
$pid = (Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force; Write-Host "killed PID $pid" } else { Write-Host "port 8501 free" }
```

- [ ] **Step 5: Start Streamlit frontend**

Run in a new terminal:
```powershell
.\.venv\Scripts\streamlit.exe run ui/streamlit_app.py --server.port 8501
```
Expected: Streamlit starts, shows URL `http://localhost:8501`

---

### Task 12: API Smoke Test (Real LLM)

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: FastAPI running on port 8000, fresh account from Task 10
- Produces: Confirmation that all API endpoints work with real LLM calls

- [ ] **Step 1: Login with generated Emirates ID**

Run:
```powershell
.\.venv\Scripts\python.exe -c "
import requests, json
from pathlib import Path

# Find the most recently generated profile
profile_dir = max(Path('data/test_applicants').iterdir(), key=lambda p: p.stat().st_mtime)
profile = json.loads((profile_dir / 'profile.json').read_text())
emirates_id = profile['identity_number']

r = requests.post('http://localhost:8000/api/v1/auth/login', json={'emirates_id': emirates_id})
print(f'Status: {r.status_code}')
data = r.json()
print(f'Applicant ID: {data.get(\"applicant_id\")}')
print(f'Application ID: {data.get(\"application_id\")}')
print(f'Phase: {data.get(\"current_phase\")}')

# Save for next steps
Path('data/.test_session.json').write_text(json.dumps({
    'emirates_id': emirates_id,
    'applicant_id': data.get('applicant_id'),
    'application_id': data.get('application_id'),
}))
"
```
Expected: `200`, applicant_id and application_id returned, phase is `intake`

- [ ] **Step 2: Send intake message (real LLM call)**

Run:
```powershell
.\.venv\Scripts\python.exe -c "
import requests, json
from pathlib import Path

session = json.loads(Path('data/.test_session.json').read_text())
app_id = session['application_id']

# Send intake information
r = requests.post(
    f'http://localhost:8000/api/v1/applications/{app_id}/chat',
    data={'text': 'My name is Ahmed Al Mansouri. I am divorced with 2 children. My support category is divorced. My phone is 0501234567 and email is ahmed@test.com. I live in Abu Dhabi. I am employed at ADNOC as an engineer. I rent my apartment. My family size is 3.'},
    files=[]
)
print(f'Status: {r.status_code}')
data = r.json()
print(f'Phase: {data.get(\"phase\")}')
print(f'Message: {data.get(\"message\", \"\")[:200]}')
"
```
Expected: `200`, phase advances to `document_collection`, LLM extracted fields from the message

- [ ] **Step 3: Upload documents (real extraction pipeline)**

Run:
```powershell
.\.venv\Scripts\python.exe -c "
import requests, json
from pathlib import Path

session = json.loads(Path('data/.test_session.json').read_text())
app_id = session['application_id']
profile_dir = max(Path('data/test_applicants').iterdir(), key=lambda p: p.stat().st_mtime)

# Upload all generated documents
files = []
for f in profile_dir.iterdir():
    if f.suffix.lower() in ('.pdf', '.png', '.jpg', '.jpeg', '.xlsx', '.docx'):
        files.append(('files', (f.name, open(f, 'rb'), f'application/{f.suffix.lstrip(\".\")}')))

r = requests.post(
    f'http://localhost:8000/api/v1/applications/{app_id}/chat',
    data={'text': 'Here are my documents for the application.'},
    files=files
)
print(f'Status: {r.status_code}')
data = r.json()
print(f'Phase: {data.get(\"phase\")}')
print(f'Documents: {len(data.get(\"uploaded_documents\", []))}')

# Close file handles
for _, (_, fh, _) in files:
    fh.close()
"
```
Expected: `200`, documents classified, phase advances to `processing`

- [ ] **Step 4: Verify document status endpoint**

Run:
```powershell
.\.venv\Scripts\python.exe -c "
import requests, json
from pathlib import Path

session = json.loads(Path('data/.test_session.json').read_text())
app_id = session['application_id']

r = requests.get(f'http://localhost:8000/api/v1/documents/status?application_id={app_id}')
print(f'Status: {r.status_code}')
data = r.json()
print(f'Documents: {len(data.get(\"documents\", []))}')
for doc in data.get('documents', []):
    print(f'  - {doc[\"document_type\"]}: {doc[\"status\"]} (confidence: {doc.get(\"confidence\")})')
"
```
Expected: `200`, list of documents with types and statuses

---

### Task 13: Full UI Flow (Real LLM + Real Docs)

**Files:**
- None (manual UI testing)

**Interfaces:**
- Consumes: Streamlit on port 8501, FastAPI on port 8000, fresh account from Task 10
- Produces: Confirmation that all 7 phases work end-to-end via the UI

- [ ] **Step 1: Open Streamlit UI**

Open browser to `http://localhost:8501`

Expected: Landing page with Emirates ID login form

- [ ] **Step 2: Phase 0 — Login**

Enter the Emirates ID generated in Task 10.

Expected: Login succeeds, redirected to chat page, phase shows as `intake`

- [ ] **Step 3: Phase 1 — Intake**

Type a message with personal information:
```
My name is Ahmed Al Mansouri. I am divorced with 2 children. My support category is divorced. My phone is 0501234567 and email is ahmed@test.com. I live in Abu Dhabi. I am employed at ADNOC as an engineer. I rent my apartment. My family size is 3.
```

Expected: LLM extracts fields, phase advances to `document_collection`. The response should acknowledge the support category.

- [ ] **Step 4: Phase 2 — Document Collection**

Upload all generated documents from the profile directory:
- Emirates ID front/back PNG
- Bank statement PDF
- Credit report PDF
- Application form PNG
- Assets/liabilities XLSX

Type: "Here are all my documents."

Expected: Documents classified, confidence scores computed, phase advances to `processing`

- [ ] **Step 5: Phase 3 — Processing**

Wait for extraction and validation to complete. This involves real LLM calls for extraction and real validation logic.

Expected: Processing completes, phase advances to `review` or `decision`

- [ ] **Step 6: Phase 4 — Review (if applicable)**

If discrepancies are detected, respond to clarification questions.

Expected: Phase advances to `decision`

- [ ] **Step 7: Phase 5 — Decision**

Wait for decision to be computed. This involves real LLM calls for eligibility and decision.

Expected: Decision card displayed (approved/manual_review/soft_decline) with explanation

- [ ] **Step 8: Phase 6 — Enablement**

View enablement recommendations.

Expected: Profile-matched recommendations displayed

---

### Task 14: Verify Observability

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: Langfuse running on port 4000
- Produces: Confirmation that traces are recorded

- [ ] **Step 1: Open Langfuse UI**

Open browser to `http://localhost:4000`

Expected: Langfuse dashboard loads

- [ ] **Step 2: Check traces**

Navigate to Traces page. Look for traces from the demo session.

Expected: Traces show:
- Orchestrator invocations
- Extraction subgraph calls
- Validation subgraph calls
- Eligibility subgraph calls
- Decision subgraph calls
- Real token counts and latencies

- [ ] **Step 3: Verify structured logs**

Check the FastAPI terminal output for structured log events:
- `node_enter` / `node_exit` for each phase
- `duration_ms` on service calls
- `chat_response_complete` with phase and decision info

Expected: JSON-formatted logs with all required fields

---

### Task 15: Session Restore

**Files:**
- None (manual testing)

**Interfaces:**
- Consumes: State snapshot persisted in PostgreSQL
- Produces: Confirmation that session state survives browser restart

- [ ] **Step 1: Close browser completely**

Close all browser windows/tabs.

- [ ] **Step 2: Reopen browser and login**

Open `http://localhost:8501`, login with the same Emirates ID from Task 10.

Expected: Session restored — chat history visible, phase is where you left off, uploaded documents shown in sidebar

- [ ] **Step 3: Verify state continuity**

Send a follow-up message or check the phase tracker.

Expected: State is continuous — no loss of context, phase tracker shows correct progress

---

## Self-Review Checklist

- [x] All 8 fixes from the spec have corresponding tasks (Tasks 1-8)
- [x] Verification plan has concrete steps with real LLM calls (Tasks 9-15)
- [x] No placeholders — every step has exact code or commands
- [x] Exact file paths throughout
- [x] Type/method names are consistent across tasks
- [x] Each task is independently testable
- [x] Frequent commits (one per task)
