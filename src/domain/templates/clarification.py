"""Clarification question templates for validation discrepancies."""

from typing import Any


CLARIFICATION_TEMPLATES: dict[str, str] = {
    "name_mismatch": (
        "We noticed a slight difference in how your name appears on your documents. "
        "On your {doc_a}, it shows '{name_a}', "
        "but on your {doc_b}, it shows '{name_b}'. "
        "Could you confirm your full legal name as it appears on your Emirates ID?"
    ),
    "income_mismatch": (
        "There's a discrepancy in the income information you provided. "
        "Your {doc_a} shows {income_a:,.2f} AED, "
        "but your {doc_b} shows {income_b:,.2f} AED. "
        "Could you clarify your total monthly income?"
    ),
    "identity_mismatch": (
        "We found inconsistent identity numbers across your documents. "
        "This is a critical issue that needs to be resolved. "
        "Please verify your Emirates ID number and ensure all documents match."
    ),
    "address_mismatch": (
        "We noticed your address appears differently on your documents. "
        "Could you confirm your current residential address?"
    ),
    "default": (
        "We need clarification on some information in your application. "
        "Please review your documents and ensure all information is consistent."
    ),
}

PRIORITY_MAP: dict[str, str] = {
    "identity_mismatch": "critical",
    "income_mismatch": "high",
    "name_mismatch": "medium",
    "address_mismatch": "low",
}


def format_clarification_question(
    discrepancy: dict[str, Any],
    applicant_context: dict[str, Any],
) -> str:
    """Generate a clarification question for a discrepancy using templates.

    Args:
        discrepancy: Discrepancy dict with type, field, values, and classification.
        applicant_context: Dict with applicant_id, application_id, support_category.

    Returns:
        Formatted clarification question string.
    """
    disc_type = discrepancy.get("type", "unknown")
    values = discrepancy.get("values", {})
    template = CLARIFICATION_TEMPLATES.get(disc_type, CLARIFICATION_TEMPLATES["default"])

    if disc_type == "name_mismatch":
        doc_types = list(values.keys())
        name_values = list(values.values())
        return template.format(
            doc_a=doc_types[0],
            name_a=name_values[0],
            doc_b=doc_types[1],
            name_b=name_values[1],
        )
    elif disc_type == "income_mismatch":
        doc_types = list(values.keys())
        income_values = list(values.values())
        return template.format(
            doc_a=doc_types[0],
            income_a=income_values[0],
            doc_b=doc_types[1],
            income_b=income_values[1],
        )
    return template
