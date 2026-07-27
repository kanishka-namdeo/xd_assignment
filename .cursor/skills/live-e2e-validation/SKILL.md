---
name: live-e2e-validation
description: Live end-to-end validation of the Social Support Application system through the lens of a real end user interacting with the agent-based UI. Uses real LLM requests (StreamLake + Ollama embeddings), actual generated documents, and fresh test accounts. Focuses on the complete user journey — from landing page through enablement — and fixes whatever breaks along the way, regardless of which layer the bug lives in. Produces a living tracker document from the start.
---

# Live E2E Validation

## Mission

Validate that the full application works end-to-end **from the perspective of a real applicant** interacting with the agent-based UI. Use **real LLM requests** (StreamLake `kat-coder-pro-v2.5` for reasoning by default, Ollama `nomic-embed-text:v1.5` for embeddings) and **actual generated documents** — not mocks. Drive the application forward through the UI exactly as a human would, observe what the user sees and experiences, fix whatever breaks (UI, API, agent, infrastructure — no layer is off-limits), and iterate until the full user journey is smooth. Produce a living tracker document from the start.

**Context isolation:** Testing subagents (1–2) are read-only observers — they detect and report failures but never touch code. Fix subagents (3A–3C) are code-writing agents with isolated context, each owning a distinct failure domain. This keeps test contexts lean and fix contexts focused on the actual repair work.

**Search-first discipline:** Before diagnosing any failure, run a web search for the exact error or symptom plus the relevant library name and the year (2026). Do not guess. Do not attempt a fix without first consulting current library-specific documentation. This applies to every phase and every subagent.

## Abort Conditions

Stop and report to the user immediately if any of the following occur:
- Infrastructure will not start after 2 restart attempts (likely Docker or port conflict beyond scope).
- LLM health endpoint returns unhealthy after verifying Ollama and `.env` are correct (LLM provider issue, not an app bug).
- A bug requires architectural changes (schema migration, agent graph rewrite, new service layer) that cannot be resolved in a single session.
- Three consecutive fix-and-retest cycles fail on the same step (diminishing returns — needs human review).

## Proactive Web Search (applies to main agent and all subagents)

**Search before acting** when any of the following conditions hold. Do not guess — search first.

| Trigger | Search for |
|---------|-----------|
| Unfamiliar error message or stack trace | The exact error + library name + year |
| Library-specific behaviour (LangGraph, Streamlit, FastAPI, structlog, alembic, asyncpg) | Current API docs, migration guides, known issues for the installed version |
| Version-specific error (e.g., after a dependency update) | `<library> <version> breaking change` or `<error> <library> <year>` |
| Low confidence in a diagnosis or fix | The specific symptom + suspected cause; cross-reference at least 2 sources |
| Agent behaviour seems off (confusing responses, wrong phase transitions) | LangGraph `interrupt()`, `Command(resume=...)`, checkpoint recovery patterns for the installed version |
| UI component misbehaves (phase tracker not updating, decision card not rendering) | Streamlit `st.fragment`, `st.navigation`, component re-render patterns for the installed version |
| Database or migration issue | Alembic migration conflict resolution, asyncpg connection pool errors |

**Search discipline:**
- Include the year (2026) in searches for time-sensitive topics (library versions, breaking changes).
- Note the source date when available. If sources conflict, acknowledge uncertainty and prefer the most recent official documentation.
- Prefer official docs and GitHub issues over blog posts for library-specific queries.
- Use the `context7` MCP server for library documentation when available (avoids web search overhead).
- Do not search for stable, well-established patterns (basic REST, SQL, Pydantic validation, standard Python syntax).

## Phase 1: Preflight

Run these checks in order. **Do not proceed past a failed check without fixing it first.**

### 1.1 Infrastructure

```powershell
docker compose ps
# Expect: all 9 containers Up/healthy
# xd_postgres, xd_neo4j, xd_qdrant, xd_langfuse_web, xd_langfuse_worker,
# xd_langfuse_postgres, xd_langfuse_clickhouse, xd_langfuse_redis, xd_langfuse_minio

curl http://localhost:11434
# Expect: 200 or Ollama welcome message

ollama list
# Expect: nomic-embed-text:v1.5 present (used for embeddings only; reasoning uses StreamLake kat-coder-pro-v2.5)

curl http://localhost:4000
# Expect: Langfuse UI loads (200)
```

