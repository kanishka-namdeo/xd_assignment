"""Deterministic document integrity validation gate.

Validates extracted data against hard constraints per document type.
No LLM calls — pure Python, <5ms target per gate invocation.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.utils.emirates_id import validate as emirates_id_validate

logger = structlog.get_logger(__name__)

_TOLERANCE = Decimal("0.01")

# ---------------------------------------------------------------------------
# Required fields per document type (aligned with extraction schema models)
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, list[str]] = {
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


def _to_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(value: Any) -> date | None:
    """Parse a date from string or return date object as-is."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Per-document validators
# ---------------------------------------------------------------------------

def _validate_emirates_id(data: dict) -> list[str]:
    errors: list[str] = []

    identity_number = data.get("identity_number")
    if identity_number and not emirates_id_validate(str(identity_number)):
        errors.append(
            f"Emirates ID checksum or format invalid: {identity_number}"
        )

    expiry = _to_date(data.get("expiry_date"))
    if expiry and expiry < date.today():
        errors.append(f"Emirates ID expired: {expiry}")

    if data.get("is_mrz_verified") is False:
        errors.append("MRZ zone not verified on Emirates ID")

    return errors


def _validate_bank_statement(data: dict) -> list[str]:
    errors: list[str] = []

    opening = _to_decimal(data.get("opening_balance"))
    closing = _to_decimal(data.get("closing_balance"))
    credits = _to_decimal(data.get("total_credits"))
    debits = _to_decimal(data.get("total_debits"))

    if all(v is not None for v in (opening, closing, credits, debits)):
        expected_closing = opening + credits - debits
        if abs(expected_closing - closing) > _TOLERANCE:
            errors.append(
                f"Balance reconciliation failed: "
                f"{opening} + {credits} - {debits} = {expected_closing}, "
                f"but closing_balance = {closing}"
            )

    start = _to_date(data.get("statement_period_start"))
    end = _to_date(data.get("statement_period_end"))
    if start and end and start >= end:
        errors.append(
            f"Statement period invalid: start {start} >= end {end}"
        )

    today = date.today()
    transactions = data.get("transactions", [])
    if isinstance(transactions, list):
        for txn in transactions:
            txn_date = _to_date(txn.get("transaction_date"))
            if txn_date and txn_date > today:
                errors.append(f"Future transaction date found: {txn_date}")
                break

    currency = data.get("currency", "AED")
    if currency != "AED":
        errors.append(f"Primary currency is {currency}, expected AED")

    return errors


def _validate_credit_report(data: dict) -> list[str]:
    errors: list[str] = []

    score = data.get("credit_score")
    if score is not None:
        try:
            score_int = int(score)
            if score_int < 300 or score_int > 900:
                errors.append(f"Credit score {score_int} outside valid range 300-900")
        except (ValueError, TypeError):
            errors.append(f"Credit score not a valid integer: {score}")

    total_outstanding = _to_decimal(data.get("total_outstanding_balance"))
    facilities = data.get("active_facilities", [])
    if total_outstanding is not None and isinstance(facilities, list) and facilities:
        facility_sum = Decimal("0")
        for f in facilities:
            bal = _to_decimal(f.get("current_balance"))
            if bal is not None:
                facility_sum += bal
        if abs(total_outstanding - facility_sum) > _TOLERANCE:
            errors.append(
                f"Total outstanding {total_outstanding} != sum of facility "
                f"balances {facility_sum}"
            )

    payment_history = data.get("payment_history", [])
    today = date.today()
    if isinstance(payment_history, list):
        for entry in payment_history:
            entry_date = _to_date(entry.get("date"))
            if entry_date and entry_date > today:
                errors.append(f"Future payment history date: {entry_date}")
                break

    return errors


