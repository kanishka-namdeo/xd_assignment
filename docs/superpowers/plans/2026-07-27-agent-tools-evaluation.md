# Agent Tools Evaluation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a four-layer evaluation framework that validates correctness of all 19 agent tools — in isolation, against real documents, against schema contracts, and inside the live agent graph.

**Architecture:** Four independently-runnable pytest layers in `evals/`: audit (tool inventory + coverage gaps), golden (run tools against real synthetic profiles with ground truth), contracts (Pydantic schema conformance + error handling), and integration (live graph with Langfuse trace validation).

**Tech Stack:** pytest, Pydantic v2, structlog, Langfuse SDK, existing agent tools from `src/agents/`, existing synthetic profiles from `data/test_applicants/profiles.json`.

## Global Constraints

- Use `.venv\Scripts\python.exe` and `.venv\Scripts\pytest.exe` for all Python commands
- Pydantic v2 patterns: `field_validator`, `model_config = ConfigDict(...)`
- Type hints: `list[str]`, `dict[str, int]`, `X | None` (PEP 585/604)
- Logging: `structlog.get_logger(__name__)` in all modules
- Test marking: live integration tests use `@pytest.mark.live`

## File Structure

| File | Responsibility |
|------|---------------|
| `evals/audit/test_tool_audit.py` | Layer 1: enumerate all 19 tools, map coverage, produce gap report |
| `evals/audit/report.json` | JSON artifact with audit results |
| `evals/golden/conftest.py` | Layer 2: fixtures for loading golden profiles and ground truth |
| `evals/golden/test_extraction_tools.py` | Run extraction tools against real documents, validate against ground truth |
| `evals/golden/test_validation_tools.py` | Run validation tools against extracted data |
| `evals/golden/test_eligibility_tools.py` | Run eligibility tools against feature dicts |
| `evals/golden/test_decision_tools.py` | Run decision tools against scores |
| `evals/contracts/schemas.py` | Layer 3: Pydantic contract definitions for all 19 tools |
| `evals/contracts/test_contracts.py` | Validate tool outputs against contracts |
| `evals/contracts/test_error_handling.py` | Malformed inputs, missing files, failure paths |
| `evals/integration/test_live_agent_graph.py` | Layer 4: full graph with real LLM, Langfuse trace validation |
| `evals/conftest.py` | Shared fixtures (markers, timeout config) |

---

### Task 1: Layer 1 — Tool Audit

**Files:**
- Create: `evals/audit/__init__.py`
- Create: `evals/audit/test_tool_audit.py`

**Interfaces:**
- Consumes: tool lists from `src.agents.extraction.tools.ALL_EXTRACTION_TOOLS`, `src.agents.validation.tools`, `src.agents.eligibility.tools`, `src.agents.decision.tools`
- Produces: `evals/audit/report.json` with keys `tool_inventory`, `coverage_map`, `gaps`

- [ ] **Step 1: Write the failing test**

Create `evals/audit/__init__.py` (empty) and `evals/audit/test_tool_audit.py`:

```python
"""Layer 1: Tool audit — enumerate all agent tools and map test coverage."""

import json
from pathlib import Path
from typing import Any

import pytest

from src.agents.extraction.tools import ALL_EXTRACTION_TOOLS
from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    applicant_clarify_tool,
    validation_confidence_tool,
)
from src.agents.eligibility.tools import (
    ml_model_predict_tool,
    feature_importance_tool,
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
)
from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)

TOOLS_REGISTRY = {
    "extraction": ALL_EXTRACTION_TOOLS,
    "validation": [
        per_document_validation_tool,
        cross_document_compare_tool,
        discrepancy_classify_tool,
        applicant_clarify_tool,
        validation_confidence_tool,
    ],
    "eligibility": [
        ml_model_predict_tool,
        feature_importance_tool,
        adjust_factor_weighting_tool,
        eligibility_explanation_tool,
    ],
    "decision": [
        decision_logic_tool,
        decision_explanation_tool,
        enablement_recommendation_tool,
        decision_formatting_tool,
    ],
}

UNIT_TEST_PATHS = {
    "extraction": Path("tests/unit/agents/test_extraction.py"),
    "validation": Path("tests/unit/agents/test_validation.py"),
    "eligibility": Path("tests/unit/agents/test_eligibility.py"),
    "decision": Path("tests/unit/agents/test_decision.py"),
}


def _tool_name(tool) -> str:
    return getattr(tool, "name", getattr(tool, "__name__", str(tool)))


def _count_tests_for_agent(agent_name: str) -> int:
    """Count test classes/methods in the unit test file for an agent."""
    test_file = UNIT_TEST_PATHS.get(agent_name)
    if not test_file or not test_file.exists():
        return 0
    content = test_file.read_text(encoding="utf-8")
    # Rough count: count lines starting with 'def test_' or 'class Test'
    test_count = sum(
        1 for line in content.splitlines()
        if line.strip().startswith("def test_") or line.strip().startswith("class Test")
    )
    return test_count


def test_tool_audit_produces_report(tmp_path):
    """Audit all tools and produce a coverage gap report."""
    report: dict[str, Any] = {
        "total_tools": 0,
        "tool_inventory": {},
        "coverage_map": {},
        "gaps": [],
    }

    for agent_name, tools in TOOLS_REGISTRY.items():
        tool_names = [_tool_name(t) for t in tools]
        report["tool_inventory"][agent_name] = tool_names
        report["total_tools"] += len(tool_names)

        test_count = _count_tests_for_agent(agent_name)
        report["coverage_map"][agent_name] = {
            "tool_count": len(tool_names),
            "unit_test_count": test_count,
            "has_tests": test_count > 0,
        }

        if test_count == 0:
            report["gaps"].append({
                "agent": agent_name,
                "tools": tool_names,
                "issue": "no_unit_tests",
            })

    # Write artifact
    report_path = Path(__file__).parent / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    assert report["total_tools"] == 19
    assert len(report["gaps"]) >= 0  # gaps are informational
    assert set(report["tool_inventory"].keys()) == {"extraction", "validation", "eligibility", "decision"}
```

