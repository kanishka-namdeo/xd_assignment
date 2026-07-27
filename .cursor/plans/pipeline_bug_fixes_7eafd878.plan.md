---
name: Pipeline Bug Fixes
overview: "Fix critical runtime bugs, architectural issues, and UI/UX defects found during the agent pipeline scan: the decision_agent import crash, missing router registration, empty validation prompt, layering violations, empty domain constants, legacy stub cleanup, phase name mismatches, duplicate set_page_config calls, file handle leaks, missing interrupt rendering, hardcoded UI constants, service layer gaps, schema mismatches, and test updates."
todos:
  - id: fix-decision-import
    content: Fix critical decision_agent ImportError in orchestrator/phases/decision.py line 72
    status: completed
  - id: fix-router-registration
    content: Register documents router in api/router.py
    status: completed
  - id: fix-async-checkpointer
    content: Fix sync/async checkpointer mismatch in validation/graph.py
    status: completed
  - id: cache-validation-graph
    content: Cache compiled validation graph to avoid rebuilding on every invocation
    status: pending
  - id: add-validation-prompt
    content: Add validation agent system prompt in validation/prompts.py and refactor nodes to use LLM
    status: completed
  - id: create-auth-service
    content: Create AuthService in src/services/auth_service.py and refactor auth.py to use it
    status: pending
  - id: create-chat-service
    content: Upgrade chat_service.py from function to class-based ChatService and refactor chat.py
    status: pending
  - id: update-deps
    content: Add get_auth_service and get_chat_service to src/api/deps.py
    status: pending
  - id: fix-schema-auth-response
    content: Add applicant_info, support_category, identity_number to AuthLoginResponse schema
    status: pending
  - id: fix-schema-chat-response
    content: Add enablement_recommendations and discrepancies fields to ChatResponse schema
    status: pending
  - id: populate-constants
    content: Populate empty domain constants and resolve 3 threshold inconsistencies
    status: completed
  - id: remove-legacy-stubs
    content: Remove legacy graph_db/ and vector_db/ stub directories
    status: completed
  - id: refactor-tool-thinness
    content: "Refactor tool thinness: extract shared logging decorator to reduce tool boilerplate"
    status: completed
  - id: fix-ui-phase-mismatch
    content: "Fix phase name mismatch: chat.py PHASE_LABELS uses 'auth' but backend returns 'authentication'"
    status: pending
  - id: fix-ui-set-page-config
    content: Remove duplicate st.set_page_config calls in chat.py and landing.py (already called in streamlit_app.py)
    status: pending
  - id: fix-ui-file-handle-leak
    content: Fix file handle leak in chat_area.py _call_chat_api (open() without context manager)
    status: pending
  - id: fix-ui-interrupt-rendering
    content: Add interrupt/clarification rendering in chat_area.py (backend returns interrupt data but UI ignores it)
    status: pending
  - id: fix-ui-hardcoded-docs
    content: Decouple document_status.py REQUIRED_DOCS_BY_CATEGORY from hardcoded values; import from domain constants
    status: pending
  - id: fix-ui-applicant-info
    content: Set applicant_info and identity_number in session state during login
    status: pending
  - id: fix-ui-enablement-type
    content: Fix enablement_section.py type mismatch (expects list[str] but may receive dict from API)
    status: pending
  - id: fix-ui-doc-type-field
    content: Fix doc_type vs document_type field name mismatch in chat_area.py
    status: pending
  - id: fix-ui-session-restore
    content: Fix uploaded_documents key mismatch on session restore (graph state uses document_type, UI expects doc_type)
    status: pending
  - id: update-tests-decision-agent
    content: Update test patches for decision_agent import fix (3 files, 9 locations)
    status: pending
  - id: update-tests-auth-chat
    content: Update test patches for auth/chat service refactor (live_api_test.py)
    status: pending
  - id: update-tests-constants
    content: Update test assertions if document collection message format changes
    status: pending
isProject: false
---

# Fix Agent Pipeline Bugs, Architectural Issues, and UI/UX Defects

Priority-ordered fixes from the pipeline scan. Critical runtime bugs first, then high-impact gaps, then UI/UX fixes, then architectural cleanup.

---

## 1. Fix critical `decision_agent` ImportError (runtime crash)

**File**: `src/agents/orchestrator/phases/decision.py` line 72

The import `from src.agents.decision.graph import decision_agent` fails because `decision/graph.py` only exports `get_decision_agent()`. Phase 5 crashes at runtime.

**Fix**: Change line 72 to use the factory function:
```python
from src.agents.decision.graph import get_decision_agent
decision_agent = get_decision_agent()
```

---

## 2. Register documents router in `router.py`

**File**: `src/api/router.py`

The documents router is never included, making all document endpoints unreachable.

