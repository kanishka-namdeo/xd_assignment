"""Discrepancy classification logic.

Classifies discrepancies as OCR errors, real discrepancies, or ambiguous.
Pure domain logic with no I/O operations.
"""

from typing import Any


def classify_discrepancy(
    discrepancy: dict[str, Any],
    extraction_confidence: dict[str, float],
) -> dict[str, Any]:
    """Classify whether a discrepancy is an OCR error or a real inconsistency.

    Args:
        discrepancy: Discrepancy dict with type, field, values, and optional similarity/variance.
        extraction_confidence: Dict mapping document_type -> extraction confidence score.

    Returns:
        Dict with classification, confidence, reasoning, and recommended_action.
    """
    disc_type = discrepancy.get("type", "unknown")
    avg_confidence = (
        sum(extraction_confidence.values()) / len(extraction_confidence)
        if extraction_confidence else 0.0
    )

    classification = "ambiguous"
    confidence = 0.5
    reasoning = ""
    recommended_action = "manual_review"

    if disc_type == "name_mismatch":
        similarity = discrepancy.get("similarity", 0.0)
        if similarity >= 0.8 and avg_confidence >= 0.85:
            classification = "ocr_error"
            confidence = 0.85
            reasoning = (
                f"High name similarity ({similarity:.2f}) and high extraction confidence "
                f"({avg_confidence:.2f}). Likely OCR variation (e.g., middle initial vs full name)."
            )
            recommended_action = "accept_with_note"
        elif similarity < 0.6:
            classification = "real_discrepancy"
            confidence = 0.90
            reasoning = (
                f"Low name similarity ({similarity:.2f}). "
                f"Likely real discrepancy requiring clarification."
            )
            recommended_action = "request_clarification"

    elif disc_type == "income_mismatch":
        variance_pct = discrepancy.get("variance_pct", 0.0)
        if variance_pct <= 10 and avg_confidence >= 0.85:
            classification = "ocr_error"
            confidence = 0.80
            reasoning = (
                f"Small income variance ({variance_pct:.1f}%) with high extraction confidence. "
                f"Likely OCR rounding or formatting difference."
            )
            recommended_action = "accept_with_note"
        elif variance_pct > 20:
            classification = "real_discrepancy"
            confidence = 0.90
            reasoning = (
                f"Large income variance ({variance_pct:.1f}%). "
                f"Likely real discrepancy requiring clarification."
            )
            recommended_action = "request_clarification"

    elif disc_type == "identity_mismatch":
        classification = "real_discrepancy"
        confidence = 0.95
        reasoning = "Identity number mismatch is critical and unlikely to be OCR error."
        recommended_action = "escalate"

    elif disc_type == "address_mismatch":
        if avg_confidence >= 0.90:
            classification = "real_discrepancy"
            confidence = 0.75
            reasoning = (
                "Address mismatch with high extraction confidence. "
                "Applicant may have moved or used different address formats."
            )
            recommended_action = "request_clarification"
        else:
            classification = "ambiguous"
            confidence = 0.60
            reasoning = (
                "Address mismatch with moderate extraction confidence. "
                "Could be OCR error or real discrepancy."
            )
            recommended_action = "request_clarification"

    return {
        "discrepancy_type": disc_type,
        "field": discrepancy.get("field", "unknown"),
        "classification": classification,
        "confidence": confidence,
        "reasoning": reasoning,
        "recommended_action": recommended_action,
    }
