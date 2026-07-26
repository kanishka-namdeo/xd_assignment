"""Validation confidence aggregation.

Computes overall validation confidence from per-document validation results
and cross-document validation results. Pure domain logic with no I/O.
"""

from typing import Any


def compute_validation_confidence(
    validation_results: dict[str, Any],
    discrepancies: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute overall validation confidence score.

    Args:
        validation_results: Dict with per_document_validation and cross_document_validation results.
        discrepancies: List of discrepancy dicts with type, classification, confidence, and resolution_status.

    Returns:
        Dict with overall_confidence, recommendation, unresolved_count, and summary.
    """
    confidences: list[float] = []

    per_doc_results = validation_results.get("per_document_validation", {})
    for _doc_id, result in per_doc_results.items():
        if isinstance(result, dict) and "confidence" in result:
            confidences.append(result["confidence"])

    cross_doc_results = validation_results.get("cross_document_validation", {})
    for _check_type, result in cross_doc_results.items():
        if isinstance(result, dict) and "confidence" in result:
            confidences.append(result["confidence"])

    base_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    unresolved_discrepancies = [
        d for d in discrepancies
        if d.get("resolution_status") == "unresolved"
    ]
    unresolved_count = len(unresolved_discrepancies)

    critical_discrepancies = [
        d for d in unresolved_discrepancies
        if d.get("discrepancy_type") in {"identity_mismatch", "income_mismatch"}
    ]

    confidence_penalty = unresolved_count * 0.05
    critical_penalty = len(critical_discrepancies) * 0.10
    overall_confidence = max(0.0, base_confidence - confidence_penalty - critical_penalty)

    if overall_confidence >= 0.90 and unresolved_count == 0:
        recommendation = "proceed_to_decision"
    elif overall_confidence >= 0.80:
        recommendation = "proceed_to_review"
    elif overall_confidence >= 0.70:
        recommendation = "manual_review"
    else:
        recommendation = "escalate"

    summary = {
        "total_documents_validated": len(per_doc_results),
        "total_cross_doc_checks": len(cross_doc_results),
        "total_discrepancies": len(discrepancies),
        "unresolved_discrepancies": unresolved_count,
        "critical_discrepancies": len(critical_discrepancies),
        "base_confidence": round(base_confidence, 2),
    }

    return {
        "overall_confidence": round(overall_confidence, 2),
        "recommendation": recommendation,
        "unresolved_count": unresolved_count,
        "critical_count": len(critical_discrepancies),
        "summary": summary,
    }