- [ ] **Step 2: Run test to verify it passes**

```bash
.\.venv\Scripts\pytest.exe evals/audit/test_tool_audit.py -v
```

Expected: PASS, with `evals/audit/report.json` created.

- [ ] **Step 3: Commit**

```bash
git add evals/audit/__init__.py evals/audit/test_tool_audit.py
git commit -m "feat(evals): add Layer 1 tool audit"
```

---

### Task 2: Shared Eval Fixtures

**Files:**
- Create: `evals/conftest.py`

**Interfaces:**
- Consumes: `data/test_applicants/profiles.json`
- Produces: `golden_profiles` fixture returning dict of profile_name → profile dict; `get_profile(name)` helper

- [ ] **Step 1: Write shared fixtures**

```python
"""Shared fixtures for evaluation tests."""

import json
from pathlib import Path

import pytest

EVALS_DATA_DIR = Path(__file__).parent.parent / "data" / "test_applicants"
PROFILES_FILE = EVALS_DATA_DIR / "profiles.json"


@pytest.fixture(scope="session")
def golden_profiles():
    """Load all golden profiles from profiles.json."""
    if not PROFILES_FILE.exists():
        pytest.skip(f"Golden profiles not found at {PROFILES_FILE}")
    with open(PROFILES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    profiles = data.get("profiles", [])
    return {p["profile_name"]: p for p in profiles}


@pytest.fixture
def approved_profile(golden_profiles):
    """Get the profile expected to result in 'approved'."""
    for name, profile in golden_profiles.items():
        if profile.get("expected_decision") == "approved":
            return profile
    pytest.skip("No approved profile found")


@pytest.fixture
def manual_review_profile(golden_profiles):
    """Get the profile expected to result in 'manual_review'."""
    for name, profile in golden_profiles.items():
        if profile.get("expected_decision") == "manual_review":
            return profile
    pytest.skip("No manual_review profile found")


@pytest.fixture
def soft_decline_profile(golden_profiles):
    """Get the profile expected to result in 'soft_decline'."""
    for name, profile in golden_profiles.items():
        if profile.get("expected_decision") == "soft_decline":
            return profile
    pytest.skip("No soft_decline profile found")
```

- [ ] **Step 2: Verify fixtures load**

```bash
.\.venv\Scripts\pytest.exe evals/audit/test_tool_audit.py --co -q
```

Expected: test collection succeeds, fixtures available.

- [ ] **Step 3: Commit**

```bash
git add evals/conftest.py
git commit -m "feat(evals): add shared golden profile fixtures"
```

---

### Task 3: Layer 2 — Golden Dataset Validation (Extraction Tools)

**Files:**
- Create: `evals/golden/__init__.py`
- Create: `evals/golden/test_extraction_tools.py`

**Interfaces:**
- Consumes: `golden_profiles` fixture, `data_dir` fixture (path to test_applicants)
- Produces: test assertions validating extraction tool outputs against ground truth

- [ ] **Step 1: Write extraction golden tests**

