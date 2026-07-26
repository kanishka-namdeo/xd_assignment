"""Confidence scoring for extracted documents.

Pure domain logic for computing field-level and overall confidence scores.
No I/O operations.
"""

from typing import Any


class ConfidenceResult:
    """Result of confidence computation."""

    def __init__(
        self,
        overall_confidence: float,
        routing_decision: str,
        field_confidences: dict[str, float],
        low_confidence_fields: list[str],
    ) -> None:
        self.overall_confidence = overall_confidence
        self.routing_decision = routing_decision
        self.field_confidences = field_confidences
        self.low_confidence_fields = low_confidence_fields


def compute_confidence(
    extracted_data: Any,
    raw_confidence: float | None = None,
    document_type: str | None = None,
) -> ConfidenceResult:
    """Compute confidence score for extracted data.

    Args:
        extracted_data: Object with extracted fields (dict-like or object with attributes).
        raw_confidence: Raw confidence from the parser (if available).
        document_type: Type of document for type-specific scoring.

    Returns:
        ConfidenceResult with overall_confidence, routing_decision,
        field_confidences, and low_confidence_fields.
    """
    field_confidences: dict[str, float] = {}
    low_confidence_fields: list[str] = []

    # Get field-level confidence if available
    if hasattr(extracted_data, "field_confidences"):
        field_confidences = dict(extracted_data.field_confidences)
        low_confidence_fields = list(getattr(extracted_data, "low_confidence_fields", []))
    elif hasattr(extracted_data, "__dict__"):
        # Compute basic confidence from field completeness
        data_dict = extracted_data.__dict__
        total_fields = len([k for k in data_dict if not k.startswith("_")])
        filled_fields = len([k for k in data_dict if not k.startswith("_") and data_dict.get(k) is not None])
        if total_fields > 0:
            completeness = filled_fields / total_fields
            field_confidences["completeness"] = completeness

    # Use raw confidence as base, fall back to computed
    base_confidence = raw_confidence or 0.85

    # Penalize for low-confidence fields
    penalty = len(low_confidence_fields) * 0.05
    overall = max(0.0, base_confidence - penalty)

    # Determine routing decision
    if overall >= 0.90:
        routing_decision = "auto_approve"
    elif overall >= 0.75:
        routing_decision = "spot_check"
    elif overall >= 0.60:
        routing_decision = "full_review"
    else:
        routing_decision = "re_extract"

    return ConfidenceResult(
        overall_confidence=overall,
        routing_decision=routing_decision,
        field_confidences=field_confidences,
        low_confidence_fields=low_confidence_fields,
    )
