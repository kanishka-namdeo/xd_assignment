"""Required documents per support category."""

REQUIRED_DOCUMENTS: dict[str, list[str]] = {
    "divorced": ["emirates_id", "bank_statement", "credit_report", "application_form"],
    "abandoned": ["emirates_id", "bank_statement", "credit_report", "application_form"],
    "unknown_parentage": ["emirates_id", "bank_statement", "application_form"],
    "health_disability": ["emirates_id", "bank_statement", "credit_report", "application_form", "resume"],
}

DEFAULT_REQUIRED_DOCUMENTS: list[str] = ["emirates_id", "bank_statement", "credit_report", "application_form"]
