"""Deterministic hard eligibility rules gate.

Validates hard eligibility constraints that must pass regardless of LLM judgment.
No LLM calls — pure Python, <5ms target per gate invocation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from src.utils.emirates_id import validate as emirates_id_validate

logger = structlog.get_logger(__name__)


def _to_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _normalize_identity(value: Any) -> str:
    """Normalize identity number by removing dashes and spaces."""
    if value is None:
        return ""
    return str(value).replace("-", "").replace(" ", "").strip()


def _check_emirates_id_validity(extracted_data: dict[str, dict]) -> str | None:
    """Check Emirates ID validity and expiry."""
    if "emirates_id" not in extracted_data:
        return "Emirates ID not present"

    eid_data = extracted_data["emirates_id"]
    identity_number = eid_data.get("identity_number")

    if not identity_number:
        return "Emirates ID identity_number is missing"

    if not emirates_id_validate(str(identity_number)):
        return f"Emirates ID checksum or format invalid: {identity_number}"

    expiry_str = eid_data.get("expiry_date")
    if expiry_str:
        try:
            from datetime import datetime
            if isinstance(expiry_str, str):
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            elif isinstance(expiry_str, date):
                expiry = expiry_str
            else:
                return f"Invalid expiry_date format: {expiry_str}"

            if expiry < date.today():
                return f"Emirates ID expired: {expiry}"
        except Exception as e:
            return f"Failed to parse expiry_date: {e}"

    return None


def _check_credit_score_range(extracted_data: dict[str, dict]) -> str | None:
    """Check credit score is within valid range 300-900."""
    if "credit_report" not in extracted_data:
        return None  # Credit report not required

    credit_data = extracted_data["credit_report"]
    score = credit_data.get("credit_score")

    if score is None:
        return "Credit score is missing from credit report"

    try:
        score_int = int(score)
        if score_int < 300 or score_int > 900:
            return f"Credit score {score_int} outside valid range 300-900"
    except (ValueError, TypeError):
        return f"Credit score is not a valid integer: {score}"

    return None


def _check_identity_consistency(extracted_data: dict[str, dict]) -> str | None:
    """Check identity number is consistent across documents."""
    identities: dict[str, str] = {}

    if "emirates_id" in extracted_data:
        eid = extracted_data["emirates_id"].get("identity_number")
        if eid:
            identities["emirates_id"] = _normalize_identity(eid)

    if "credit_report" in extracted_data:
        cr = extracted_data["credit_report"].get("identity_number")
        if cr:
            identities["credit_report"] = _normalize_identity(cr)

    if "application_form" in extracted_data:
        form = extracted_data["application_form"].get("identity_number")
        if form:
            identities["application_form"] = _normalize_identity(form)

    if len(identities) < 2:
        return None  # Not enough data to compare

    unique_values = set(identities.values())
    if len(unique_values) > 1:
        details = ", ".join(f"{k}={v}" for k, v in identities.items())
        return f"Identity number mismatch across documents: {details}"

    return None


def _check_bank_statement_reconciliation(extracted_data: dict[str, dict]) -> str | None:
    """Check bank statement balance reconciliation."""
    if "bank_statement" not in extracted_data:
        return None  # Bank statement not required

    bank_data = extracted_data["bank_statement"]

    opening = _to_decimal(bank_data.get("opening_balance"))
    closing = _to_decimal(bank_data.get("closing_balance"))
    credits = _to_decimal(bank_data.get("total_credits"))
    debits = _to_decimal(bank_data.get("total_debits"))

    if any(v is None for v in (opening, closing, credits, debits)):
        return "Bank statement missing required balance fields"

    expected_closing = opening + credits - debits
    tolerance = Decimal("0.01")

    if abs(expected_closing - closing) > tolerance:
        return (
            f"Bank statement balance reconciliation failed: "
            f"{opening} + {credits} - {debits} = {expected_closing}, "
            f"but closing_balance = {closing}"
        )

    return None


def _check_required_documents_present(
    extracted_data: dict[str, dict],
    validation_results: dict,
) -> str | None:
    """Check all required documents are present and validated."""
    # For now, assume emirates_id and application_form are always required
    required = ["emirates_id", "application_form"]

    for doc_type in required:
        if doc_type not in extracted_data:
            return f"Required document not present: {doc_type}"
        if doc_type not in validation_results:
            return f"Required document not validated: {doc_type}"

    return None


def _check_validation_confidence(validation_results: dict) -> str | None:
    """Check that validation confidence is >= 0.70."""
    for doc_type, result in validation_results.items():
        if isinstance(result, dict):
            confidence = result.get("confidence")
            if confidence is not None:
                try:
                    conf_float = float(confidence)
                    if conf_float < 0.70:
                        return (
                            f"Validation confidence for {doc_type} is {conf_float:.2f}, "
                            f"below threshold 0.70"
                        )
                except (ValueError, TypeError):
                    pass

    return None


def check_hard_eligibility_rules(
    extracted_data: dict[str, dict],
    validation_results: dict,
) -> tuple[bool, str | None]:
    """Deterministic validation of hard eligibility rules.

    Args:
        extracted_data: Dict mapping document_type -> extracted data dict.
        validation_results: Dict mapping document_type -> validation result.

    Returns:
        (passes, failure_reason) — failure_reason is None when passes is True.
    """
    checks = [
        ("Emirates ID validity", _check_emirates_id_validity),
        ("Credit score range", _check_credit_score_range),
        ("Identity consistency", _check_identity_consistency),
        ("Bank statement reconciliation", _check_bank_statement_reconciliation),
        ("Required documents present", lambda _: _check_required_documents_present(extracted_data, validation_results)),
        ("Validation confidence", lambda _: _check_validation_confidence(validation_results)),
    ]

    for check_name, check_func in checks:
        try:
            failure = check_func(extracted_data)
            logger.debug("eligibility_check", event="eligibility_check", check=check_name, passed=failure is None, failure_reason=failure)
            if failure:
                return False, failure
        except Exception as e:
            logger.exception("eligibility_check_error", event="eligibility_check_error", check=check_name, error=str(e))
            return False, f"Error running {check_name}: {e}"

    logger.info("eligibility_passed", event="eligibility_passed", checks_completed=len(checks))
    return True, None