### 1.2 Application Health

```powershell
# Kill stale app processes by port only (never by process name):
$pid8000 = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
if ($pid8000) { Stop-Process -Id $pid8000 -Force }
$pid8501 = (Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue).OwningProcess
if ($pid8501) { Stop-Process -Id $pid8501 -Force }

# Start backend (run in background):
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "src.main:app", "--reload", "--port", "8000" -PassThru

# Start frontend (run in background):
Start-Process -FilePath ".\.venv\Scripts\streamlit.exe" -ArgumentList "run", "ui/streamlit_app.py", "--server.port", "8501" -PassThru

# Wait ~10s for apps to start, then verify structural health (DB + graph compilation):
curl http://localhost:8000/api/v1/health/langgraph
# Expect: {"status": "healthy", "components": {"postgres": "ok", "graphs": {...}}}

# Then verify LLM connectivity:
curl http://localhost:8000/api/v1/health/llm
# Expect: {"status": "healthy", "provider": "streamlake", "model": "kat-coder-pro-v2.5", "latency_ms": ...}
# Note: default LLM_PROVIDER is streamlake (kat-coder-pro-v2.5); Ollama is used for embeddings only (nomic-embed-text:v1.5)
```

### 1.3 Database Migrations

```powershell
.\.venv\Scripts\python.exe -m alembic current
# Expect: matches the latest migration head (e.g., 20260727001_add_validation_confidence)
```

### 1.4 Fresh Test Accounts

Generate two fresh accounts — one for the primary UI browser flow and one for the agent-experience audit. They must not share an `application_id`.

```powershell
# Account A — for Subagent 1 (primary UI browser flow)
.\.venv\Scripts\python.exe scripts/generate_fresh_account.py
# Capture: emirates_id_A, profile_path_A

# Account B — for Subagent 2 (agent experience audit)
.\.venv\Scripts\python.exe scripts/generate_fresh_account.py
# Capture: emirates_id_B, profile_path_B
```

**Do not launch subagents until all preflight checks pass.**

## Phase 2: Tracker Document

Create `docs/live-testing-tracker.md` before launching any tests. Use this exact structure:

```markdown
# Live E2E Tracker — YYYY-MM-DD

## Session Info
| Field | Value |
|-------|-------|
| Start time | |
| Git branch / commit | |
| LLM provider | |
| Embedding model | |
| Account A (UI flow) — Emirates ID | |
| Account A — Profile path | |
| Account B (experience audit) — Emirates ID | |
| Account B — Profile path | |

## Test Matrix

| # | Scenario | Subagent | Phase | Expected | Actual | Status | Latency | Notes |
|---|----------|----------|-------|----------|--------|--------|---------|-------|

Status values: PASS, FAIL, BLOCKED, SKIP.

## Bugs Found

| ID | Severity | Step | Symptom | Root Cause | Fix | Commit |
|----|----------|------|---------|------------|-----|--------|

Severity: critical (blocks flow), major (degraded experience), minor (cosmetic).

## Fixes Applied

| Commit | What Changed | Files | Rationale |
|--------|-------------|-------|-----------|

## Agent Experience Scores

Rate each dimension 1-5 (1=poor, 5=excellent). Record specific message examples.

| Dimension | Score | Evidence (quote or paraphrase) |
|-----------|-------|-------------------------------|
| Helpfulness | | |
| Clarity | | |
| Tone | | |
| Progressive Disclosure | | |
| Error Messages | | |
| Decision Explanation | | |
| Enablement Personalization | | |
| **Overall** | avg | |

## Open Issues

| Issue | Impact | Next Step |
|-------|--------|-----------|
```

## Phase 3: Test Subagents

Launch the two test subagents in waves. **Test subagents are read-only — they detect and report failures but never touch code.** Do not launch a subagent until its wave dependencies have reported results.

### Wave Schedule

```
Wave 1:
  Subagent 1 — UI Browser Flow (uses emirates_id_A, profile_path_A)
  Drives the full 7-phase applicant journey through the Streamlit UI as a real user would.
  Records every UI observation, agent message, phase transition, and failure.

Wave 2:
  Subagent 2 — Agent Experience Audit (uses message logs from Subagent 1)
  Evaluates the conversational quality of every agent message produced during Wave 1.
  Scores each dimension, flags tone issues, and produces the experience report.
```

### Failure category vocabulary (used by all test subagents)

