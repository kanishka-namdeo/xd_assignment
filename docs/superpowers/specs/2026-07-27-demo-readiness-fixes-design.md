# Demo Readiness Fixes — Design Specification

**Date:** 2026-07-27
**Author:** Agent
**Status:** Approved
**Approach:** B — Pragmatic Demo-Ready

---

## Executive Summary

This spec addresses 8 bugs and architectural issues discovered during a full codebase scan, plus a verification plan to demonstrate the complete 7-phase applicant flow end-to-end with real LLM calls and freshly generated synthetic documents. The goal is to make the application demo-ready for end users with zero mocks.

**Approach chosen:** Pragmatic Demo-Ready — fix all runtime crashes, state management bugs, and architecture violations; verify the full flow with real infrastructure and real LLM calls.

---

## Problem Statement

A comprehensive scan of all 5 layers (API, services, agents, infrastructure, UI) identified the following issues that prevent the application from being demo-ready:

### Critical (will crash at runtime)
1. **`_UUID()` undefined** — `src/services/extraction_pipeline.py` calls `_UUID()` on lines 181, 198, 240, 242 but the function is never defined. The import is `from uuid import UUID, uuid4`. This will raise `NameError` when `persist_results()` runs.
2. **Document status endpoint is a stub** — `GET /api/v1/documents/status` in `src/api/v1/documents.py` returns `{"status": "ok"}` with no real logic.

### State management bugs
3. **`support_category` not propagated to top-level state** — The intake node stores `support_category` inside `applicant_info` dict but never sets `state["support_category"]`. Sub-agents (validation, decision) read `state.get("support_category")` directly, which returns `None`.
4. **`new_documents_uploaded` flag never set** — The review node checks `state.get("new_documents_uploaded", False)` to detect new uploads, but no node ever sets this to `True`.

### Architecture violations
5. **Service imports agent tools** — `src/services/chat_service.py` imports `decision_formatting_tool` from `src.agents.decision.tools`, violating the four-layer architecture (services should not import from agent tools).
6. **Hardcoded model names** — `src/api/v1/chat.py` hardcodes `"kat-coder-pro-v2.5"` instead of using `settings.STREAMLAKE_MODEL`.

### Dead code
7. **Chat streaming bypasses orchestrator** — `POST /applications/{id}/chat/stream` in `src/api/v1/chat.py` uses raw LLM streaming instead of the orchestrator graph. The UI doesn't use this endpoint, but it's misleading dead code.

### Minor
8. **Unused imports** — `Decimal` imported but unused in `validation_service.py`, `eligibility_service.py`; `parse_by_document_type` imported but unused in `extraction_service.py`.

---

## Scope

### In Scope
- All 8 fixes listed above
- Fresh test account generation with synthetic documents
- End-to-end verification with real LLM calls (no mocks)
- Full 7-phase flow verification via UI and API

### Out of Scope
- Extraction pipeline's cross-layer import of `ValidationService` (works, refactor later)
- Empty `__init__.py` files in `vector/` and `graph/` (cosmetic)
- Service-layer unit tests (separate effort)
- API route unit tests (separate effort)

---

## Detailed Fixes

### Fix 1: `_UUID()` → `UUID()` in extraction_pipeline.py

**File:** `src/services/extraction_pipeline.py`
**Lines:** 181, 198, 240, 242

**Problem:** `_UUID(...)` is called but never defined. The import at line 8 is `from uuid import UUID, uuid4`.

**Fix:** Replace all 4 occurrences of `_UUID(...)` with `UUID(...)`.

**Before:**
```python
_UUID(er["document_id"]) if isinstance(er["document_id"], str) else er["document_id"]
```

**After:**
```python
UUID(er["document_id"]) if isinstance(er["document_id"], str) else er["document_id"]
```

**Impact:** Prevents `NameError` crash when `persist_results()` runs.

---

### Fix 2: Document Status Endpoint

**File:** `src/api/v1/documents.py`

**Problem:** `GET /api/v1/documents/status` is a stub returning `{"status": "ok"}`.

**Fix:** Implement a real endpoint that:
- Accepts `application_id` as a query parameter
- Queries `DocumentRepository` for documents by applicant
- Returns a list of documents with type, status, confidence, and upload timestamp
- Follows the same thin-route pattern as other endpoints (parse input, call service/repository, return response)