**Fix**: Add import and registration:
```python
from src.api.v1 import applications, auth, chat, eligibility, documents
# ...
router.include_router(documents.router)
```

Note: `documents.py` is currently a stub (only `/status` health check). Registering it now makes the router reachable; the stub endpoints can be expanded later.

---

## 3. Fix validation graph: checkpointer + caching + system prompt

**Files**: `src/agents/validation/graph.py`, `src/agents/validation/prompts.py`, `src/agents/validation/nodes.py`

Three issues in the validation agent:

**3a. Sync/async checkpointer mismatch** (`graph.py` line 75): Uses sync `PostgresSaver.from_conn_string()` while the orchestrator uses `AsyncPostgresSaver`. When validation is invoked from async context via `ainvoke()`, this can cause event loop issues.

**Fix**: Switch to `AsyncPostgresSaver`:
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
```

**3b. Graph rebuilds on every invocation** (`graph.py` lines 75-77, 115): `run_validation_agent()` calls `build_validation_graph()` which creates a new DB connection and runs `.setup()` DDL each time. No caching.

**Fix**: Cache the compiled graph at module level or use a factory with memoization:
```python
_compiled_graph = None

def get_validation_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_validation_graph()
    return _compiled_graph
```

**3c. Empty system prompt** (`prompts.py`): Currently empty (just a docstring). All validation nodes are deterministic tool invocations with no LLM calls. `SystemMessage` is imported in `nodes.py` but never used.

**Fix**: Define `VALIDATION_SYSTEM_PROMPT` covering role, tools, and Reflexion loop instructions. Then refactor `attempt_validation_node` to use `create_react_agent` with the system prompt (matching the pattern used in `decision/nodes.py`). This converts the validation agent from pure tool calls to an LLM-guided Reflexion loop.

---

## 4. Fix layering violations: create AuthService and ChatService

**Files**: `src/api/v1/auth.py`, `src/api/v1/chat.py`, `src/services/auth_service.py`, `src/services/chat_service.py`, `src/api/deps.py`, `src/domain/schemas/auth.py`

Both endpoints directly instantiate infrastructure repositories, bypassing the service layer.

**4a. Create `AuthService`** in `src/services/auth_service.py`:
- Uses `ApplicantRepository` + `ApplicationRepository`
- Method: `login(emirates_id: str) -> dict` — encapsulates validate, find/create applicant, find/create application, return state snapshot
- Follow existing service pattern: class with `__init__(session: AsyncSession)`, structlog logger, `duration_ms` logging

**4b. Upgrade `chat_service.py`** from function to class-based `ChatService`:
- Uses `ApplicationRepository` + `DecisionService`
- Method: `handle_chat(application_id, text, file_paths, langfuse_client)` — encapsulates state load/save, orchestrator invocation, interrupt handling, decision persistence, phase transitions
- Move file-save logic from `chat.py` lines 93-104 into `DocumentService` or a helper
- Move `decision_formatting_tool` import (Layer 3 import from Layer 1) into the service
- Move `LangfuseClient` access (Layer 4 import from Layer 1) into the service

**4c. Update `src/api/deps.py`**:
- Add `get_auth_service(db) -> AuthService`
- Add `get_chat_service(db) -> ChatService`

**4d. Extend `AuthLoginResponse`** in `src/domain/schemas/auth.py`:
- Add `applicant_info: dict | None = None` — UI needs `support_category` for document requirements
- Add `identity_number: str | None = None` — UI needs it for header badge and returning user banner
- The `AuthService.login()` method populates these from the applicant/application records

**4e. Extend `ChatResponse`** in `src/domain/schemas/chat.py`:
- Add `enablement_recommendations: list[dict] | None = None` — currently not in schema, UI reads it but always gets None
- Add `discrepancies: list[dict] | None = None` — currently not in schema, UI reads it but always gets None
- The `ChatService.handle_chat()` method populates these from the graph state result

---

## 5. Populate empty domain constants and resolve inconsistencies

**Files**:
- `src/domain/constants/document_types.py`
- `src/domain/constants/validation_rules.py`
- `src/domain/constants/eligibility_rules.py`
- `src/services/extraction_service.py`
- `src/services/validation_service.py`
- `src/services/eligibility_service.py`
- `src/agents/orchestrator/phases/document_collection.py`
- `ui/components/document_status.py`

Currently empty stubs. Business logic is hardcoded in 6+ locations.

**5a. Extract constants from services**:
- `document_types.py`: Extract `REQUIRED_DOCUMENTS` dict (per support category) from `extraction_service.py`, `validation_service.py`, and `document_collection.py`
- `validation_rules.py`: Extract validation rule definitions from gate implementations
- `eligibility_rules.py`: Extract `CATEGORY_ADJUSTMENTS` and thresholds from `eligibility_service.py`

**5b. Resolve 3 threshold inconsistencies** discovered during scan:
1. Employment stability threshold: `eligibility_service.py` uses 24 months, `eligibility/tools.py` uses 36 months — standardize to 24 months
2. Soft decline threshold: `decision/prompts.py` uses 0.40, `decision_service.py` uses 0.50 — standardize to 0.40
3. `eligibility_rules.py` hardcodes a 2-doc required list instead of category-aware dicts — use the centralized `REQUIRED_DOCUMENTS`

**5c. Update all consumers** to import from constants:
- `src/services/extraction_service.py`
- `src/services/validation_service.py`
- `src/services/eligibility_service.py`
- `src/agents/orchestrator/phases/document_collection.py`
- `ui/components/document_status.py` (after UI fixes in section 13)

---

## 6. Remove legacy stub directories

**Paths**: `src/infrastructure/graph_db/`, `src/infrastructure/vector_db/`

These are dead code. Active modules are `graph/` and `vector/`.

**Fix**: Delete both directories. Verify no imports reference them (grep for `graph_db` and `vector_db` in `src/`).

---

## 7. Fix API-UI contract mismatches

**Files**: `src/domain/schemas/chat.py`, `src/domain/schemas/auth.py`, `ui/app_pages/landing.py`, `ui/app_pages/chat.py`, `ui/fragments/chat_area.py`

10 field mismatches between API responses and UI expectations:

**7a. `doc_type` vs `document_type`** — `chat_area.py` line 178 reads `doc.get("document_type", "Document")` but API returns `doc_type`. Chat messages always show "Document uploaded" instead of the actual type.

**Fix**: Change `chat_area.py` to read `doc.get("doc_type", "Document")`.

**7b. `enablement_recommendations` missing from ChatResponse** — UI reads it but API never returns it. The data exists inside `decision_card["enablement_section"]` but not as a top-level field.

**Fix**: Add `enablement_recommendations: list[dict] | None = None` to `ChatResponse`. Populate from graph state in `ChatService`.

**7c. `discrepancies` missing from ChatResponse** — UI reads it but API never returns it.

**Fix**: Add `discrepancies: list[dict] | None = None` to `ChatResponse`. Populate from graph state in `ChatService`.

**7d. `identity_number` not set in session state** — `landing.py` `handle_login()` never sets `st.session_state.identity_number`. UI header always shows masked placeholder.

**Fix**: After `AuthLoginResponse` is extended with `identity_number` (fix 4d), set it in session state in `landing.py`:
```python
st.session_state.identity_number = data.get("identity_number", formatted_id)
```

**7e. `applicant_info` not set in session state** — Same root cause. After `AuthLoginResponse` is extended (fix 4d), set it in `landing.py`:
```python
st.session_state.applicant_info = data.get("applicant_info")
```

**7f. `uploaded_documents` key mismatch on session restore** — Graph state uses `document_type` key, but `document_status.py` reads `doc_type`. On session restore, all docs appear missing.

**Fix**: Normalize keys in `landing.py` when restoring from state snapshot:
```python
for doc in state_snapshot.get("uploaded_documents", []):
    if "document_type" in doc and "doc_type" not in doc:
        doc["doc_type"] = doc["document_type"]