Every `failure_queue` entry must include a `category` field. The triage in Phase 4 routes by this field:

| Category value | Routes to fix subagent |
|----------------|----------------------|
| `ui` | 3B — UI & Frontend |
| `frontend` | 3B — UI & Frontend |
| `api` | 3A — API & Agent |
| `agent` | 3A — API & Agent |
| `agent-response` | 3A — API & Agent (prompt/tone issues) |
| `infrastructure` | 3C — Infrastructure & DB |
| `data` | 3C — Infrastructure & DB |

### Subagent 1 — UI Browser Flow (Primary Test Driver)

**Type:** `browser-use`

**Prompt to subagent:**

```
You are testing the Social Support Application as a real applicant would — through the Streamlit UI, from landing page to enablement. Your job is to experience the product end-to-end and report everything that breaks, confuses, or degrades the user experience.

Context:
- Frontend URL: http://localhost:8501
- Emirates ID: {emirates_id}
- Profile directory with documents: {profile_path}
- Required documents in profile: emirates_id_front.png, emirates_id_back.png, bank_statement.pdf, credit_report.pdf, resume.docx, assets_liabilities.xlsx, application_form.png
- This is a FRESH account. Drive the application forward from authentication through enablement exactly as a real applicant would.

IMPORTANT: You are a READ-ONLY tester. Do NOT attempt to fix any failures you encounter. Record every failure in detail and report it in the failure_queue. A separate fix subagent will handle repairs — and those fixes can touch ANY layer (UI, API, agent, infrastructure). Your job is to find the problems from the user's perspective.

Search Rule: If any UI component behaves unexpectedly (phase tracker not updating, decision card not rendering, file upload not triggering, chat messages not appearing, agent giving confusing responses), search for the current library API patterns before recording a diagnosis. Include the relevant library name (Streamlit, LangGraph, FastAPI) and the year (2026) in your search. Your search-informed diagnosis helps the fix subagent work faster. Do not attempt a fix yourself.

Navigate the UI as a real applicant would. For each action, record:
- What you did (clicked, typed, uploaded)
- What you observed on screen (text, component state, agent message)
- Whether the UI responded correctly
- Any errors, loading spinners that never complete, or missing components
- The full text of every agent message (so Subagent 2 can evaluate tone and clarity)

Steps:
1. Land on the landing page. Verify the Emirates ID input and "Start Application" button are visible and usable.
2. Enter the Emirates ID and click Start Application. Verify navigation to the chat page. Note any delays or errors.
3. In the chat, send your personal information including a support category (e.g., "I am divorced and seeking financial support"). Verify the agent responds with acknowledgment and either asks follow-up questions or advances to document collection. Record the agent's exact words.
4. Use the chat file attachment to upload all documents from the profile directory. Verify the phase tracker component updates to show documents were received. Note if any document is misclassified or rejected.
5. Wait for processing to complete. Watch the phase tracker transition through processing → review/decision. Record the total wait time and any agent messages during processing.
6. If in review, answer clarification questions in chat. Record the agent's questions and your responses. Verify phase eventually advances to "decision".
7. If in decision, verify a decision card is displayed with the outcome and eligibility score. Record the decision explanation word-for-word.
8. Continue to enablement. Verify personalized recommendations are shown. Record the recommendations.

Also test these edge scenarios naturally within the flow (do not break character as a real applicant):
- After auth + intake, stop and re-auth with the same Emirates ID. Verify session recovery works (same application_id, prior messages restored).
- Upload a wrong file type (a plain .txt file named "notes.txt"). Verify it is handled gracefully — either classified as "unknown" with a clear message, or rejected with a helpful error. Must NOT crash the server.
- Send a vague or incomplete message (e.g., "I need help" with no details). Verify the agent asks clarifying questions rather than crashing or giving a generic response.

Also note:
- Any UI elements that are broken, missing, or unresponsive
- Whether the phase tracker accurately reflects the current phase
- Whether decision cards are readable and well-formatted
- Whether the agent's tone feels appropriate for someone seeking government support
- Any console errors visible in the browser
- Total time from landing page to enablement

Return a structured report:
- Per-step: step, passed (bool), observation, failure_detail (if any), agent_message (full text)
- Edge scenarios: scenario, passed (bool), response_summary, graceful (bool)
- Screenshots of key states (landing, chat mid-flow, decision card, enablement)
- ALL agent messages displayed in the chat (for Subagent 2)
- failure_queue: list of {step_or_scenario, symptom, error_message, console_error (if any), category — one of: ui, frontend, api, agent, agent-response, infrastructure, data, search_results_summary}
- total_end_to_end_time_ms
```