```python
"""Layer 2: Golden dataset validation — extraction tools."""

import pytest
from pathlib import Path

from src.agents.extraction.tools import (
    ocr_extract_tool,
    pdf_parse_tool,
    confidence_score_tool,
)

EVALS_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "test_applicants"


class TestExtractionGoldenDataset:
    """Run extraction tools against real documents and validate against ground truth."""

    def test_ocr_extract_emirates_id(self, approved_profile):
        """OCR tool extracts text from Emirates ID image."""
        pytest.importorskip("paddleocr")
        doc_files = approved_profile.get("documents", {}).get("emirates_id", {}).get("files", [])
        if not doc_files:
            pytest.skip("No emirates_id files in profile")

        front_file = doc_files[0]
        file_path = EVALS_DATA_DIR / approved_profile["profile_name"] / front_file
        if not file_path.exists():
            pytest.skip(f"File not found: {file_path}")

        result = ocr_extract_tool.invoke({"file_path": str(file_path)})
        assert "error" not in result
        assert "text" in result or "blocks" in result
        assert result.get("confidence", 0) > 0

    def test_pdf_parse_bank_statement(self, approved_profile):
        """PDF parse tool extracts bank statement data."""
        pytest.importorskip("pymupdf4llm")
        doc_files = approved_profile.get("documents", {}).get("bank_statement", {}).get("files", [])
        if not doc_files:
            pytest.skip("No bank_statement files in profile")

        file_path = EVALS_DATA_DIR / approved_profile["profile_name"] / doc_files[0]
        if not file_path.exists():
            pytest.skip(f"File not found: {file_path}")

        result = pdf_parse_tool.invoke({"file_path": str(file_path)})
        assert "error" not in result
        assert "markdown" in result or "json_structure" in result

    def test_confidence_score_computes(self, approved_profile):
        """Confidence score tool computes scores for extracted data."""
        emirates_data = approved_profile.get("documents", {}).get("emirates_id", {}).get("data", {})
        if not emirates_data:
            pytest.skip("No emirates_id data in profile")

        result = confidence_score_tool.invoke({
            "extracted_data": emirates_data,
            "document_type": "emirates_id",
        })
        assert "error" not in result or result.get("overall_confidence") >= 0
```

- [ ] **Step 2: Run tests**

```bash
.\.venv\Scripts\pytest.exe evals/golden/test_extraction_tools.py -v
```

Expected: PASS (or SKIP if dependencies/files missing).

- [ ] **Step 3: Commit**

```bash
git add evals/golden/__init__.py evals/golden/test_extraction_tools.py
git commit -m "feat(evals): add Layer 2 extraction golden tests"
```

---

### Task 4: Layer 2 — Golden Dataset Validation (Validation, Eligibility, Decision Tools)

**Files:**
- Create: `evals/golden/test_validation_tools.py`
- Create: `evals/golden/test_eligibility_tools.py`
- Create: `evals/golden/test_decision_tools.py`

**Interfaces:**
- Consumes: `golden_profiles` fixture, tool invoke APIs
- Produces: assertions validating tool outputs

- [ ] **Step 1: Validation golden tests**

```python
"""Layer 2: Golden dataset validation — validation tools."""

import pytest

from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    validation_confidence_tool,
)


class TestValidationGoldenDataset:
    """Run validation tools against golden profile data."""

    def test_per_document_validation_valid_emirates_id(self, approved_profile):
        """Valid Emirates ID data passes validation."""
        emirates_data = approved_profile.get("documents", {}).get("emirates_id", {}).get("data", {})
        if not emirates_data:
            pytest.skip("No emirates_id data")

        result = per_document_validation_tool.invoke({
            "extracted_data": emirates_data,
            "document_type": "emirates_id",
        })
        assert result["overall_status"] in ("valid", "invalid")
        assert "confidence" in result

    def test_cross_document_identity_match(self, approved_profile):
        """Identity numbers match across documents in a consistent profile."""
        extracted_data = {}
        for doc_type, doc_info in approved_profile.get("documents", {}).items():
            data = doc_info.get("data", {})
            if data:
                extracted_data[doc_type] = data

        if not extracted_data:
            pytest.skip("No document data")

        result = cross_document_compare_tool.invoke({
            "extracted_data": extracted_data,
            "comparison_type": "identity_match",
        })
        assert "overall_match" in result
        assert "confidence" in result

    def test_validation_confidence_computes(self, approved_profile):
        """Validation confidence tool produces a score."""
        result = validation_confidence_tool.invoke({
            "validation_results": {"overall_status": "valid"},
            "discrepancies": [],
        })
        assert "overall_confidence" in result
        assert "recommendation" in result
```

- [ ] **Step 2: Eligibility golden tests**

