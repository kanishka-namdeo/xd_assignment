# API-Only Agent Skill Design

## Executive Summary

A Cursor Agent Skill that enables the agent to interact with the Social Support Application entirely through its FastAPI backend — no Streamlit UI required. The skill pairs a concise SKILL.md (workflow guidance, troubleshooting) with a single executable Python script (`scripts/api_client.py`) that wraps all API operations as async subcommands.

**Use cases:**
- Automated testing & validation — run full 7-phase flows, catch regressions
- Demo & smoke testing — quickly exercise the app before a meeting
- Data generation & exploration — generate accounts, submit applications, collect decisions

## Architecture

### Skill Structure

```
.cursor/skills/api-only-interaction/
├── SKILL.md              # Workflow guidance, command reference, troubleshooting
├── reference.md          # Full API reference (endpoints, schemas, error codes)
└── examples.md           # Common scenarios (happy path, session recovery, edge cases)
```

### Script Structure

```
scripts/api_client.py
```

A single async script using `httpx`. Subcommands map to application phases:

| Subcommand | Purpose |
|---|---|
| `generate-account` | Generate fresh test account (wraps `generate_fresh_account.py`) |
| `login` | Auth with Emirates ID → returns `application_id` |
| `intake` | Send personal details, loop through interrupts until `document_collection` |
| `upload-docs` | Upload all documents from a profile directory |
| `process` | Trigger processing, poll until phase exits `processing` |
| `review` | Answer clarification questions, loop until `decision` phase |
| `decision` | Poll until decision rendered, print outcome + score |
| `enablement` | Query enablement recommendations |
| `full-flow` | Run complete 7-phase flow end-to-end |
| `status` | Get current application status, phase, decision |
| `eligibility` | Compute and print eligibility score + explanation |

### Data Flow

```
Agent invokes skill
  → SKILL.md provides workflow guidance
  → Agent runs: .\.venv\Scripts\python.exe scripts/api_client.py <subcommand> [args]
  → Script makes HTTP requests to FastAPI backend
  → Script prints structured JSON to stdout
  → Agent parses output, reports results, handles errors
```

## Subcommand Details

### `generate-account [--seed N] [--output-dir PATH]`

Subprocesses `scripts/generate_fresh_account.py` with the given seed and output directory. Parses the "FRESH ACCOUNT READY" block from stdout to extract the Emirates ID and profile path. Prints both as JSON.

### `login --emirates-id <eid>`

```
POST /api/v1/auth/login
Body: {"emirates_id": "<eid>"}
Output: {"application_id": "...", "applicant_id": "...", "current_phase": "...", "is_new_applicant": true/false}
```

### `intake --app-id <id> --profile-dir <path> [--max-loops N]`

Reads `profile.json` from the profile directory, constructs a comprehensive intake message with all required fields (including `support_category`), sends it via chat, and loops through any interrupts until the phase advances to `document_collection`.

### `upload-docs --app-id <id> --profile-dir <path>`

Discovers all document files in the profile directory, uploads them via multipart form-data to the chat endpoint. Returns the list of classified documents.

### `process --app-id <id> [--timeout-seconds N]`

Sends a "proceed" message to trigger processing, then polls `GET /applications/{id}` until the phase exits `processing`. Returns the final phase and elapsed time.

### `review --app-id <id> [--max-loops N]`

If in `review` phase, answers any clarification questions from interrupts and loops until the phase advances to `decision`.

### `decision --app-id <id> [--timeout-seconds N]`

Polls until `decision` is non-null. Prints decision, eligibility score, and explanation.

### `enablement --app-id <id>`

Sends an enablement query and prints the recommendations.

### `full-flow --emirates-id <eid> --profile-dir <path> [--seed N]`

Orchestrates the complete flow: `login` → `intake` → `upload-docs` → `process` → `review` → `decision` → `enablement`. Handles interrupts automatically. Prints a summary at the end.

### `status --app-id <id>`

Prints current application status: phase, decision, eligibility score, document count.

### `eligibility --app-id <id>`

Calls `POST /eligibility/{id}/compute` and `GET /eligibility/{id}/explanation`. Prints score, factors, and human-readable explanation.

## Output Format

All subcommands print structured JSON to stdout:

```json
{
  "command": "login",
  "success": true,
  "data": {
    "application_id": "uuid",
    "current_phase": "intake"
  },
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

A `--verbose` flag prints human-readable progress logs to stderr.

## SKILL.md Content Outline

1. **Purpose** — what the skill does, when to use it
2. **Preflight Checklist** — 7 checks before any interaction (Docker, Ollama, LLM health, migrations, fresh account, .env, ports)
3. **Command Reference** — each subcommand with arguments, examples, expected output
4. **7-Phase Workflow** — how to drive the full flow, handling interrupts, session recovery
5. **Troubleshooting** — symptom → diagnosis → fix table
6. **Output Interpretation** — decision thresholds, phase meanings, error codes

## Error Handling

- Script catches HTTP errors and prints structured error JSON
- Interrupts are handled automatically by `intake` and `review` subcommands
- Timeout on `process` and `decision` subcommands (default 90s and 60s respectively)
- All errors include the command name and latency for debugging

## Testing

- Each subcommand can be tested independently
- `full-flow` tested against all 3 golden profiles (approved, manual_review, soft_decline)
- Script has no side effects beyond what the API itself does