### Subagent 2 — Agent Experience Audit

**Type:** `generalPurpose`

**Prerequisite:** Subagent 1 must complete so you have message logs to evaluate.

**Prompt to subagent:**

```
You are auditing the conversational quality of the Social Support Application agent.

Context:
This is a UAE government social support application. Applicants may be stressed, non-technical, and seeking financial assistance during difficult life circumstances (divorce, abandonment, unknown parentage, health disability). The agent's tone must be respectful, clear, and supportive — never dismissive, robotic, or condescending.

IMPORTANT: You are a READ-ONLY auditor. Do NOT attempt to fix any prompt or tone issues you identify. Record every issue in detail in the failure_queue. A separate fix subagent will handle prompt engineering repairs.

Search Rule: If you encounter agent messages that seem confusing, jargon-heavy, or tone-deaf and you are unsure whether this is a known issue or a prompt engineering problem, search for current best practices on conversational AI tone for government services, or LangGraph agent prompt design patterns (include year 2026). Your search-informed diagnosis helps the fix subagent work faster. Do not attempt a fix yourself.

You will receive the full message log from Subagent 1's UI browser flow test. Evaluate each dimension on a 1-5 scale:

1 = Poor: confusing, rude, or unhelpful
2 = Below average: partially helpful but unclear or incomplete
3 = Adequate: gets the job done but could be better
4 = Good: clear, helpful, appropriate tone
5 = Excellent: empathetic, precise, proactively helpful

Dimensions:
1. Helpfulness — Does the agent explain what is needed and why? Does it guide the applicant through each step?
2. Clarity — Are questions specific and unambiguous? Would a non-technical user understand what to do?
3. Tone — Is the agent respectful, empathetic, and appropriate for a government support context?
4. Progressive Disclosure — Does the agent ask one thing at a time rather than overwhelming the applicant with a long list of questions?
5. Error Messages — When something goes wrong, does the agent explain what happened and what to do next?
6. Decision Explanation — Is the rationale for the decision (approved/manual_review/soft_decline) clear and human-readable?
7. Enablement Personalization — Are the recommendations specific to the applicant's situation, or generic boilerplate?

For each dimension:
- Assign a score 1-5
- Quote 2-3 specific agent messages as evidence (one good example, one bad example if applicable)
- Write one sentence explaining the score

Also flag any messages that are:
- Confusing or ambiguous
- Rude, dismissive, or tone-deaf
- Missing actionable next steps
- Technically accurate but too jargon-heavy

Return a structured report:
- Per-dimension: dimension, score, good_example (quote), bad_example (quote or "none"), rationale (1 sentence)
- Overall average score
- Top 3 recommended improvements (specific, actionable)
- failure_queue: list of {dimension, symptom, bad_message (quote), suggested_improvement, category — always "agent-response" for prompt/tone issues, search_results_summary}
```

## Phase 4: Fix-and-Iterate Orchestration

After Subagents 1–2 report, the main agent runs the following orchestration loop. **Testing subagents never fix; fix subagents never test.** Context stays isolated at every step.

### 4.1 — Orchestration Loop

The main agent executes steps 1–8 in order. If step 8 triggers an iteration, return to step 1 (COLLECT) within this same Phase 4.