**Implementation:**
```python
@router.get("/status")
async def document_status(
    application_id: str,
    db: AsyncDB,
) -> dict:
    """Return document upload status for an application."""
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

**Impact:** UI and API consumers can query real document status.

---

### Fix 3: `support_category` State Propagation

**File:** `src/agents/orchestrator/phases/intake.py`

**Problem:** Intake stores `support_category` in `applicant_info` but never sets the top-level `state["support_category"]`. Sub-agents read `state.get("support_category")` directly and get `None`.

**Fix:** When intake completes (all fields collected), set the top-level `support_category` state field alongside `applicant_info`.

**Before:**
```python
result = {
    "messages": [{"role": "assistant", "content": response}],
    "current_phase": "document_collection",
    "applicant_info": applicant_info,
}
```

**After:**
```python
result = {
    "messages": [{"role": "assistant", "content": response}],
    "current_phase": "document_collection",
    "applicant_info": applicant_info,
    "support_category": applicant_info.get("support_category"),
}
```

**Impact:** Validation and decision agents receive the correct support category.

---

### Fix 4: `new_documents_uploaded` Flag

**File:** `src/agents/orchestrator/phases/document_collection.py`

**Problem:** The review node checks `state.get("new_documents_uploaded", False)` to detect new uploads, but no node sets this to `True`.

**Fix:** When document_collection classifies and persists new documents, set `new_documents_uploaded: True` in the returned state dict.

**Implementation:** In the document_collection node, when new documents are successfully classified:
```python
result = {
    "messages": [...],
    "current_phase": "processing",
    "uploaded_documents": new_docs,
    "new_documents_uploaded": True,  # ADD THIS
}
```

**Impact:** Review node can correctly detect fresh uploads.

---

### Fix 5: Chat Streaming — Wire to Orchestrator

**File:** `src/api/v1/chat.py`

**Problem:** `POST /applications/{id}/chat/stream` uses raw LLM streaming instead of the orchestrator graph. The UI doesn't use this endpoint, but it's misleading.

**Fix:** Replace the raw LLM stream generator with one that uses `ChatService` / orchestrator's `run_streaming()` from `agent_runner.py`. The streaming endpoint should yield SSE events for phase transitions, extraction results, and the final decision.

**Implementation:** Use `run_streaming()` from `src/services/agent_runner.py` which yields structured events (phase transitions, extraction_complete, validation_complete, decision_reached, interrupt). Format each event as an SSE message.

**Impact:** Streaming endpoint is functional and consistent with the non-streaming endpoint.

---

### Fix 6: Move `decision_formatting_tool` Out of Service Layer

**File:** `src/services/chat_service.py`

**Problem:** Direct import of `decision_formatting_tool` from `src.agents.decision.tools` violates the four-layer architecture.

**Fix:** Add a `format_decision_card()` method to `DecisionService` that wraps the tool call. Update `chat_service.py` to call `DecisionService.format_decision_card()` instead of importing the tool directly.

**Implementation:**
```python
# In src/services/decision_service.py
class DecisionService:
    def format_decision_card(self, decision_data: dict) -> dict:
        """Format a decision for UI display."""
        from src.agents.decision.tools import decision_formatting_tool
        return decision_formatting_tool.invoke(decision_data)

# In src/services/chat_service.py
# Replace:
# from src.agents.decision.tools import decision_formatting_tool
# With:
decision_svc = DecisionService(self.session)
formatted_card = decision_svc.format_decision_card({...})
```

**Impact:** Service layer no longer imports agent tools directly. Architecture violation resolved.

---

### Fix 7: Replace Hardcoded Model Names

**File:** `src/api/v1/chat.py`

**Problem:** Lines 42 and 118 hardcode `"kat-coder-pro-v2.5"` instead of using `settings.STREAMLAKE_MODEL`.

**Fix:** Replace hardcoded strings with `settings.STREAMLAKE_MODEL`.

**Before:**
```python
model="kat-coder-pro-v2.5"
```

**After:**
```python
model=settings.STREAMLAKE_MODEL
```

**Impact:** Model name is configurable via environment variable.

---

### Fix 8: Clean Up Unused Imports

**Files:**
- `src/services/extraction_service.py` — remove unused `parse_by_document_type` and `Decimal`
- `src/services/validation_service.py` — remove unused `Decimal` at module level
- `src/services/eligibility_service.py` — remove unused `Decimal`

**Impact:** Cleaner code, no functional change.

---

## Demo Verification Plan

### Key Principle: No Mocks — Real Stack End-to-End

Every verification step uses:
- **Real LLM calls** via StreamLake (or Ollama fallback) — not mocked
- **Real generated documents** from `scripts/generate_fresh_account.py` — not hand-crafted
- **Real infrastructure** — PostgreSQL, Neo4j, Qdrant, Ollama all running
- **Real LangGraph graphs** — full orchestrator with all sub-agents

### Step 1: Infrastructure Preflight

```powershell
docker compose ps          # all 9 containers healthy
ollama list                # models pulled (qwen3.5:14b, nomic-embed-text)
```

Expected: All containers show `healthy` or `running`. Ollama models are available.

### Step 2: Generate Fresh Account + Documents

```powershell
.\.venv\Scripts\python.exe scripts/generate_fresh_account.py --seed demo_2026
```

Produces: Emirates ID front/back PNG, bank statement PDF, credit report PDF, application form PNG, assets/liabilities XLSX — all cross-document consistent with a known profile.

### Step 3: Start Application Servers

```powershell
# Terminal 1: FastAPI backend (real LLM calls)
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000

