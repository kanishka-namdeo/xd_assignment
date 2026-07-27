# Agent Tools Evaluation Framework — Design Specification

## Executive Summary

Build a four-layer evaluation framework in `evals/` that validates whether all 19 agent tools across 4 agents (extraction, validation, eligibility, decision) are working correctly — both in isolation (functional correctness) and when wired into the full LangGraph agent graph (integration correctness).

The framework uses the existing `data/test_applicants/` synthetic profiles as a golden dataset with ground-truth annotations, Pydantic contracts for schema conformance, and Langfuse traces for live integration validation.

## Architecture

Four layers, independently runnable, progressively more comprehensive:

```
evals/
├── audit/                          # Layer 1: Tool Audit
│   └── test_tool_audit.py          # Enumerate all tools, map coverage, flag gaps
├── golden/                         # Layer 2: Golden Dataset Validation
│   ├── conftest.py                 # Load test_applicants profiles + ground truth
│   ├── test_extraction_tools.py    # Run extraction tools against real documents
│   ├── test_validation_tools.py    # Run validation tools against extracted data
│   ├── test_eligibility_tools.py   # Run eligibility tools against features
│   └── test_decision_tools.py      # Run decision tools against scores
├── contracts/                      # Layer 3: Schema Contract Tests
│   ├── schemas.py                  # Pydantic contracts for each tool's I/O
│   ├── test_contracts.py           # Validate tool outputs against contracts
│   └── test_error_handling.py      # Malformed inputs, missing files, failures
└── integration/                    # Layer 4: Live Integration
    └── test_live_agent_graph.py    # Full graph with real LLM, validate via Langfuse
```

## Tool Inventory

19 tools across 4 agents:

| Agent | Tool | Purpose |
|-------|------|---------|
| extraction | `ocr_extract_tool` | Extract text from images using PaddleOCR |
| extraction | `pdf_parse_tool` | Parse digital PDF using PyMuPDF4LLM |
| extraction | `table_extract_tool` | Extract tables from PDF using Camelot |
| extraction | `resume_parse_tool` | Parse resume/CV using SmartResume |
| extraction | `xlsx_extract_tool` | Extract data from Excel using openpyxl |
| extraction | `confidence_score_tool` | Compute field-level confidence scores |
| validation | `per_document_validation_tool` | Validate single document for internal consistency |
| validation | `cross_document_compare_tool` | Compare fields across multiple documents |
| validation | `discrepancy_classify_tool` | Classify discrepancy as OCR error vs real |
| validation | `applicant_clarify_tool` | Generate clarification question for applicant |
| validation | `validation_confidence_tool` | Compute overall validation confidence |
| eligibility | `ml_model_predict_tool` | Predict eligibility via ML model or rule-based fallback |
| eligibility | `feature_importance_tool` | Compute feature importance via SHAP or rule-based |
| eligibility | `adjust_factor_weighting_tool` | Adjust score based on applicant context |
| eligibility | `eligibility_explanation_tool` | Generate human-readable eligibility explanation |
| decision | `decision_logic_tool` | Apply decision rules for final recommendation |
| decision | `decision_explanation_tool` | Generate human-readable decision explanation |
| decision | `enablement_recommendation_tool` | Generate personalized enablement recommendations |
| decision | `decision_formatting_tool` | Format final decision for chat display |

## Layer 1 — Tool Audit

**File:** `evals/audit/test_tool_audit.py`

Programmatically enumerates all 19 tools, cross-references with existing unit test coverage in `tests/unit/agents/`, and produces a gap report.

**Output:**
- Tool inventory — all 19 tools enumerated by agent
- Coverage map — which tools have unit tests, which don't
- Gap flags — tools with zero tests, tools with only happy-path tests, tools missing error-case coverage
- Artifact: `evals/audit/report.json`

## Layer 2 — Golden Dataset Validation

**Directory:** `evals/golden/`

Uses the 3 existing `data/test_applicants/` profiles as ground truth.

### Golden Profiles

| Profile | Expected Decision | Key Ground Truth |
|---------|------------------|-----------------|
| `divorced_employed_good_credit` | `approved` | identity_number, income=12000, credit_score=720 |
| `abandoned_unemployed_poor_credit` | `manual_review` | identity_number, income=3500, credit_score=520 |
| `unknown_parentage_self_employed_borderline` | `soft_decline` | identity_number, income=8000, credit_score=640 |