```
1. COLLECT
   - Gather failure_queue from Subagents 1 and 2 via the Task tool's return value.
   - Each test subagent returns a structured report with a failure_queue field.
   - If all queues are empty, skip to Phase 5 (success criteria).

2. DEDUPLICATE
   - Merge entries with the same root symptom (e.g., the same LangGraph interrupt bug reported as both a UI issue and an agent issue).
   - Keep one representative entry per unique root cause; note all subagents that observed it.

3. TRIAGE — route each unique failure by its category field:
   - category in {ui, frontend} → Fix Subagent 3B
   - category in {api, agent} → Fix Subagent 3A
   - category = agent-response → Fix Subagent 3A (prompt/tone issues)
   - category in {infrastructure, data} → Fix Subagent 3C

4. DISPATCH — launch fix subagents in parallel via the Task tool, one per non-empty category.
   Pass the deduplicated failure_queue entries as the {failure_queue_entries_from_triage} placeholder.

5. WAIT — for all fix subagents to complete and report.

6. RE-RUN — launch Subagent 1 (UI Browser Flow) again to verify fixes. Use the same emirates_id and profile_path from the original run.
   - If 3A fixed prompt/tone issues (agent-response), also launch Subagent 2 (Experience Audit) to verify chat messages improved.
   - If 3C fixed infrastructure, re-run Subagent 1 — infrastructure bugs affect the full user journey.

7. RECORD — for each fix:
   - Log the bug in docs/live-testing-tracker.md under "Bugs Found" (severity, step, symptom, root cause)
   - Log the fix under "Fixes Applied" (commit hash, files changed, rationale)

8. ITERATE — if re-runs surface new failures, return to step 1 (COLLECT) of this Phase 4.
   Abort if three consecutive fix-and-retest cycles fail on the same step.
```

### 4.2 — Fix Subagent 3A: API & Agent Bugs

**Type:** `generalPurpose`

**Prerequisite:** Main agent triage has assigned failures with category `api`, `agent`, or `agent-response` to this subagent.

**Prompt to subagent:**

```
You are fixing bugs in the Social Support Application that affect the end-user experience. These bugs were discovered through UI-driven testing but may live in any backend layer.

Context:
- Backend runs on http://localhost:8000 (FastAPI + LangGraph agents)
- Four-layer architecture: API routes → Services → Agents/Domain → Infrastructure
- LLM provider: StreamLake kat-coder-pro-v2.5 (reasoning), Ollama nomic-embed-text:v1.5 (embeddings)
- This subagent handles: API route bugs, service orchestration bugs, LangGraph graph wiring, agent prompts, domain logic, and prompt/tone issues (category agent-response)

You have been assigned the following failures from the test phase:

{failure_queue_entries_from_triage}

For EACH failure, follow this sequence:

1. SEARCH — Run a web search for the exact error or symptom + the relevant library name + year (2026). Libraries to search by symptom:
   - Phase transition bugs → LangGraph interrupt(), Command(resume=), conditional edge routing
   - Multipart / file upload → FastAPI UploadFile, multipart form handling
   - State leakage → LangGraph checkpoint, state_snapshot persistence
   - Agent behaviour / prompt issues → LangGraph agent prompt design, ReAct patterns, conversational AI tone for government services
   Check Langfuse traces at http://localhost:4000 for agent-side errors (often more detail than terminal logs).
   Only proceed to diagnosis after search results are reviewed.

2. DIAGNOSE — Identify the root cause. Trace the dependency chain from the failing symptom to the responsible module. Read the relevant source files before proposing a fix.

3. FIX — Make the minimal change needed. Follow the four-layer architecture:
   - API routes: thin handlers only (parse, call service, return)
   - Services: orchestration logic, agent invocation
   - Agents/Domain: graph wiring, prompts, domain logic
   - Infrastructure: DB models, repositories, external clients
   Never introduce circular imports.
   If adding logging: use structlog.get_logger(__name__), include duration_ms and relevant IDs, never log PII.
   For prompt/tone fixes (category agent-response): edit the relevant prompts.py file; keep changes respectful, clear, and supportive.

4. VERIFY — Run the relevant unit tests:
   .\.venv\Scripts\pytest.exe tests/unit/ -q -k <relevant_test_name>
   Only proceed when unit tests pass.

5. COMMIT — Commit the fix with a descriptive message:
   git add <changed_files>
   git commit -m "fix: <one-line description of what was fixed>"

Return a structured report for each failure:
- failure_id, root_cause, files_changed, fix_summary, unit_test_result, commit_hash
```

### 4.3 — Fix Subagent 3B: UI & Frontend Bugs

**Type:** `generalPurpose`

**Prerequisite:** Main agent triage has assigned failures with category `ui` or `frontend` to this subagent.

**Prompt to subagent:**