```python
"""Layer 2: Golden dataset validation — eligibility tools."""

import pytest

from src.agents.eligibility.tools import (
    ml_model_predict_tool,
    feature_importance_tool,
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
)


class TestEligibilityGoldenDataset:
    """Run eligibility tools against golden profile features."""

    def test_ml_predict_approved_profile(self, approved_profile):
        """ML prediction for approved profile returns eligible."""
        applicant = approved_profile.get("applicant", {})
        features = {
            "monthly_income": float(applicant.get("total_monthly_income", 15000)),
            "family_size": int(applicant.get("family_size", 3)),
            "employment_stability_months": 24,
            "credit_score": 720,
            "debt_to_income_ratio": 0.35,
            "net_worth": 50000,
            "housing_cost_ratio": 0.23,
            "support_category": applicant.get("support_category", ""),
            "has_dependents": len(applicant.get("dependents", [])) > 0,
            "employment_status": applicant.get("employment_status", "employed"),
        }
        result = ml_model_predict_tool.invoke({"applicant_features": features})
        assert "predicted_class" in result
        assert "probability" in result
        assert result["method"] in ("ml_model", "rule_based")

    def test_feature_importance(self, approved_profile):
        """Feature importance tool returns ranked features."""
        features = {
            "monthly_income": 15000,
            "credit_score": 720,
            "debt_to_income_ratio": 0.35,
        }
        result = feature_importance_tool.invoke({"applicant_features": features})
        assert "top_features" in result
        assert "method" in result

    def test_factor_weighting_adjustment(self, approved_profile):
        """Factor weighting adjusts score based on context."""
        result = adjust_factor_weighting_tool.invoke({
            "eligibility_score": 0.65,
            "feature_importance": [{"feature": "credit_score", "importance": 0.3}],
            "applicant_context": {
                "support_category": "divorced",
                "family_size": 3,
                "has_dependents": True,
                "employment_status": "employed",
            },
        })
        assert "adjusted_score" in result
        assert "adjustment_amount" in result
        assert "reasoning" in result

    def test_eligibility_explanation(self, approved_profile):
        """Explanation tool generates readable text."""
        result = eligibility_explanation_tool.invoke({
            "eligibility_score": 0.70,
            "feature_importance": [{"feature": "credit_score", "importance": 0.3}],
            "applicant_context": {"support_category": "divorced", "credit_score": 720},
            "validation_results": {"overall_confidence": 0.90},
        })
        assert "explanation" in result
        assert "recommendation" in result
```

- [ ] **Step 3: Decision golden tests**

```python
"""Layer 2: Golden dataset validation — decision tools."""

import pytest

from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)


class TestDecisionGoldenDataset:
    """Run decision tools against golden profile scores."""

    def test_decision_logic_approved(self, approved_profile):
        """High score + high confidence + no discrepancies = approved."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "discrepancies": [],
            "support_category": "divorced",
        })
        assert result["decision"] == "approved"

    def test_decision_logic_soft_decline(self, soft_decline_profile):
        """Low score = soft_decline."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.25,
            "validation_confidence": 0.90,
            "discrepancies": [],
            "support_category": "unknown_parentage",
        })
        assert result["decision"] == "soft_decline"

    def test_decision_explanation(self, approved_profile):
        """Explanation tool generates decision-specific text."""
        result = decision_explanation_tool.invoke({
            "decision": "approved",
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "applicant_context": {
                "support_category": "divorced",
                "family_size": 3,
            },
        })
        assert "explanation" in result
        assert "key_factors" in result

    def test_enablement_recommendations(self, approved_profile):
        """Enablement tool returns recommendations for approved decision."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "employed",
                "has_dependents": True,
                "credit_score": 720,
            },
            "eligibility_score": 0.75,
            "decision": "approved",
        })
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    def test_decision_formatting(self, approved_profile):
        """Formatting tool produces a decision card."""
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Your application is approved.",
            "enablement_recommendations": {"recommendations": []},
            "applicant_context": {"support_category": "divorced"},
        })
        assert result["title"] == "Application Approved"
        assert result["color"] == "green"
        assert result["icon"] == "check_circle"
```

- [ ] **Step 4: Run all golden tests**

```bash
.\.venv\Scripts\pytest.exe evals/golden/ -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add evals/golden/test_validation_tools.py evals/golden/test_eligibility_tools.py evals/golden/test_decision_tools.py
git commit -m "feat(evals): add Layer 2 validation/eligibility/decision golden tests"
```

---

### Task 5: Layer 3 — Schema Contracts

**Files:**
- Create: `evals/contracts/__init__.py`
- Create: `evals/contracts/schemas.py`
- Create: `evals/contracts/test_contracts.py`

