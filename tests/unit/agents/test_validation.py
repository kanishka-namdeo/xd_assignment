"""Validation agent unit tests."""

import pytest
import structlog
from unittest.mock import MagicMock, patch

from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    applicant_clarify_tool,
    validation_confidence_tool,
)
from src.agents.validation.nodes import (
    attempt_validation_node,
    evaluate_validation_node,
    critique_validation_node,
)

logger = structlog.get_logger(__name__)


class TestPerDocumentValidationTool:
    """Test per-document validation tool."""

    def test_valid_document(self):
        """Test validation passes for valid extracted data."""
        valid_data = {
            "identity_number": "784-1990-1234567-6",
            "full_name_en": "Ahmed Mohammed Ali",
            "nationality": "UAE",
            "date_of_birth": "1990-05-15",
            "gender": "Male",
            "expiry_date": "2028-12-31",
        }
        result = per_document_validation_tool.invoke({
            "extracted_data": valid_data,
            "document_type": "emirates_id",
        })
        assert result["overall_status"] == "valid"
        assert result["confidence"] == 1.0
        assert len(result["errors"]) == 0

    def test_invalid_document_missing_fields(self):
        """Test validation fails for missing required fields."""
        incomplete_data = {"identity_number": "123"}
        result = per_document_validation_tool.invoke({
            "extracted_data": incomplete_data,
            "document_type": "emirates_id",
        })
        assert result["overall_status"] == "invalid"
        assert result["confidence"] < 1.0
        assert len(result["errors"]) > 0

    def test_confidence_decreases_with_errors(self):
        """Test confidence decreases as error count increases."""
        data_with_errors = {
            "identity_number": "invalid",
            "full_name_en": "",
            "nationality": "",
        }
        result = per_document_validation_tool.invoke({
            "extracted_data": data_with_errors,
            "document_type": "emirates_id",
        })
        assert result["confidence"] < 1.0
        assert result["confidence"] >= 0.0


class TestCrossDocumentCompareTool:
    """Test cross-document comparison tool."""

    def test_identity_match(self, sample_extracted_data):
        """Test identity numbers match across documents."""
        result = cross_document_compare_tool.invoke({
            "extracted_data": sample_extracted_data,
            "comparison_type": "identity_match",
        })
        assert result["overall_match"] is True
        assert len(result["discrepancies"]) == 0
        assert result["confidence"] == 1.0

    def test_identity_mismatch(self, sample_extracted_data):
        """Test identity numbers mismatch across documents."""
        data = sample_extracted_data.copy()
        data["credit_report"] = data["credit_report"].copy()
        data["credit_report"]["identity_number"] = "999999999999999"
        result = cross_document_compare_tool.invoke({
            "extracted_data": data,
            "comparison_type": "identity_match",
        })
        assert result["overall_match"] is False
        assert len(result["discrepancies"]) > 0
        assert result["discrepancies"][0]["type"] == "identity_mismatch"

    def test_name_match_high_similarity(self, sample_extracted_data):
        """Test names match with high Jaccard similarity."""
        result = cross_document_compare_tool.invoke({
            "extracted_data": sample_extracted_data,
            "comparison_type": "name_consistency",
        })
        assert result["overall_match"] is True
        assert result["confidence"] == 1.0

    def test_name_mismatch_low_similarity(self, sample_extracted_data):
        """Test names mismatch with low Jaccard similarity."""
        data = sample_extracted_data.copy()
        data["emirates_id"] = data["emirates_id"].copy()
        data["emirates_id"]["full_name_en"] = "John Smith"
        result = cross_document_compare_tool.invoke({
            "extracted_data": data,
            "comparison_type": "name_consistency",
        })
        assert result["overall_match"] is False
        assert len(result["discrepancies"]) > 0

    def test_income_match(self, sample_extracted_data):
        """Test income values match within 20% variance."""
        data = sample_extracted_data.copy()
        data["bank_statement"] = data["bank_statement"].copy()
        data["bank_statement"]["closing_balance"] = 12000.0
        result = cross_document_compare_tool.invoke({
            "extracted_data": data,
            "comparison_type": "income_consistency",
        })
        assert result["overall_match"] is True
        assert result["confidence"] == 1.0

    def test_income_mismatch(self, sample_extracted_data):
        """Test income values mismatch with >20% variance."""
        data = sample_extracted_data.copy()
        data["application_form"] = data["application_form"].copy()
        data["application_form"]["total_monthly_income"] = 5000.0
        result = cross_document_compare_tool.invoke({
            "extracted_data": data,
            "comparison_type": "income_consistency",
        })
        assert result["overall_match"] is False
        assert len(result["discrepancies"]) > 0


