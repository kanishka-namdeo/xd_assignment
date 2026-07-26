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
    extracted_data: dict,
    document_type: str,
) -> dict:
    """Validate extracted data within a single document for internal consistency."""
    start = time.perf_counter()
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
        }
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("per_document_validation_error", document_type=document_type, error=str(e), duration_ms=round(duration_ms, 2))
        return {"document_type": document_type, "validation_results": [], "overall_status": "error", "confidence": 0.0, "errors": [str(e)]}


@tool
def cross_document_compare_tool(
    extracted_data: dict[str, dict],
    comparison_type: str,
) -> dict:
    """Compare fields across multiple documents for consistency."""
    start = time.perf_counter()
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
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("cross_document_compare_error", comparison_type=comparison_type, error=str(e), duration_ms=round(duration_ms, 2))
        return {"comparison_type": comparison_type, "results": [], "overall_match": False, "discrepancies": [], "confidence": 0.0, "error": str(e)}


@tool
def discrepancy_classify_tool(
    discrepancy: dict,
    extraction_confidence: dict[str, float],
) -> dict:
    """Classify whether a discrepancy is an OCR error or a real inconsistency."""
    start = time.perf_counter()
    logger.debug("discrepancy_classify_start", discrepancy_type=discrepancy.get("type"), field=discrepancy.get("field"))

    try:
        result = classify_discrepancy(discrepancy, extraction_confidence)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("discrepancy_classified", discrepancy_type=result["discrepancy_type"], classification=result["classification"], confidence=round(result["confidence"], 2), recommended_action=result["recommended_action"], duration_ms=round(duration_ms, 2))
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("discrepancy_classify_error", discrepancy_type=discrepancy.get("type"), error=str(e), duration_ms=round(duration_ms, 2))
        return {"discrepancy_type": discrepancy.get("type", "unknown"), "field": discrepancy.get("field", "unknown"), "classification": "error", "confidence": 0.0, "reasoning": f"Classification failed: {e}", "recommended_action": "manual_review"}


@tool
def applicant_clarify_tool(
    discrepancy: dict,
    applicant_context: dict,
) -> dict:
    """Generate a clarification question for the applicant."""
    start = time.perf_counter()
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
            "applicant_id": applicant_context.get("applicant_id"),
            "application_id": applicant_context.get("application_id"),
        }
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("applicant_clarify_error", discrepancy_type=discrepancy.get("type"), error=str(e), duration_ms=round(duration_ms, 2))
        return {"question": "We need additional information to process your application. Please contact support.", "field": discrepancy.get("field", "unknown"), "discrepancy_type": discrepancy.get("type", "unknown"), "priority": "high", "classification": "error", "error": str(e)}


@tool
def validation_confidence_tool(
    validation_results: dict,
    discrepancies: list[dict],
) -> dict:
    """Compute overall validation confidence score."""
    start = time.perf_counter()
    logger.debug("validation_confidence_start", discrepancy_count=len(discrepancies))

    try:
        result = compute_validation_confidence(validation_results, discrepancies)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("validation_confidence_complete", overall_confidence=round(result["overall_confidence"], 2), recommendation=result["recommendation"], unresolved_count=result["unresolved_count"], critical_count=result["critical_count"], duration_ms=round(duration_ms, 2))
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("validation_confidence_error", error=str(e), duration_ms=round(duration_ms, 2))
        return {"overall_confidence": 0.0, "recommendation": "escalate", "unresolved_count": 0, "critical_count": 0, "summary": {"error": str(e)}}