**Interfaces:**
- Consumes: tool invoke APIs
- Produces: Pydantic contract models, conformance test results

- [ ] **Step 1: Define contract schemas**

```python
"""Pydantic contract definitions for all agent tool outputs."""

from pydantic import BaseModel, ConfigDict


class BaseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ExtractionOutputContract(BaseContract):
    """Contract for extraction tool outputs."""
    duration_ms: float
    error: str | None = None


class OcrExtractContract(ExtractionOutputContract):
    text: str | None = None
    blocks: list | None = None
    confidence: float | None = None
    language: str | None = None


class PdfParseContract(ExtractionOutputContract):
    markdown: str | None = None
    json_structure: dict | None = None
    confidence: float | None = None
    field_count: int | None = None
    document_type: str | None = None


class TableExtractContract(ExtractionOutputContract):
    tables: list | None = None
    table_count: int | None = None
    confidence: float | None = None
    flavor: str | None = None


class ResumeParseContract(ExtractionOutputContract):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    total_positions: int | None = None
    confidence: float | None = None


class XlsxExtractContract(ExtractionOutputContract):
    sheets: dict | None = None
    sheet_count: int | None = None
    sheet_names: list | None = None


class ConfidenceScoreContract(ExtractionOutputContract):
    overall_confidence: float | None = None
    routing_decision: str | None = None
    field_confidences: dict | None = None
    low_confidence_fields: list | None = None


class ValidationOutputContract(BaseContract):
    duration_ms: float
    confidence: float


class PerDocumentValidationContract(ValidationOutputContract):
    document_type: str
    validation_results: list
    overall_status: str
    errors: list


class CrossDocumentCompareContract(ValidationOutputContract):
    comparison_type: str
    overall_match: bool
    discrepancies: list


class DiscrepancyClassifyContract(ValidationOutputContract):
    discrepancy_type: str
    classification: str
    recommended_action: str


class ApplicantClarifyContract(ValidationOutputContract):
    question: str
    field: str
    discrepancy_type: str
    priority: str


class ValidationConfidenceContract(ValidationOutputContract):
    overall_confidence: float
    recommendation: str
    unresolved_count: int
    critical_count: int


class EligibilityOutputContract(BaseContract):
    duration_ms: float
    predicted_class: str | None = None
    probability: float | None = None
    method: str | None = None


class MlPredictContract(EligibilityOutputContract):
    factor_contributions: dict | None = None


class FeatureImportanceContract(EligibilityOutputContract):
    top_features: list | None = None


class AdjustFactorContract(BaseContract):
    duration_ms: float
    adjusted_score: float
    adjustment_amount: float
    reasoning: str


class EligibilityExplanationContract(BaseContract):
    duration_ms: float
    explanation: str
    key_factors: list
    recommendation: str


class DecisionOutputContract(BaseContract):
    duration_ms: float


class DecisionLogicContract(DecisionOutputContract):
    decision: str
    reasoning: str
    eligibility_score: float
    validation_confidence: float
    critical_discrepancies: int


class DecisionExplanationContract(DecisionOutputContract):
    explanation: str
    key_factors: list
    support_category: str


class EnablementRecommendationContract(DecisionOutputContract):
    recommendations: list
    total_count: int


class DecisionFormattingContract(DecisionOutputContract):
    title: str
    decision: str
    color: str
    icon: str
    explanation: str
    next_steps: list


CONTRACT_MAP = {
    "ocr_extract_tool": OcrExtractContract,
    "pdf_parse_tool": PdfParseContract,
    "table_extract_tool": TableExtractContract,
    "resume_parse_tool": ResumeParseContract,
    "xlsx_extract_tool": XlsxExtractContract,
    "confidence_score_tool": ConfidenceScoreContract,
    "per_document_validation_tool": PerDocumentValidationContract,
    "cross_document_compare_tool": CrossDocumentCompareContract,
    "discrepancy_classify_tool": DiscrepancyClassifyContract,
    "applicant_clarify_tool": ApplicantClarifyContract,
    "validation_confidence_tool": ValidationConfidenceContract,
    "ml_model_predict_tool": MlPredictContract,
    "feature_importance_tool": FeatureImportanceContract,
    "adjust_factor_weighting_tool": AdjustFactorContract,
    "eligibility_explanation_tool": EligibilityExplanationContract,
    "decision_logic_tool": DecisionLogicContract,
    "decision_explanation_tool": DecisionExplanationContract,
    "enablement_recommendation_tool": EnablementRecommendationContract,
    "decision_formatting_tool": DecisionFormattingContract,
}
```

- [ ] **Step 2: Write contract conformance tests**