def _validate_assets_liabilities(data: dict) -> list[str]:
    errors: list[str] = []

    total_assets = _to_decimal(data.get("total_assets"))
    total_liabilities = _to_decimal(data.get("total_liabilities"))
    net_worth = _to_decimal(data.get("net_worth"))

    if total_assets is not None and total_assets < 0:
        errors.append(f"total_assets is negative: {total_assets}")
    if total_liabilities is not None and total_liabilities < 0:
        errors.append(f"total_liabilities is negative: {total_liabilities}")

    if all(v is not None for v in (total_assets, total_liabilities, net_worth)):
        expected_nw = total_assets - total_liabilities
        if abs(expected_nw - net_worth) > _TOLERANCE:
            errors.append(
                f"Net worth reconciliation failed: "
                f"{total_assets} - {total_liabilities} = {expected_nw}, "
                f"but net_worth = {net_worth}"
            )

    stmt_date = _to_date(data.get("statement_date"))
    if stmt_date:
        six_months_ago = date.today() - timedelta(days=180)
        if stmt_date < six_months_ago:
            errors.append(
                f"Assets/liabilities statement date {stmt_date} is older "
                f"than 6 months"
            )

    asset_categories = [
        "cash_and_deposits", "savings_accounts", "investment_accounts",
        "retirement_accounts", "real_estate_value", "vehicle_value",
        "other_assets",
    ]
    if total_assets is not None:
        cat_sum = Decimal("0")
        for cat in asset_categories:
            val = _to_decimal(data.get(cat))
            if val is not None:
                cat_sum += val
        if abs(cat_sum - total_assets) > _TOLERANCE:
            errors.append(
                f"Asset categories sum {cat_sum} != total_assets {total_assets}"
            )

    return errors


def _validate_resume(data: dict) -> list[str]:
    errors: list[str] = []
    today = date.today()

    work_experience = data.get("work_experience", [])
    if not isinstance(work_experience, list):
        work_experience = []

    for exp in work_experience:
        start = _to_date(exp.get("start_date"))
        end_raw = exp.get("end_date")
        is_current = exp.get("is_current", False)

        if end_raw is None or str(end_raw).lower() in ("present", "current", ""):
            end = None
        else:
            end = _to_date(end_raw)

        if start and end and start >= end:
            errors.append(
                f"Work experience date invalid: start {start} >= end {end} "
                f"at {exp.get('company', 'unknown')}"
            )

        if end and end > today:
            errors.append(
                f"Future end_date in work experience: {end} "
                f"at {exp.get('company', 'unknown')}"
            )

        if start and start > today:
            errors.append(
                f"Future start_date in work experience: {start} "
                f"at {exp.get('company', 'unknown')}"
            )

        if is_current and end is not None:
            errors.append(
                f"Current position has non-null end_date: {end} "
                f"at {exp.get('company', 'unknown')}"
            )

    return errors


def _validate_application_form(data: dict) -> list[str]:
    errors: list[str] = []

    total_income = _to_decimal(data.get("total_monthly_income"))
    salary = _to_decimal(data.get("monthly_salary"))
    other = _to_decimal(data.get("other_income"))

    if all(v is not None for v in (total_income, salary, other)):
        expected = salary + other
        if abs(total_income - expected) > _TOLERANCE:
            errors.append(
                f"Total monthly income {total_income} != "
                f"monthly_salary ({salary}) + other_income ({other}) = {expected}"
            )

    return errors


_VALIDATORS: dict[str, Any] = {
    "emirates_id": _validate_emirates_id,
    "bank_statement": _validate_bank_statement,
    "credit_report": _validate_credit_report,
    "assets_liabilities": _validate_assets_liabilities,
    "resume": _validate_resume,
    "application_form": _validate_application_form,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_document_integrity(
    extracted_data: dict,
    document_type: str,
) -> tuple[bool, list[str]]:
    """Deterministic validation of extracted data for a single document.

    Args:
        extracted_data: The extracted data dictionary for the document.
        document_type: One of the supported document type keys.

    Returns:
        (is_valid, errors) — errors is empty when is_valid is True.
    """
    errors: list[str] = []

    required = _REQUIRED_FIELDS.get(document_type, [])
    for field in required:
        value = extracted_data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"Required field missing or empty: {field}")

    validator = _VALIDATORS.get(document_type)
    if validator:
        errors.extend(validator(extracted_data))
    else:
        logger.warning("No integrity validator for document_type=%s", document_type)

    is_valid = len(errors) == 0
    if is_valid:
        logger.info("integrity_passed", event="integrity_passed", document_type=document_type)
    else:
        logger.warning("integrity_failed", event="integrity_failed", document_type=document_type, error_count=len(errors), errors=errors)
    return is_valid, errors
