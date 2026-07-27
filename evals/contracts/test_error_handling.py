"""Layer 3: Error handling — tools must not raise on malformed input."""

import time

import pytest
import structlog

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

logger = structlog.get_logger(__name__)


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
    "table_extract_tool": [
        {"file_path": ""},
        {"file_path": None},
        {},
    ],
    "resume_parse_tool": [
        {"file_path": ""},
        {"file_path": None},
        {},
    ],
    "xlsx_extract_tool": [
        {"file_path": ""},
        {"file_path": None},
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
        start = time.perf_counter()
        try:
            result = tool.invoke(bad_input)
            duration_ms = (time.perf_counter() - start) * 1000

            logger.debug(
                "error_handling_test_passed",
                tool=tool_name,
                input_index=i,
                duration_ms=round(duration_ms, 2),
                has_error_key="error" in result,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "error_handling_test_failed",
                tool=tool_name,
                input_index=i,
                duration_ms=round(duration_ms, 2),
                exception_type=type(e).__name__,
            )
            logger.exception("error_handling_test_exception")
            pytest.fail(f"{tool_name} raised {type(e).__name__} on malformed input {i}: {e}")

        # Result should be a dict (possibly with "error" key)
        assert isinstance(result, dict), f"{tool_name} returned non-dict on malformed input {i}"