```
You are fixing UI and frontend bugs in the Social Support Application Streamlit frontend.

Context:
- Frontend runs on http://localhost:8501 (Streamlit)
- UI structure: streamlit_app.py (entry), app_pages/ (pages), components/ (reusables), fragments/ (@st.fragment sections)
- Key patterns: st.navigation with st.Page, @st.fragment for partial reruns, st.chat_message / st.chat_input for conversation

You have been assigned the following failures from the test phase:

{failure_queue_entries_from_triage}

For EACH failure, follow this sequence:

1. SEARCH — Run a web search for the exact error or symptom + "Streamlit" + year (2026). Search for:
   - Phase tracker not updating → st.fragment re-render, session_state mutation
   - Decision card not rendering → Streamlit component state, conditional rendering
   - File upload not triggering → st.chat_input accept_file, multipart handling
   - Chat messages not appearing → st.chat_message, session_state messages list
   - Navigation issues → st.navigation, st.Page API
   Prefer official Streamlit docs and GitHub issues over blog posts.

2. DIAGNOSE — Identify the root cause. Read the relevant UI source files before proposing a fix.

3. FIX — Make the minimal change needed. Follow Streamlit conventions:
   - Use @st.fragment for expensive sections that need partial reruns
   - Use st.session_state for cross-rerun state (identity_number, applicant_info, uploaded_documents, current_phase)
   - Keep components pure and importable from components/
   - Never mutate session_state lists in-place — reassign with new list
   If adding logging: use structlog.get_logger(__name__), include duration_ms, never log PII.

4. VERIFY — Identify and run relevant unit tests:
   - Search for test files matching the affected component: tests/unit/ui/ or tests/unit/components/
   - Run: .\.venv\Scripts\pytest.exe tests/unit/ -q -k <test_file_prefix>
   - If no matching test exists, skip this step but note it in your report.
   Only proceed when unit tests pass (or no tests exist).

5. COMMIT — Commit the fix with a descriptive message:
   git add <changed_files>
   git commit -m "fix(ui): <one-line description of what was fixed>"

Return a structured report for each failure:
- failure_id, root_cause, files_changed, fix_summary, unit_test_result, commit_hash
```

### 4.4 — Fix Subagent 3C: Infrastructure & Database Bugs

**Type:** `generalPurpose`

**Prerequisite:** Main agent triage has assigned failures with category `infrastructure` or `data` to this subagent.

**Prompt to subagent:**

```
You are fixing infrastructure, database, and Docker-level bugs in the Social Support Application.

Context:
- PostgreSQL on localhost:5432 (container: xd_postgres)
- Neo4j on localhost:7687 (container: xd_neo4j)
- Qdrant on localhost:6333 (container: xd_qdrant)
- Langfuse stack: web:4000, worker:3030, postgres:5433, clickhouse:8123, redis:6379, minio:9090
- Ollama on localhost:11434 (embeddings: nomic-embed-text:v1.5)
- Migrations managed by Alembic (asyncpg + SQLAlchemy)

You have been assigned the following failures from the test phase:

{failure_queue_entries_from_triage}

For EACH failure, follow this sequence:

1. SEARCH — Run a web search for the exact error or symptom + the relevant library/service name + year (2026). Search for:
   - Connection pool errors → asyncpg connection pool, SQLAlchemy async session
   - Migration conflicts → Alembic migration conflict resolution, stamp_head
   - Container crashes → Docker compose resource limits, healthcheck failures
   - Neo4j query failures → Cypher syntax, relationship constraints
   - Qdrant ingestion errors → Qdrant REST API, vector dimension mismatch
   - Langfuse worker unreachable → Docker compose service dependencies
   Prefer official docs and GitHub issues.

2. DIAGNOSE — Identify the root cause. Check container logs, database state, and migration history before proposing a fix:
   - docker compose logs --tail=100 <service>
   - .\.venv\Scripts\python.exe -m alembic current
   - docker compose ps

3. FIX — Make the minimal change needed. Follow these rules:
   - DB schema changes: modify the SQLAlchemy model first, then generate a migration with alembic revision --autogenerate -m "description"
   - Docker issues: adjust docker-compose.yml or service healthchecks — never use docker compose down -v (data loss)
   - Connection issues: check .env variables match container ports
   - Never kill infrastructure processes by name — use docker compose restart <service> or port-based killing for app processes only
   If adding logging: use structlog.get_logger(__name__), include duration_ms and relevant IDs, never log PII.

4. VERIFY — Identify and run relevant unit tests:
   - Search for test files matching the affected infrastructure: tests/unit/infrastructure/ or tests/unit/db/
   - Run: .\.venv\Scripts\pytest.exe tests/unit/ -q -k <test_file_prefix>
   - If no matching test exists, skip this step but note it in your report.
   Only proceed when unit tests pass (or no tests exist).

5. COMMIT — Commit the fix with a descriptive message:
   git add <changed_files>
   git commit -m "fix(infra): <one-line description of what was fixed>"

Return a structured report for each failure:
- failure_id, root_cause, files_changed, fix_summary, unit_test_result, commit_hash
```