### Profile Schema Extension

Each `profile.json` is extended with tool-level expected outputs:

```json
{
  "applicant": {
    "identity_number": "784-1990-1234567-6",
    "full_name_en": "Ahmed Mohammed Ali",
    "support_category": "divorced",
    "monthly_salary": 12000
  },
  "expected_extraction": {
    "emirates_id": {
      "identity_number": "784-1990-1234567-6",
      "full_name_en": "Ahmed Mohammed Ali"
    },
    "bank_statement": {
      "monthly_income": 12000,
      "account_balance": 45000
    }
  },
  "expected_validation": {
    "overall_status": "valid",
    "discrepancies": []
  },
  "expected_decision": "approved"
}
```

### Tests

- **Extraction** — run each extraction tool on the profile's actual documents, assert extracted fields match ground truth within tolerance
- **Validation** — run validation tools on extracted data, assert status matches expected
- **Eligibility** — run ML/rule-based prediction, assert predicted class aligns with expected decision
- **Decision** — run decision tools, assert final decision matches expected

## Layer 3 — Schema Contracts

**Directory:** `evals/contracts/`

Pydantic models define the contract for each tool's output.

### Contract Definition

```python
class ToolOutputContract(BaseModel):
    tool_name: str
    input_schema: dict
    output_schema: dict
    error_schema: dict
    latency_bound_ms: float = 5000.0
```

### Tests

- **Contract conformance** — every tool output validated against its Pydantic contract
- **Schema drift detection** — if a tool adds/removes a field, the contract test fails
- **Error handling** — inject malformed inputs (missing files, wrong types, empty dicts), assert tools return error schema (not raise exceptions)
- **Latency bounds** — tools must complete within defined bounds (configurable per tool)

## Layer 4 — Live Integration

**Directory:** `evals/integration/`

Runs the full agent graph with real LLM calls against the golden dataset.

### Test Flow

1. Load a golden profile
2. Run the full agent graph with real LLM
3. Query Langfuse traces for tool calls
4. Assert: correct tools were called in correct order
5. Assert: tool outputs were consumed by downstream nodes
6. Assert: final decision matches expected

### Validation via Langfuse Traces

- Tool call sequence: extraction → validation → eligibility → decision
- No tool raised unhandled exceptions
- Final decision matches golden profile's expected decision

### Marking

Tests are marked with `@pytest.mark.live` so they can be run selectively:
```bash
pytest evals/integration/ -m live
```

## Success Criteria

| Criterion | Target | How Measured |
|-----------|--------|--------------|
| Tool audit coverage | 100% of 19 tools enumerated, gaps flagged | `evals/audit/` report |
| Golden dataset pass rate | All 3 profiles produce expected decisions | `evals/golden/` assertions |
| Schema contract conformance | All tool outputs validate against contracts | `evals/contracts/test_contracts.py` |
| Error handling | All tools return error schema (no unhandled exceptions) on malformed input | `evals/contracts/test_error_handling.py` |
| Live integration | Full graph completes, decision matches expected, no tool errors | `evals/integration/test_live_agent_graph.py` |

## Execution Plan

1. Extend `profile.json` in each test applicant directory with tool-level ground truth annotations
2. Build `evals/audit/` — tool inventory, coverage map, gap report
3. Build `evals/golden/` — run tools against real documents, validate against ground truth
4. Build `evals/contracts/` — Pydantic contracts, conformance tests, error handling tests
5. Build `evals/integration/` — live graph execution with Langfuse trace validation
6. Run full suite — `pytest evals/ -v`, fix any failures, document results

## Risk Notes

- **Golden dataset annotations** — extending `profile.json` with tool-level expectations requires careful annotation; incorrect ground truth will cause false failures
- **Real document extraction** — extraction tools depend on OCR/PDF libraries that may produce slightly different results across runs; tolerances need to be calibrated
- **Live integration cost** — real LLM calls are slow and token-expensive; this layer should be opt-in (e.g., `pytest evals/integration/ -m live`)
- **Langfuse dependency** — integration tests require Langfuse to be running; need graceful degradation if unavailable