```

---

## 8. Refactor tool thinness (optional, lower priority)

17 of 19 tools exceed the 30-line limit. The bloat comes from logging boilerplate (~10-15 lines per tool).

**Approach**: Extract a shared `@tool_wrapper` decorator in `src/utils/tool_helpers.py` that handles:
- `start = time.perf_counter()` / `duration_ms` computation
- `logger.info("tool_invoke", ...)` / `logger.info("tool_complete", ...)`
- try/except error handling

Each tool body then only contains input validation + domain call + return formatting, bringing most under 30 lines.

This is a larger refactor -- do after the critical/high fixes are in.

---

## 9. Fix phase name mismatch in UI

**File**: `ui/app_pages/chat.py` line 19

`PHASE_LABELS` uses `"auth"` as the key, but the backend returns `"authentication"` as the phase value. The phase badge in the header will show the raw value instead of the label.

**Fix**: Change the key from `"auth"` to `"authentication"`:
```python
PHASE_LABELS = {
    "authentication": "Authentication",  # was "auth"
    ...
}
```

Note: `ui/components/phase_tracker.py` already uses `"authentication"` correctly. Only `chat.py` has the mismatch.

---

## 10. Remove duplicate `st.set_page_config` calls

**Files**: `ui/app_pages/chat.py` line 155, `ui/app_pages/landing.py` line 305

`streamlit_app.py` already calls `st.set_page_config()` on line 24. Calling it again inside a page render function causes `StreamlitAPIException: set_page_config can only be called once per app`.

**Fix**: Remove the `st.set_page_config()` calls from both `chat.py` (line 155) and `landing.py` (line 305). The entrypoint in `streamlit_app.py` is the single source of truth.

---

## 11. Fix file handle leak in chat_area.py

**File**: `ui/fragments/chat_area.py` line 50

`_call_chat_api` opens files with `open(path, "rb")` but never closes them. On repeated uploads, this leaks file descriptors.

**Fix**: Use context managers or read all file contents before the request:
```python
def _call_chat_api(application_id: str, text: str, file_paths: list[str]) -> dict[str, Any]:
    url = f"{API_BASE}/api/v1/applications/{application_id}/chat"
    form_data = {"text": text}
    
    opened_files = []
    try:
        for path in file_paths:
            f = open(path, "rb")
            opened_files.append(("files", (Path(path).name, f, "application/octet-stream")))
        resp = requests.post(url, data=form_data, files=opened_files, timeout=60)
        resp.raise_for_status()
        return resp.json()
    finally:
        for _, (_, fh, _) in opened_files:
            fh.close()