# Terminal 2: Streamlit frontend
.\.venv\Scripts\streamlit.exe run ui/streamlit_app.py --server.port 8501
```

### Step 4: API Smoke Test (Real LLM)

Run a script that hits the live API with real requests:
- `POST /api/v1/auth/login` with generated Emirates ID
- `POST /api/v1/applications/{id}/chat` with intake message → real LLM extracts fields
- `POST /api/v1/applications/{id}/chat` with file uploads → real extraction pipeline
- Verify document status endpoint returns real data
- Verify Langfuse traces are recorded (observability check)

### Step 5: Full UI Flow (Real LLM + Real Docs)

Walk through all 7 phases in Streamlit using the generated documents:

| Phase | Action | Real Component |
|-------|--------|----------------|
| 0 — Auth | Login with generated Emirates ID | Real DB write |
| 1 — Intake | Type personal info | Real LLM call extracts fields |
| 2 — Doc Collection | Upload generated PDFs/PNGs/XLSX | Real document processing |
| 3 — Processing | Auto-triggered | Real extraction subgraph + validation subgraph with LLM |
| 4 — Review | Handle discrepancies | Real LLM generates clarification if needed |
| 5 — Decision | Auto-triggered | Real eligibility subgraph + decision subgraph with LLM |
| 6 — Enablement | Displayed | Real LLM-generated recommendations |

### Step 6: Verify Observability

- Check Langfuse UI at `http://localhost:4000` — traces should show all agent calls with real token counts and latencies
- Check structured logs for `duration_ms` on all service calls

### Step 7: Session Restore

- Close browser, reopen, login again — state snapshot restores from DB, chat history preserved

---

## Affected Areas

| Area | Status | Notes |
|------|--------|-------|
| API routes | changed | Fix document status endpoint, chat streaming, hardcoded model names |
| Services | changed | Fix extraction_pipeline `_UUID()`, move decision_formatting_tool to DecisionService, clean unused imports |
| Agents | changed | Fix support_category propagation in intake, set new_documents_uploaded in document_collection |
| Domain | not affected | No changes needed |
| Infrastructure | not affected | No changes needed |
| Tests | not affected | No test changes in this scope (separate effort) |
| Migrations | not affected | No schema changes |
| Config | not affected | No new env vars |
| Logging/observability | not affected | Existing logging sufficient |
| Docs | changed | This spec |

---

## Dependency Map

Files affected through import/call chains:

1. `src/services/extraction_pipeline.py` — called by `extraction_service.py`, which is called by `processing_node` in orchestrator
2. `src/api/v1/documents.py` — registered in `src/api/router.py`, called by UI
3. `src/agents/orchestrator/phases/intake.py` — called by orchestrator graph, state flows to all subsequent phases
4. `src/agents/orchestrator/phases/document_collection.py` — called by orchestrator graph, state flows to processing/review
5. `src/api/v1/chat.py` — called by UI, calls `ChatService`
6. `src/services/chat_service.py` — called by chat endpoint, calls orchestrator and `DecisionService`
7. `src/services/decision_service.py` — called by `chat_service.py`, will wrap `decision_formatting_tool`

---

## Risk Notes

1. **Streaming endpoint rewrite** — Replacing the raw LLM stream with orchestrator streaming is the highest-risk change. The `run_streaming()` function yields structured events, not raw text deltas. The SSE format must be preserved for compatibility.

2. **State propagation** — Adding `support_category` to the top-level state is a small change but affects all downstream nodes. Must verify that validation and decision agents correctly use the value.

3. **Fresh account generation** — The `generate_fresh_account.py` script must produce valid documents that pass all extraction and validation gates. If the generators have bugs, the demo will fail at processing phase.

4. **Real LLM calls** — Using real LLM calls means the demo depends on StreamLake/Ollama availability and rate limits. If the LLM provider is down, the demo fails.

5. **No test coverage** — This spec fixes bugs but doesn't add tests. The fixes should be verified manually, but automated tests are out of scope.

---

## Success Criteria

1. All 7 phases work end-to-end with fresh account
2. No runtime crashes (no `NameError`, no stub endpoints)
3. State propagates correctly to all sub-agents
4. Architecture violations resolved (no service→agent tool imports)
5. Fresh test account created with synthetic documents
6. Real LLM calls used throughout (no mocks)
7. Langfuse traces recorded for all agent calls
8. Session restore works (state persists across browser restarts)

---

## Future Improvements (Out of Scope)

- Add unit tests for service layer
- Add API route tests
- Refactor extraction_pipeline to use dependency injection instead of direct service imports
- Add E2E test suite with real LLM calls
- Populate empty `__init__.py` files with proper exports
- Add type annotations for `TableExtractionResult.tables` (currently mismatched with runtime)
