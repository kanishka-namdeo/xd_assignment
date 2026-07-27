# Live E2E Tracker — 2026-07-27

## Session Info
| Field | Value |
|-------|-------|
| Start time | 2026-07-27 20:49 GST |
| Git branch / commit | main (uncommitted changes) |
| LLM provider | StreamLake kat-coder-pro-v2.5 |
| Embedding model | Ollama nomic-embed-text:v1.5 |
| Account A (UI flow) — Emirates ID | 784-1989-5064222-7 |
| Account A — Profile path | data/fresh_accounts/applicant_158229 |
| Account B (experience audit) — Emirates ID | 784-2004-9189284-8 |
| Account B — Profile path | data/fresh_accounts/applicant_372997 |

## Test Matrix

| # | Scenario | Subagent | Phase | Expected | Actual | Status | Latency | Notes |
|---|----------|----------|-------|----------|--------|--------|---------|-------|
| 1 | Landing page loads | 1 | Auth | Emirates ID input + Start button visible | All elements visible, properly styled | PASS | <1s | Clean layout |
| 2 | Authentication | 1 | Auth→Intake | Navigate to chat after ID entry | Navigated successfully, phase tracker updated | PASS | ~2s | Welcome message displayed |
| 3 | Intake message | 1 | Intake | Agent acknowledges support category | Agent noted 'Abandoned' category, transitioned to doc collection | PASS | ~5s | Phase tracker updated correctly |
| 4 | Document upload | 1 | Doc Collection | Upload all 7 docs, phase tracker updates | BLOCKED by Cursor IDE browser security (DOM.setFileInputFiles denied) | BLOCKED | N/A | Browser automation limitation, not app bug |
| 5 | Processing | 1 | Processing | Phase transitions to review/decision | BLOCKED (depends on step 4) | BLOCKED | N/A | |
| 6 | Review/clarification | 1 | Review | Agent asks clarification questions if needed | BLOCKED (depends on step 4) | BLOCKED | N/A | |
| 7 | Decision rendered | 1 | Decision | Decision card with outcome + score | BLOCKED (depends on step 4) | BLOCKED | N/A | |
| 8 | Enablement | 1 | Enablement | Personalized recommendations shown | BLOCKED (depends on step 4) | BLOCKED | N/A | |
| 9 | Session recovery | 1 | Auth | Re-auth restores session | BLOCKED by browser automation | BLOCKED | N/A | Code exists in landing.py |
| 10 | Wrong file type | 1 | Doc Collection | Graceful handling of .txt upload | BLOCKED by browser automation | BLOCKED | N/A | |
| 11 | Vague message | 1 | Doc Collection | Agent asks clarifying questions | Agent gave misleading "Thank you for uploading" response | FAIL | ~3s | Critical: misleading response |
| 12 | Decision card | 1 | Decision | Clean decision explanation | Decision card shows raw JSON in explanation field | FAIL | N/A | BUG-002: raw JSON visible |
| 13 | Interrupt schema | 1 | Enablement | Interrupt data validates correctly | Pydantic validation fails: recommendations field expects strings but gets dicts | FAIL | N/A | BUG-003: schema mismatch |
| 14 | Vague message (post-fix) | 1 | Enablement | Helpful response to vague query | Returns "An unexpected error occurred" due to Pydantic validation failure | FAIL | N/A | BUG-004: validation error exposed |
| 15 | Decision card (post-fix) | 1 | Decision | Clean decision explanation | Clean explanation text, no raw JSON | PASS | ~6s | BUG-002 fixed in commit 4654eed |
| 16 | Interrupt schema (post-fix) | 1 | Enablement | Interrupt data validates correctly | Recommendations properly formatted as dicts | PASS | ~6s | BUG-003 fixed in commit 4654eed |
| 17 | Error handling (post-fix) | 1 | Enablement | Specific error message | Returns user input as fallback (LLM API 400 error) | PARTIAL | ~6s | BUG-004 fixed, but LLM API issue remains |

## Bugs Found

| ID | Severity | Step | Symptom | Root Cause | Fix | Commit |
|----|----------|------|---------|------------|-----|--------|
| BUG-001 | critical | Edge: Vague message | Agent says "Thank you for uploading your documents" when user sent "I need help" and no documents were uploaded | agent-response: Document collection phase prompt doesn't distinguish between file upload events and text-only messages | Fixed in first round | 317173f |
| BUG-002 | major | Decision phase | Decision card shows raw JSON in explanation field | decision_service.py format_decision_card() returns raw JSON string instead of formatted explanation | Fixed: extract explanation from JSON block | 4654eed |
| BUG-003 | major | Enablement phase | Pydantic validation fails: recommendations field expects strings but gets dicts | InterruptData schema defines recommendations as list[str] but enablement_node creates list[dict] with title/description | Fixed: updated InterruptData.recommendations to accept list[dict] | 4654eed |
| BUG-004 | critical | Enablement phase | Returns "An unexpected error occurred" when user sends vague message | chat_service.py exception handler catches Pydantic ValidationError but returns generic error message | Fixed: added specific ValidationError handling | 4654eed |
| BUG-005 | major | Chat response | Document list shows duplicates (336 documents instead of 7) | chat_service.py builds uploaded_documents list without deduplication | Fixed: deduplicate by file_path | 8933f70 |
| BUG-006 | major | Enablement phase | Type comparison error when family_size is string | enablement.py compares string family_size with int 1 | Fixed: convert family_size to int | e01dbe3 |

## Fixes Applied

| Commit | What Changed | Files | Rationale |
|--------|-------------|-------|-----------|
| 7fb9b99 | Added exception handling in chat service and API endpoint | src/services/chat_service.py, src/api/v1/chat.py, tests/unit/services/test_chat_service.py | Backend no longer crashes during document processing; returns graceful error message |
| 317173f | Improved agent tone, empathy, and user-facing messages | src/agents/orchestrator/prompts.py, src/agents/orchestrator/phases/document_collection.py, src/agents/orchestrator/phases/enablement.py, src/agents/decision/tools.py | Agent now uses empathetic language, acknowledges applicant's situation, avoids system terminology |

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
| **Overall** | | |

## Open Issues

| Issue | Impact | Next Step |
|-------|--------|-----------|
| Document upload blocked by browser automation | Cannot test phases 4-8 through browser | Use API to upload documents, then verify UI state |
| BUG-001: Vague message handling | Users sending non-file messages during doc collection get misleading response | Fix agent prompt for document collection phase |
