# Agent Evaluation Framework

## Purpose
Four-layer evaluation framework for measuring agent tool correctness and accuracy. Distinct from unit tests: evaluates tools against real documents, schema contracts, and ground-truth datasets — not just code correctness.

## Ownership
- Primary: Development Team
- Review Required: Evaluation changes require review

## Local Contracts

### Four-Layer Framework

| Layer | Directory | Purpose |
|-------|-----------|---------|
| 1 — Audit | `evals/audit/` | Enumerate all 19 agent tools, map unit test coverage, flag gaps |
| 2 — Golden Dataset | `evals/golden/` | Run tools against real synthetic profiles with ground-truth annotations |
| 3 — Schema Contracts | `evals/contracts/` | Pydantic contract conformance + error handling validation |
| 4 — Live Integration | `tests/integration/` | Full agent graph with real LLM calls, Langfuse trace validation |

### Layer 1 — Tool Audit
- `test_tool_audit.py`: Enumerates 19 tools across 4 agents (extraction, validation, eligibility, decision)
- Produces `evals/audit/report.json` with `tool_inventory`, `coverage_map`, `gaps`

### Layer 2 — Golden Dataset Validation
- Uses `data/test_applicants/profiles.json` with 3 cross-document-consistent profiles:
  - `divorced_employed_good_credit` → expected: approved
  - `abandoned_unemployed_poor_credit` → expected: manual_review
  - `unknown_parentage_self_employed_borderline` → expected: soft_decline
- Test files: `test_extraction_tools.py`, `test_validation_tools.py`, `test_eligibility_tools.py`, `test_decision_tools.py`
- Shared fixtures in `evals/conftest.py`: `golden_profiles`, `approved_profile`, `manual_review_profile`, `soft_decline_profile`

### Layer 3 — Schema Contracts
- `schemas.py`: Pydantic contract definitions for all 19 tool outputs
- `test_contracts.py`: Parametrized conformance tests — catches schema drift
- `test_error_handling.py`: Malformed input tests — all tools must return error dict, not raise

### Layer 4 — Live Integration
- `tests/integration/test_live_integration.py`: Full graph buildability + live LLM tests
- Live tests marked with `@pytest.mark.live` — skipped by default, require running infrastructure

### Evaluation Standards
- All 19 tools must have contract definitions
- All tools must gracefully handle malformed input
- Golden dataset tests validate against real document data
- Live integration tests require infrastructure (PostgreSQL, Neo4j, Qdrant, Ollama/StreamLake)

### Additional Evaluation Scripts
The following evaluation scripts exist at the `evals/` root level but are not part of the four-layer framework:
- `evals/test_eligibility_scoring.py` — Eligibility scoring validation
- `evals/test_extraction_accuracy.py` — Extraction accuracy validation
- `evals/test_validation_rules.py` — Validation rules validation
- `evals/live_e2e_report.json` — Runtime artifact from live E2E testing (not a test file)

## Work Guidance

### Running Evaluations
```bash
# All layers (non-live)
.\.venv\Scripts\pytest.exe evals/ -v

# Specific layer
.\.venv\Scripts\pytest.exe evals/audit/ -v
.\.venv\Scripts\pytest.exe evals/golden/ -v
.\.venv\Scripts\pytest.exe evals/contracts/ -v

# Live integration (requires infrastructure + LLM)
.\.venv\Scripts\pytest.exe tests/integration/ -v -m live
```

### Adding a New Tool Contract
1. Add contract class in `evals/contracts/schemas.py` extending the appropriate base
2. Add entry to `CONTRACT_MAP`
3. Add to `TOOLS_UNDER_TEST` in `test_contracts.py`
4. Add malformed inputs to `MALFORMED_INPUTS` in `test_error_handling.py`

### Interpreting Results
- Contract test failures indicate schema drift — a tool changed its output shape
- Error handling failures indicate a tool raises on bad input instead of returning an error dict
- Golden dataset failures indicate extraction/validation/decision quality regression

## Verification
- Evaluation suite runs on CI after each merge
- 50+ tests across all 4 layers
- Regression alerts if contract conformance drops below 100%

## Child DOX Index
None - single-level structure.
