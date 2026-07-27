# Live E2E Tracker — 2026-07-27

## Session Info
| Field | Value |
|-------|-------|
| Start time | 2026-07-27 21:41 PM (UTC+4) |
| Git branch | (check git status) |
| LLM provider | streamlake (kat-coder-pro-v2.5) |
| Embedding model | nomic-embed-text:v1.5 |
| Fresh account seed | 32801 |
| Emirates ID | 784-2001-0097190-0 |
| Profile path | data/fresh_accounts/applicant_32801/ |

## Test Matrix

| # | Scenario | Subagent | Phase | Expected | Actual | Status | Latency | Notes |
|---|----------|----------|-------|----------|--------|--------|---------|-------|
| 1 | API Auth - Login | 1 | auth | 200, application_id | | | | |
| 2 | API Intake - Personal details | 1 | intake | Phase advances to document_collection | | | | |
| 3 | API Document Upload - All 7 docs | 1 | document_collection | All classified correctly | | | | |
| 4 | API Processing | 1 | processing | Phase advances beyond processing | | | | |
| 5 | API Review - Clarifications | 1 | review | Phase advances to decision | | | | |
| 6 | API Decision | 1 | decision | Decision in (approved, manual_review, soft_decline) | | | | |
| 7 | API Enablement | 1 | enablement | Personalized recommendations | | | | |
| 8 | UI Landing page | 2 | auth | Input + button visible | | | | |
| 9 | UI Chat flow | 2 | intake+doc_collection | Agent responds, phase updates | | | | |
| 10 | UI Document upload | 2 | document_collection | Upload triggers, phase tracker updates | | | | |
| 11 | UI Processing display | 2 | processing | Phase tracker transitions | | | | |
| 12 | UI Decision card | 2 | decision | Decision card renders | | | | |
| 13 | UI Enablement display | 2 | enablement | Recommendations shown | | | | |
| 14 | Edge Invalid Emirates ID | 3 | auth | 400 error | | | | |
| 15 | Edge Partial intake | 3 | intake | Interrupt for missing fields | | | | |
| 16 | Edge Missing documents | 3 | document_collection | Lists remaining docs | | | | |
| 17 | Edge Session recovery | 3 | recovery | State restored | | | | |
| 18 | Edge Wrong file type | 3 | document_collection | Graceful handling | | | | |
| 19 | Edge Concurrent apps | 3 | concurrency | State isolated | | | | |
| 20 | Agent Experience - Helpfulness | 4 | all | Score 1-5 | | | | |
| 21 | Agent Experience - Clarity | 4 | all | Score 1-5 | | | | |
| 22 | Agent Experience - Tone | 4 | all | Score 1-5 | | | | |

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
