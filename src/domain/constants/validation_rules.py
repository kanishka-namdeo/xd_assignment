"""Validation rule definitions extracted from gate implementations."""

# ---------------------------------------------------------------------------
# Required fields per document type (from document_integrity gate)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: dict[str, list[str]] = {
    "emirates_id": [
        "identity_number", "full_name_en", "nationality",
        "date_of_birth", "gender", "expiry_date",
    ],
    "bank_statement": [
        "bank_name", "account_holder_name", "account_number",
        "currency", "statement_period_start", "statement_period_end",
        "opening_balance", "closing_balance", "total_debits", "total_credits",
    ],
    "credit_report": [
        "cb_subject_id", "identity_number", "full_name",
        "credit_score", "risk_band",
        "total_active_accounts", "total_closed_accounts",
        "total_outstanding_balance",
    ],
    "assets_liabilities": [
        "applicant_name", "statement_date",
        "total_assets", "total_liabilities", "net_worth",
    ],
    "resume": [
        "full_name", "work_experience", "total_positions",
    ],
    "application_form": [
        "applicant_name", "identity_number", "date_of_birth",
        "nationality", "contact_phone", "employment_status",
        "total_monthly_income",
    ],
}

# ---------------------------------------------------------------------------
# Validation thresholds
# ---------------------------------------------------------------------------

VALIDATION_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence to pass gate
VALIDATION_PASS_THRESHOLD = 0.80  # Confidence for clean pass
VALIDATION_BORDERLINE_THRESHOLD = 0.70  # Confidence for borderline pass

NAME_SIMILARITY_THRESHOLD = 0.6  # Jaccard similarity threshold for name matching

CREDIT_SCORE_MIN = 300
CREDIT_SCORE_MAX = 900

# ---------------------------------------------------------------------------
# Cross-document consistency checks
# ---------------------------------------------------------------------------

CONSISTENCY_CHECKS = ["identity_match", "name_consistency", "income_consistency", "address_consistency"]

# ---------------------------------------------------------------------------
# Hard eligibility rules (from eligibility_rules gate)
# ---------------------------------------------------------------------------

HARD_ELIGIBILITY_CHECKS = [
    "emirates_id_validity",
    "credit_score_range",
    "identity_consistency",
    "bank_statement_reconciliation",
    "required_documents_present",
    "validation_confidence",
]

# Always-required documents for hard eligibility (subset used when category unknown)
ALWAYS_REQUIRED_DOCUMENTS = ["emirates_id", "application_form"]