```

---

## 12. Add interrupt/clarification rendering in chat area

**File**: `ui/fragments/chat_area.py`

The backend returns `interrupt` data in `ChatResponse` (clarification questions from validation agent), but `_append_assistant_message` stores it without rendering. The chat area never displays interrupt content to the user.

**Fix**: In `render_chat_area()`, after rendering the message content, check for interrupt data and render it as a styled clarification card:
```python
if msg.get("interrupt"):
    interrupt = msg["interrupt"]
    st.info(f"**Question:** {interrupt.get('question', '')}")
    if interrupt.get("missing_fields"):
        st.warning("Missing fields: " + ", ".join(interrupt["missing_fields"]))
    if interrupt.get("missing_documents"):
        st.warning("Missing documents: " + ", ".join(interrupt["missing_documents"]))
    if interrupt.get("discrepancies"):
        render_discrepancy_cards(interrupt["discrepancies"])
```

---

## 13. Decouple document_status.py from hardcoded constants

**File**: `ui/components/document_status.py` lines 21-29

`REQUIRED_DOCS_BY_CATEGORY` and `DEFAULT_REQUIRED_DOCS` are hardcoded in the UI component. These should come from the domain constants (populated in fix #5).

**Fix**: After fix #5 populates `src/domain/constants/document_types.py`, import from there:
```python
from src.domain.constants.document_types import REQUIRED_DOCUMENTS, DEFAULT_REQUIRED_DOCS
```

Remove the local duplicates. This ensures the UI checklist stays in sync with backend validation rules.

---

## 14. Fix missing `applicant_info` in session state

**File**: `ui/app_pages/chat.py` lines 228-229

The chat endpoint reads `result.get("applicant_info", {}).get("support_category", "unknown")` for decision formatting, but `applicant_info` is never set in session state during login. The `AuthLoginResponse` schema doesn't include it.

**Fix**: Two options:
- **Option A**: Add `applicant_info` to `AuthLoginResponse` and set it in session state during login
- **Option B**: Have the chat endpoint read `support_category` from the graph state instead of `applicant_info` session state

Option B is simpler -- the orchestrator already tracks `support_category` in the state after intake. Update `chat.py` to read from the API response's phase state rather than session state.

---

## 15. Fix enablement_section.py type mismatch

**File**: `ui/components/enablement_section.py` line 20

Function signature expects `recommendations: list[str] | None`, but the API may return a dict with a `"recommendations"` key containing a list. The `chat_area.py` passes `msg["enablement_recommendations"]` directly without type checking.

**Fix**: Add type coercion at the top of `render_enablement_section`:
```python
def render_enablement_section(recommendations: list[str] | dict | None = None) -> None:
    if isinstance(recommendations, dict):
        recommendations = recommendations.get("recommendations", [])
    if not recommendations:
        ...
```

---

## Execution Order

1. Fix #1 (decision_agent import) -- 1 line change, unblocks Phase 5
2. Fix #2 (router registration) -- 2 lines, unblocks document API
3. Fix #7 (async checkpointer) -- small change, prevents runtime issues
4. Fix #10 (duplicate set_page_config) -- remove 2 lines, prevents crash
5. Fix #9 (phase name mismatch) -- 1 key rename
6. Fix #11 (file handle leak) -- wrap in try/finally
7. Fix #3 (validation prompt) -- new content + wire into nodes
8. Fix #12 (interrupt rendering) -- add UI for clarification questions
9. Fix #15 (enablement type mismatch) -- add type coercion
10. Fix #14 (applicant_info) -- read from graph state
11. Fix #4 (layering violations) -- new service + refactor 2 endpoints
12. Fix #5 (domain constants) -- extract + update imports
13. Fix #13 (UI hardcoded docs) -- import from domain constants
14. Fix #6 (legacy stubs) -- delete + grep verification
15. Fix #8 (tool thinness) -- optional refactor