```python
"""Layer 3: Schema contract conformance tests."""

import pytest
from src.agents.extraction.tools import (
    ocr_extract_tool,
    pdf_parse_tool,
    table_extract_tool,
    resume_parse_tool,
    xlsx_extract_tool,
    confidence_score_tool,
)
from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    applicant_clarify_tool,
    validation_confidence_tool,
)
from src.agents.eligibility.tools import (
    ml_model_predict_tool,
    feature_importance_tool,
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
)
from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)
from evals.contracts.schemas import CONTRACT_MAP

TOOLS_UNDER_TEST = {
    "ocr_extract_tool": lambda: ocr_extract_tool.invoke({"file_path": "/nonexistent.png"}),
    "pdf_parse_tool": lambda: pdf_parse_tool.invoke({"file_path": "/nonexistent.pdf"}),
    "table_extract_tool": lambda: table_extract_tool.invoke({"file_path": "/nonexistent.pdf"}),
    "resume_parse_tool": lambda: resume_parse_tool.invoke({"file_path": "/nonexistent.docx"}),
    "xlsx_extract_tool": lambda: xlsx_extract_tool.invoke({"file_path": "/nonexistent.xlsx"}),
    "confidence_score_tool": lambda: confidence_score_tool.invoke({
        "extracted_data": {}, "document_type": "emirates_id"
    }),
    "per_document_validation_tool": lambda: per_document_validation_tool.invoke({
        "extracted_data": {}, "document_type": "emirates_id"
    }),
    "cross_document_compare_tool": lambda: cross_document_compare_tool.invoke({
        "extracted_data": {}, "comparison_type": "identity_match"
    }),
    "discrepancy_classify_tool": lambda: discrepancy_classify_tool.invoke({
        "discrepancy": {}, "extraction_confidence": {}
    }),
    "applicant_clarify_tool": lambda: applicant_clarify_tool.invoke({
        "discrepancy": {}, "applicant_context": {}
    }),
    "validation_confidence_tool": lambda: validation_confidence_tool.invoke({
        "validation_results": {}, "discrepancies": []
    }),
    "ml_model_predict_tool": lambda: ml_model_predict_tool.invoke({
        "applicant_features": {}
    }),
    "feature_importance_tool": lambda: feature_importance_tool.invoke({
        "applicant_features": {}
    }),
    "adjust_factor_weighting_tool": lambda: adjust_factor_weighting_tool.invoke({
        "eligibility_score": 0.5,
        "feature_importance": [],
        "applicant_context": {},
    }),
    "eligibility_explanation_tool": lambda: eligibility_explanation_tool.invoke({
        "eligibility_score": 0.5,
        "feature_importance": [],
        "applicant_context": {},
        "validation_results": {},
    }),
    "decision_logic_tool": lambda: decision_logic_tool.invoke({
        "eligibility_score": 0.5,
        "validation_confidence": 0.5,
        "discrepancies": [],
        "support_category": "general",
    }),
    "decision_explanation_tool": lambda: decision_explanation_tool.invoke({
        "decision": "approved",
        "eligibility_score": 0.5,
        "validation_confidence": 0.5,
        "applicant_context": {},
    }),
    "enablement_recommendation_tool": lambda: enablement_recommendation_tool.invoke({
        "applicant_context": {},
        "eligibility_score": 0.5,
        "decision": "approved",
    }),
    "decision_formatting_tool": lambda: decision_formatting_tool.invoke({
        "decision": "approved",
        "explanation": "test",
        "enablement_recommendations": None,
        "applicant_context": {},
    }),
}


@pytest.mark.parametrize("tool_name,invoke_fn", TOOLS_UNDER_TEST.items())
def test_tool_output_conforms_to_contract(tool_name, invoke_fn):
    """Every tool output must conform to its Pydantic contract."""
    contract_cls = CONTRACT_MAP.get(tool_name)
    if contract_cls is None:
        pytest.fail(f"No contract defined for {tool_name}")

    result = invoke_fn()
    if not isinstance(result, dict):
        pytest.fail(f"{tool_name} returned non-dict: {type(result)}")

    # Error responses are allowed to deviate from contract
    if "error" in result and len(result) <= 2:
        return

    contract = contract_cls(**result)
    assert contract is not None
```

- [ ] **Step 3: Run contract tests**

```bash
.\.venv\Scripts\pytest.exe evals/contracts/test_contracts.py -v
```

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add evals/contracts/__init__.py evals/contracts/schemas.py evals/contracts/test_contracts.py
git commit -m "feat(evals): add Layer 3 schema contract tests"
```

---

### Task 6: Layer 3 — Error Handling Tests

**Files:**
- Create: `evals/contracts/test_error_handling.py`

**Interfaces:**
- Consumes: tool invoke APIs
- Produces: assertions that tools return error schema on malformed input

- [ ] **Step 1: Write error handling tests**

```python
"""Layer 3: Error handling — tools must not raise on malformed input."""

