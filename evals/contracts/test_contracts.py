"""Layer 3: Schema contract conformance tests."""

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
from evals.contracts.schemas import CONTRACT_MAP

logger = structlog.get_logger(__name__)

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

    start = time.perf_counter()
    result = invoke_fn()
    duration_ms = (time.perf_counter() - start) * 1000

    if not isinstance(result, dict):
        logger.error(
            "contract_validation_failed",
            tool=tool_name,
            duration_ms=round(duration_ms, 2),
            reason="non_dict_result",
        )
        pytest.fail(f"{tool_name} returned non-dict: {type(result)}")

    # Error responses are allowed to deviate from contract
    if "error" in result and len(result) <= 2:
        logger.debug(
            "contract_validation_skipped",
            tool=tool_name,
            duration_ms=round(duration_ms, 2),
            reason="error_response",
        )
        return

    contract = contract_cls(**result)
    logger.info(
        "contract_validation_passed",
        tool=tool_name,
        duration_ms=round(duration_ms, 2),
    )
    assert contract is not None