class TestDiscrepancyClassifyTool:
    """Test discrepancy classification tool."""

    def test_name_mismatch_ocr_error(self):
        """Test high similarity name mismatch classified as OCR error."""
        discrepancy = {
            "type": "name_mismatch",
            "field": "name",
            "values": {"doc1": "Ahmed Mohammed", "doc2": "Ahmed M"},
            "similarity": 0.85,
        }
        confidence = {"doc1": 0.90, "doc2": 0.92}
        result = discrepancy_classify_tool.invoke({
            "discrepancy": discrepancy,
            "extraction_confidence": confidence,
        })
        assert result["classification"] == "ocr_error"
        assert result["recommended_action"] == "accept_with_note"

    def test_name_mismatch_real_discrepancy(self):
        """Test low similarity name mismatch classified as real discrepancy."""
        discrepancy = {
            "type": "name_mismatch",
            "field": "name",
            "values": {"doc1": "Ahmed Mohammed", "doc2": "John Smith"},
            "similarity": 0.50,
        }
        confidence = {"doc1": 0.90, "doc2": 0.92}
        result = discrepancy_classify_tool.invoke({
            "discrepancy": discrepancy,
            "extraction_confidence": confidence,
        })
        assert result["classification"] == "real_discrepancy"
        assert result["recommended_action"] == "request_clarification"

    def test_identity_mismatch_critical(self):
        """Test identity mismatch always classified as critical real discrepancy."""
        discrepancy = {
            "type": "identity_mismatch",
            "field": "identity_number",
            "values": {"doc1": "123", "doc2": "456"},
        }
        confidence = {"doc1": 0.95, "doc2": 0.95}
        result = discrepancy_classify_tool.invoke({
            "discrepancy": discrepancy,
            "extraction_confidence": confidence,
        })
        assert result["classification"] == "real_discrepancy"
        assert result["confidence"] == 0.95
        assert result["recommended_action"] == "escalate"

    def test_income_mismatch_ocr_error(self):
        """Test small income variance classified as OCR error."""
        discrepancy = {
            "type": "income_mismatch",
            "field": "income",
            "values": {"doc1": 12000, "doc2": 12500},
            "variance_pct": 5.0,
        }
        confidence = {"doc1": 0.88, "doc2": 0.90}
        result = discrepancy_classify_tool.invoke({
            "discrepancy": discrepancy,
            "extraction_confidence": confidence,
        })
        assert result["classification"] == "ocr_error"
        assert result["recommended_action"] == "accept_with_note"

    def test_income_mismatch_real_discrepancy(self):
        """Test large income variance classified as real discrepancy."""
        discrepancy = {
            "type": "income_mismatch",
            "field": "income",
            "values": {"doc1": 12000, "doc2": 8000},
            "variance_pct": 30.0,
        }
        confidence = {"doc1": 0.90, "doc2": 0.90}
        result = discrepancy_classify_tool.invoke({
            "discrepancy": discrepancy,
            "extraction_confidence": confidence,
        })
        assert result["classification"] == "real_discrepancy"
        assert result["recommended_action"] == "request_clarification"


class TestApplicantClarifyTool:
    """Test clarification question generation tool."""

    def test_name_mismatch_question(self):
        """Test clarification question for name mismatch."""
        discrepancy = {
            "type": "name_mismatch",
            "field": "name",
            "values": {"emirates_id": "Ahmed Mohammed", "bank_statement": "Ahmed M"},
        }
        context = {"applicant_id": "test-001", "application_id": "app-001"}
        result = applicant_clarify_tool.invoke({
            "discrepancy": discrepancy,
            "applicant_context": context,
        })
        assert "name" in result["question"].lower()
        assert result["priority"] == "medium"
        assert result["discrepancy_type"] == "name_mismatch"

    def test_income_mismatch_question(self):
        """Test clarification question for income mismatch."""
        discrepancy = {
            "type": "income_mismatch",
            "field": "income",
            "values": {"bank_statement": 12000, "application_form": 8000},
        }
        context = {"applicant_id": "test-001", "application_id": "app-001"}
        result = applicant_clarify_tool.invoke({
            "discrepancy": discrepancy,
            "applicant_context": context,
        })
        assert "income" in result["question"].lower()
        assert result["priority"] == "high"

    def test_identity_mismatch_question(self):
        """Test clarification question for identity mismatch."""
        discrepancy = {
            "type": "identity_mismatch",
            "field": "identity_number",
            "values": {"doc1": "123", "doc2": "456"},
        }
        context = {"applicant_id": "test-001", "application_id": "app-001"}
        result = applicant_clarify_tool.invoke({
            "discrepancy": discrepancy,
            "applicant_context": context,
        })
        assert "identity" in result["question"].lower()
        assert result["priority"] == "critical"


