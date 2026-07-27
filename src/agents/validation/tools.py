"""Validation tools for Reflexion reasoning loop.

Five thin wrapper tools delegating business logic to domain layer:
- per_document_validation_tool → domain/scoring + gates
- cross_document_compare_tool → domain/cross_document.py
- discrepancy_classify_tool → domain/discrepancy_classifier.py
- applicant_clarify_tool → domain/templates/clarification.py
- validation_confidence_tool → domain/scoring/validation_scorer.py
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.tools import tool

from src.agents.gates.document_integrity import validate_document_integrity
from src.domain.cross_document import (
    check_address_consistency,
    check_identity_match,
    check_income_consistency,
    check_name_consistency,
)
from src.domain.discrepancy_classifier import classify_discrepancy
from src.domain.scoring.validation_scorer import compute_validation_confidence
from src.domain.templates.clarification import PRIORITY_MAP, format_clarification_question

logger = structlog.get_logger(__name__)


@tool
def per_document_validation_tool(
    extracted_data: Any = None,
    document_type: Any = None,
) -> dict:
    """Validate extracted data within a single document for internal consistency."""
    start = time.perf_counter()

    if extracted_data is None or not isinstance(extracted_data, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="per_document_validation", reason="extracted_data must be a dict")
        return {"document_type": document_type if isinstance(document_type, str) else "unknown", "validation_results": [], "overall_status": "error", "confidence": 0.0, "errors": ["extracted_data must be a dict"], "duration_ms": round(duration_ms, 2)}

    if document_type is None or not isinstance(document_type, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="per_document_validation", reason="document_type must be a string")
        return {"document_type": "unknown", "validation_results": [], "overall_status": "error", "confidence": 0.0, "errors": ["document_type must be a string"], "duration_ms": round(duration_ms, 2)}

    logger.debug("validation_tool_start", tool="per_document_validation", document_type=document_type)

    try:
        is_valid, errors = validate_document_integrity(extracted_data, document_type)
        validation_results = [
            {"rule": "integrity_check", "status": "passed" if is_valid else "failed", "message": "All integrity checks passed" if is_valid else e}
            for e in (["All integrity checks passed"] if is_valid else errors)
        ]
        overall_status = "valid" if is_valid else "invalid"
        confidence = 1.0 if is_valid else max(0.0, 1.0 - (len(errors) * 0.15))

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("per_document_validation_complete", document_type=document_type, status=overall_status, error_count=len(errors), confidence=round(confidence, 2), duration_ms=round(duration_ms, 2))

        return {
            "document_type": document_type,
            "validation_results": validation_results,
            "overall_status": overall_status,
            "confidence": confidence,
            "errors": errors,
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("per_document_validation_error", document_type=document_type, error=str(e), duration_ms=round(duration_ms, 2))
        return {"document_type": document_type, "validation_results": [], "overall_status": "error", "confidence": 0.0, "errors": [str(e)], "duration_ms": round(duration_ms, 2)}


@tool
def cross_document_compare_tool(
    extracted_data: Any = None,
    comparison_type: Any = None,
) -> dict:
    """Compare fields across multiple documents for consistency."""
    start = time.perf_counter()

    if extracted_data is None or not isinstance(extracted_data, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="cross_document_compare", reason="extracted_data must be a dict")
        return {"comparison_type": comparison_type if isinstance(comparison_type, str) else "unknown", "results": [], "overall_match": False, "discrepancies": [], "confidence": 0.0, "error": "extracted_data must be a dict", "duration_ms": round(duration_ms, 2)}

    if comparison_type is None or not isinstance(comparison_type, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="cross_document_compare", reason="comparison_type must be a string")
        return {"comparison_type": "unknown", "results": [], "overall_match": False, "discrepancies": [], "confidence": 0.0, "error": "comparison_type must be a string", "duration_ms": round(duration_ms, 2)}

    logger.debug("cross_document_compare_start", comparison_type=comparison_type, document_count=len(extracted_data))

    try:
        checkers = {
            "identity_match": check_identity_match,
            "name_consistency": check_name_consistency,
            "income_consistency": check_income_consistency,
            "address_consistency": check_address_consistency,
        }
        checker = checkers.get(comparison_type)
        result = checker(extracted_data) if checker else {"comparison_type": comparison_type, "results": [], "overall_match": True, "discrepancies": [], "confidence": 1.0}

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("cross_document_compare_complete", comparison_type=comparison_type, overall_match=result.get("overall_match"), discrepancy_count=len(result.get("discrepancies", [])), confidence=round(result.get("confidence", 0), 2), duration_ms=round(duration_ms, 2))
        result["duration_ms"] = round(duration_ms, 2)
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("cross_document_compare_error", comparison_type=comparison_type, error=str(e), duration_ms=round(duration_ms, 2))
        return {"comparison_type": comparison_type, "results": [], "overall_match": False, "discrepancies": [], "confidence": 0.0, "error": str(e), "duration_ms": round(duration_ms, 2)}


@tool
def discrepancy_classify_tool(
    discrepancy: Any = None,
    extraction_confidence: Any = None,
) -> dict:
    """Classify whether a discrepancy is an OCR error or a real inconsistency."""
    start = time.perf_counter()

    if discrepancy is None or not isinstance(discrepancy, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="discrepancy_classify", reason="discrepancy must be a dict")
        return {"discrepancy_type": "unknown", "field": "unknown", "classification": "error", "confidence": 0.0, "reasoning": "discrepancy must be a dict", "recommended_action": "manual_review", "duration_ms": round(duration_ms, 2)}

    if extraction_confidence is None or not isinstance(extraction_confidence, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="discrepancy_classify", reason="extraction_confidence must be a dict")
        return {"discrepancy_type": discrepancy.get("type", "unknown"), "field": discrepancy.get("field", "unknown"), "classification": "error", "confidence": 0.0, "reasoning": "extraction_confidence must be a dict", "recommended_action": "manual_review", "duration_ms": round(duration_ms, 2)}

    logger.debug("discrepancy_classify_start", discrepancy_type=discrepancy.get("type"), field=discrepancy.get("field"))

    try:
        result = classify_discrepancy(discrepancy, extraction_confidence)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("discrepancy_classified", discrepancy_type=result["discrepancy_type"], classification=result["classification"], confidence=round(result["confidence"], 2), recommended_action=result["recommended_action"], duration_ms=round(duration_ms, 2))
        result["duration_ms"] = round(duration_ms, 2)
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("discrepancy_classify_error", discrepancy_type=discrepancy.get("type"), error=str(e), duration_ms=round(duration_ms, 2))
        return {"discrepancy_type": discrepancy.get("type", "unknown"), "field": discrepancy.get("field", "unknown"), "classification": "error", "confidence": 0.0, "reasoning": f"Classification failed: {e}", "recommended_action": "manual_review", "duration_ms": round(duration_ms, 2)}


@tool
def applicant_clarify_tool(
    discrepancy: Any = None,
    applicant_context: Any = None,
) -> dict:
    """Generate a clarification question for the applicant."""
    start = time.perf_counter()

    if discrepancy is None or not isinstance(discrepancy, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="applicant_clarify", reason="discrepancy must be a dict")
        return {"question": "We need additional information to process your application. Please contact support.", "field": "unknown", "discrepancy_type": "unknown", "priority": "high", "confidence": 0.0, "classification": "error", "error": "discrepancy must be a dict", "duration_ms": round(duration_ms, 2)}

    if applicant_context is None or not isinstance(applicant_context, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="applicant_clarify", reason="applicant_context must be a dict")
        return {"question": "We need additional information to process your application. Please contact support.", "field": discrepancy.get("field", "unknown"), "discrepancy_type": discrepancy.get("type", "unknown"), "priority": "high", "confidence": 0.0, "classification": "error", "error": "applicant_context must be a dict", "duration_ms": round(duration_ms, 2)}

    logger.debug("applicant_clarify_start", discrepancy_type=discrepancy.get("type"), applicant_id=applicant_context.get("applicant_id"))

    try:
        question = format_clarification_question(discrepancy, applicant_context)
        priority = PRIORITY_MAP.get(discrepancy.get("type", "unknown"), "medium")
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("clarification_question_generated", discrepancy_type=discrepancy.get("type"), priority=priority, applicant_id=applicant_context.get("applicant_id"), duration_ms=round(duration_ms, 2))
        return {
            "question": question,
            "field": discrepancy.get("field", "unknown"),
            "discrepancy_type": discrepancy.get("type", "unknown"),
            "priority": priority,
            "confidence": 1.0,
            "applicant_id": applicant_context.get("applicant_id"),
            "application_id": applicant_context.get("application_id"),
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("applicant_clarify_error", discrepancy_type=discrepancy.get("type"), error=str(e), duration_ms=round(duration_ms, 2))
        return {"question": "We need additional information to process your application. Please contact support.", "field": discrepancy.get("field", "unknown"), "discrepancy_type": discrepancy.get("type", "unknown"), "priority": "high", "confidence": 0.0, "classification": "error", "error": str(e), "duration_ms": round(duration_ms, 2)}


@tool
def validation_confidence_tool(
    validation_results: Any = None,
    discrepancies: Any = None,
) -> dict:
    """Compute overall validation confidence score."""
    start = time.perf_counter()

    if validation_results is None or not isinstance(validation_results, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="validation_confidence", reason="validation_results must be a dict")
        return {"overall_confidence": 0.0, "recommendation": "escalate", "unresolved_count": 0, "critical_count": 0, "confidence": 0.0, "summary": {"error": "validation_results must be a dict"}, "duration_ms": round(duration_ms, 2)}

    if discrepancies is None or not isinstance(discrepancies, list):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="validation_confidence", reason="discrepancies must be a list")
        return {"overall_confidence": 0.0, "recommendation": "escalate", "unresolved_count": 0, "critical_count": 0, "confidence": 0.0, "summary": {"error": "discrepancies must be a list"}, "duration_ms": round(duration_ms, 2)}

    logger.debug("validation_confidence_start", discrepancy_count=len(discrepancies))

    try:
        result = compute_validation_confidence(validation_results, discrepancies)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("validation_confidence_complete", overall_confidence=round(result["overall_confidence"], 2), recommendation=result["recommendation"], unresolved_count=result["unresolved_count"], critical_count=result["critical_count"], duration_ms=round(duration_ms, 2))
        result["duration_ms"] = round(duration_ms, 2)
        result["confidence"] = round(result.get("overall_confidence", 0.0), 2)
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("validation_confidence_error", error=str(e), duration_ms=round(duration_ms, 2))
        return {"overall_confidence": 0.0, "recommendation": "escalate", "unresolved_count": 0, "critical_count": 0, "confidence": 0.0, "summary": {"error": str(e)}, "duration_ms": round(duration_ms, 2)}