## Phase 5: Success Criteria

All of the following must be true before declaring done:

- [ ] **Preflight** — All infrastructure, app, and DB checks passed.
- [ ] **UI Browser Flow** — All 8 steps completed in the browser with no broken or unresponsive UI elements. A real applicant could complete the full journey without assistance.
- [ ] **Edge Scenarios** — Session recovery, wrong file type, and vague message scenarios all handled gracefully (no 500s, no crashes, appropriate responses).
- [ ] **Agent Experience** — Overall score >= 3.5/5. No dimension scored below 2. No rude or confusing messages flagged.
- [ ] **Decision Rendered** — Decision card displays with outcome and eligibility score, visible in the UI.
- [ ] **Enablement** — Personalized recommendations displayed and contextually relevant.
- [ ] **PII Safety** — No Emirates ID numbers, names, or phone numbers appear in backend logs.
- [ ] **Tracker Complete** — All sections of `docs/live-testing-tracker.md` filled in.
- [ ] **Commits** — All fixes committed with descriptive messages. No uncommitted changes left behind.

## Phase 6: Closeout

Before ending the session:

1. **Update tracker** — Fill in any remaining empty sections. Ensure the test matrix has a final status for every row.
2. **Update `docs/solution-summary.md`** — If any bug revealed an architectural issue (e.g., agent graph wiring, service layer gap, missing infrastructure integration), add a note to the "Future improvements" or "Known limitations" section.
3. **Update `docs/e2e-testing-tracker.md`** — If this session fixed bugs or validated new flows, append a row to the existing E2E testing tracker with date, scope, and outcome.
4. **Leave infrastructure running** — Do not stop Docker containers or app processes. The user may want to inspect the running state.
5. **Report** — Summarize for the user:
   - Number of tests run, passed, failed
   - Number of bugs found and fixed
   - Agent experience overall score
   - Any open issues that need attention
   - Commit range covering the fixes

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Luhn fails on login | Invalid Emirates ID format | Use `scripts/generate_fresh_account.py` or `src/utils/emirates_id.py` for checksum |
| Docs classified as `unknown` | Filename lacks type hint | Name files `bank_statement.pdf`, `credit_report.pdf`, `resume.docx`, `assets_liabilities.xlsx`, `application_form.png`, `emirates_id_front.png`, `emirates_id_back.png` |
| `.xlsx` not recognized | Extension not in classifier | Add `assets_liabilities` to document classifier rules |
| Phase stuck at processing | LLM provider unhealthy | `GET /health/llm`; check Ollama (`curl localhost:11434`) and StreamLake connectivity |
| Phase stuck at intake | No `support_category` in message | Include divorced/abandoned/unknown_parentage/health_disability in intake text |
| Interrupt not resuming | `_pending_interrupt` not cleared | Verify next chat request body includes the answer text; inspect Langfuse trace for graph state |
| Session recovery fails | `state_snapshot` column missing | Run `alembic upgrade head`; verify migration `20260726001_add_state_snapshot` applied |
| Port 8000 in use | Stale uvicorn process | `$pid = (Get-NetTCPConnection -LocalPort 8000).OwningProcess; Stop-Process -Id $pid -Force` |
| Port 8501 in use | Stale Streamlit process | `$pid = (Get-NetTCPConnection -LocalPort 8501).OwningProcess; Stop-Process -Id $pid -Force` |
| Docker container exited | Resource limit or crash | `docker compose logs --tail=100 <service>`; then `docker compose up -d` |
| Langfuse unreachable | Worker not started | `docker compose restart xd_langfuse_worker` |
| Graph compilation fails | Missing dependency or circular import | `GET /health/langgraph` to identify which graph fails; check imports in agent `graph.py` |
| Streaming endpoint hangs | SSE not configured | Verify `chat/stream` endpoint accepts `text/event-stream` response; check `run_streaming()` in `agent_runner.py` |
| `validation_confidence` column missing | Migration not applied | Run `alembic upgrade head`; verify migration `20260727001_add_validation_confidence` applied |