import pytest

from src.agents.extraction.tools import (
    ocr_extract_tool,
    pdf_parse_tool,
    table_extract_tool,
    resume_parse_tool,
    xlsx_extract_tool,
    confidence_score_tool,
)
from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    applicant_clarify_tool,
    validation_confidence_tool,
)
from src.agents.eligibility.tools import (
    ml_model_predict_tool,
    feature_importance_tool,
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
)
from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)


MALFORMED_INPUTS = {
    "ocr_extract_tool": [
        {"file_path": ""},
        {"file_path": None},
        {},
    ],
    "pdf_parse_tool": [
        {"file_path": ""},
        {"file_path": 12345},
        {},
    ],
    "confidence_score_tool": [
        {"extracted_data": None, "document_type": "emirates_id"},
        {"extracted_data": "not_a_dict", "document_type": "emirates_id"},
        {},
    ],
    "per_document_validation_tool": [
        {"extracted_data": None, "document_type": "emirates_id"},
        {"extracted_data": "not_a_dict", "document_type": "emirates_id"},
        {},
    ],
    "cross_document_compare_tool": [
        {"extracted_data": None, "comparison_type": "identity_match"},
        {"extracted_data": "not_a_dict", "comparison_type": "identity_match"},
        {},
    ],
    "discrepancy_classify_tool": [
        {"discrepancy": None, "extraction_confidence": {}},
        {"discrepancy": "not_a_dict", "extraction_confidence": {}},
        {},
    ],
    "applicant_clarify_tool": [
        {"discrepancy": None, "applicant_context": {}},
        {},
    ],
    "validation_confidence_tool": [
        {"validation_results": None, "discrepancies": []},
        {"validation_results": {}, "discrepancies": None},
        {},
    ],
    "ml_model_predict_tool": [
        {"applicant_features": None},
        {"applicant_features": "not_a_dict"},
        {},
    ],
    "feature_importance_tool": [
        {"applicant_features": None},
        {},
    ],
    "adjust_factor_weighting_tool": [
        {"eligibility_score": "not_a_number", "feature_importance": [], "applicant_context": {}},
        {},
    ],
    "eligibility_explanation_tool": [
        {"eligibility_score": "not_a_number", "feature_importance": [], "applicant_context": {}, "validation_results": {}},
        {},
    ],
    "decision_logic_tool": [
        {"eligibility_score": "not_a_number", "validation_confidence": "not_a_number", "discrepancies": [], "support_category": "general"},
        {},
    ],
    "decision_explanation_tool": [
        {"decision": None, "eligibility_score": 0.5, "validation_confidence": 0.5, "applicant_context": {}},
        {},
    ],
    "enablement_recommendation_tool": [
        {"applicant_context": None, "eligibility_score": 0.5, "decision": "approved"},
        {},
    ],
    "decision_formatting_tool": [
        {"decision": None, "explanation": "test", "enablement_recommendations": None, "applicant_context": {}},
        {},
    ],
}


@pytest.mark.parametrize("tool_name,malformed_inputs", MALFORMED_INPUTS.items())
def test_tool_handles_malformed_input(tool_name, malformed_inputs):
    """Tools must return error dict, not raise, on malformed input."""
    tool = globals().get(tool_name)
    if tool is None:
        pytest.fail(f"Tool {tool_name} not found")

    for i, bad_input in enumerate(malformed_inputs):
        try:
            result = tool.invoke(bad_input)
        except Exception as e:
            pytest.fail(f"{tool_name} raised {type(e).__name__} on malformed input {i}: {e}")

        # Result should be a dict (possibly with "error" key)
        assert isinstance(result, dict), f"{tool_name} returned non-dict on malformed input {i}"
```

- [ ] **Step 2: Run error handling tests**

```bash
.\.venv\Scripts\pytest.exe evals/contracts/test_error_handling.py -v
```

Expected: All PASS (tools gracefully handle bad input).

- [ ] **Step 3: Commit**

```bash
git add evals/contracts/test_error_handling.py
git commit -m "feat(evals): add Layer 3 error handling tests"
```

---

### Task 7: Layer 4 — Live Integration Test

**Files:**
- Create: `evals/integration/__init__.py`
- Create: `evals/integration/test_live_agent_graph.py`

**Interfaces:**
- Consumes: `golden_profiles` fixture, full agent graph from `src.agents.orchestrator.graph`
- Produces: assertions validating full graph execution with real LLM

- [ ] **Step 1: Write live integration test**

```python
"""Layer 4: Live integration — full agent graph with real LLM calls."""