class TestValidationConfidenceTool:
    """Test validation confidence computation tool."""

    def test_no_discrepancies_high_confidence(self):
        """Test high confidence with no discrepancies."""
        validation_results = {
            "per_document_validation": {
                "emirates_id": {"confidence": 1.0},
                "bank_statement": {"confidence": 1.0},
            },
            "cross_document_validation": {
                "identity_match": {"confidence": 1.0},
            },
        }
        discrepancies = []
        result = validation_confidence_tool.invoke({
            "validation_results": validation_results,
            "discrepancies": discrepancies,
        })
        assert result["overall_confidence"] >= 0.90
        assert result["recommendation"] == "proceed_to_decision"
        assert result["unresolved_count"] == 0

    def test_unresolved_discrepancies_lower_confidence(self):
        """Test confidence decreases with unresolved discrepancies."""
        validation_results = {
            "per_document_validation": {
                "emirates_id": {"confidence": 0.95},
            },
            "cross_document_validation": {},
        }
        discrepancies = [
            {"resolution_status": "unresolved", "discrepancy_type": "name_mismatch"},
            {"resolution_status": "unresolved", "discrepancy_type": "income_mismatch"},
        ]
        result = validation_confidence_tool.invoke({
            "validation_results": validation_results,
            "discrepancies": discrepancies,
        })
        assert result["overall_confidence"] < 0.95
        assert result["unresolved_count"] == 2

    def test_critical_discrepancy_lower_confidence(self):
        """Test confidence decreases more with critical discrepancies."""
        validation_results = {
            "per_document_validation": {
                "emirates_id": {"confidence": 0.95},
            },
            "cross_document_validation": {},
        }
        discrepancies = [
            {"resolution_status": "unresolved", "discrepancy_type": "identity_mismatch"},
        ]
        result = validation_confidence_tool.invoke({
            "validation_results": validation_results,
            "discrepancies": discrepancies,
        })
        assert result["overall_confidence"] < 0.85
        assert result["critical_count"] == 1

    def test_low_confidence_escalate(self):
        """Test escalation when confidence < 0.70."""
        validation_results = {
            "per_document_validation": {
                "emirates_id": {"confidence": 0.60},
            },
            "cross_document_validation": {},
        }
        discrepancies = [
            {"resolution_status": "unresolved", "discrepancy_type": "identity_mismatch"},
            {"resolution_status": "unresolved", "discrepancy_type": "income_mismatch"},
        ]
        result = validation_confidence_tool.invoke({
            "validation_results": validation_results,
            "discrepancies": discrepancies,
        })
        assert result["overall_confidence"] < 0.70
        assert result["recommendation"] == "escalate"


class TestReflexionLoop:
    """Test Reflexion reasoning loop."""

    def test_validation_pass_first_attempt(self, sample_state):
        """Test validation passes on first attempt with high confidence."""
        state = sample_state.copy()
        state["retry_count"] = 0
        state["validation_results"] = {
            "per_document_validation": {
                "emirates_id": {"confidence": 0.95},
                "bank_statement": {"confidence": 0.92},
            },
            "cross_document_validation": {
                "identity_match": {"confidence": 1.0},
            },
        }
        state["discrepancies"] = []
        result = critique_validation_node(state)
        assert result["_next_action"] == "proceed"

    def test_validation_fail_retry(self, sample_state):
        """Test validation retry after failure."""
        state = sample_state.copy()
        state["retry_count"] = 1
        state["discrepancies"] = [
            {
                "classification": "real_discrepancy",
                "resolution_status": "unresolved",
                "discrepancy_type": "name_mismatch",
            }
        ]
        result = critique_validation_node(state)
        assert result["_next_action"] == "request_clarification"

    def test_validation_escalate_after_retries(self, sample_state):
        """Test escalation after 3 failed attempts."""
        state = sample_state.copy()
        state["retry_count"] = 3
        state["discrepancies"] = [
            {
                "classification": "real_discrepancy",
                "resolution_status": "unresolved",
                "discrepancy_type": "identity_mismatch",
            }
        ]
        result = critique_validation_node(state)
        assert result["_next_action"] == "escalate"


class TestGate2Completeness:
    """Test Gate 2 completeness validation."""

    def test_all_docs_present(self, sample_state):
        """Test gate passes when all required documents present."""
        from src.agents.validation.nodes import gate_2_completeness_node
        state = sample_state.copy()
        state["support_category"] = "divorced"
        result = gate_2_completeness_node(state)
        assert result["gate_status"] in ["passed", "failed"]

    def test_missing_doc(self, sample_state):
        """Test gate fails when required document missing."""
        from src.agents.validation.nodes import gate_2_completeness_node
        state = sample_state.copy()
        state["support_category"] = "divorced"
        state["extracted_data"] = {"emirates_id": {}}
        result = gate_2_completeness_node(state)
        assert len(result["gate_errors"]) > 0

    def test_identity_inconsistency(self, sample_state):
        """Test gate fails when identity inconsistent."""
        from src.agents.validation.nodes import gate_2_completeness_node
        state = sample_state.copy()
        state["support_category"] = "divorced"
        state["extracted_data"]["credit_report"]["identity_number"] = "999999999999999"
        result = gate_2_completeness_node(state)
        assert result["gate_status"] == "failed"
