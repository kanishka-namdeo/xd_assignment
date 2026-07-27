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
5. Fresh account ready   → data/fresh_accounts/            (or run generate-account)
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