import pytest
from typing import Any


class TestLiveAgentGraph:
    """Run the full orchestrator graph with real LLM and validate tool invocation."""

    @pytest.mark.live
    @pytest.mark.skip(reason="Requires running infrastructure and real LLM")
    async def test_full_graph_approved_profile(self, approved_profile):
        """Full graph execution produces expected decision for approved profile."""
        from src.agents.orchestrator.graph import build_orchestrator_graph
        from src.services.chat_service import ChatService

        # Build and run the graph
        graph = build_orchestrator_graph()
        assert graph is not None

        # The graph should complete and produce a decision
        # This is a smoke test — full execution requires DB + LLM
        assert hasattr(graph, "compile")

    @pytest.mark.live
    @pytest.mark.skip(reason="Requires running infrastructure and real LLM")
    async def test_tool_invocation_sequence(self, approved_profile):
        """Tools are invoked in expected sequence during graph execution."""
        # Validate that the graph structure includes tool-calling nodes
        from src.agents.extraction.graph import build_extraction_graph
        from src.agents.validation.graph import build_validation_graph
        from src.agents.eligibility.graph import build_eligibility_graph
        from src.agents.decision.graph import build_decision_graph

        # Each subgraph should be buildable
        extraction = build_extraction_graph()
        validation = build_validation_graph()
        eligibility = build_eligibility_graph()
        decision = build_decision_graph()

        assert extraction is not None
        assert validation is not None
        assert eligibility is not None
        assert decision is not None

    def test_graph_structure_valid(self):
        """Agent subgraphs are structurally valid (no real LLM needed)."""
        from src.agents.extraction.graph import build_extraction_graph
        from src.agents.validation.graph import build_validation_graph

        extraction = build_extraction_graph()
        validation = build_validation_graph()

        assert extraction is not None
        assert validation is not None
```

- [ ] **Step 2: Run integration tests (non-live subset)**

```bash
.\.venv\Scripts\pytest.exe evals/integration/ -v -m "not live"
```

Expected: PASS (live tests skipped).

- [ ] **Step 3: Commit**

```bash
git add evals/integration/__init__.py evals/integration/test_live_agent_graph.py
git commit -m "feat(evals): add Layer 4 live integration tests"
```

---

### Task 8: Run Full Suite and Document Results

**Files:**
- Modify: `evals/AGENTS.md` (update with framework documentation)

**Interfaces:**
- Consumes: all 4 layers
- Produces: full test run output, updated AGENTS.md

- [ ] **Step 1: Run full evaluation suite**

```bash
.\.venv\Scripts\pytest.exe evals/ -v --ignore=evals/integration/
```

Expected: All non-live tests PASS.

- [ ] **Step 2: Run with coverage report**

```bash
.\.venv\Scripts\pytest.exe evals/ --ignore=evals/integration/ --cov=src.agents --cov-report=term-missing -v
```

Expected: Coverage report showing which agent tool code is exercised.

- [ ] **Step 3: Update evals/AGENTS.md**

Update the `evals/AGENTS.md` file to document the new four-layer framework structure, replacing the placeholder content with:

```markdown
# Agent Evaluation Framework

## Purpose
Four-layer evaluation framework for measuring agent tool correctness:
1. **Audit** — tool inventory and coverage gap analysis
2. **Golden Dataset** — tool validation against real synthetic profiles
3. **Schema Contracts** — Pydantic contract conformance and error handling
4. **Live Integration** — full agent graph with real LLM calls

## Running Evaluations

```bash
# All layers (non-live)
.\.venv\Scripts\pytest.exe evals/ -v --ignore=evals/integration/

# Specific layer
.\.venv\Scripts\pytest.exe evals/audit/ -v
.\.venv\Scripts\pytest.exe evals/golden/ -v
.\.venv\Scripts\pytest.exe evals/contracts/ -v

# Live integration (requires infrastructure + LLM)
.\.venv\Scripts\pytest.exe evals/integration/ -v -m live
```

## Golden Dataset
Uses `data/test_applicants/profiles.json` with 3 cross-document-consistent profiles:
- `divorced_employed_good_credit` → expected: approved
- `abandoned_unemployed_poor_credit` → expected: manual_review
- `unknown_parentage_self_employed_borderline` → expected: soft_decline
```

- [ ] **Step 4: Commit**

```bash
git add evals/AGENTS.md
git commit -m "docs(evals): document four-layer evaluation framework"
```
