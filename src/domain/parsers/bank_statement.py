"""Bank statement document parser."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_bank_statement(raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse bank statement data from extracted text.

    Args:
        raw_text: Plain text extracted from the bank statement.
        raw_result: Raw parser result object (ExtractionResult for PDFs).

    Returns:
        Dict with bank_name, account_holder_name, account_number, iban,
        account_type, currency, statement_period, balances, transactions.
    """
    text = _get_text(raw_text, raw_result)

    if not text or len(text.strip()) < 5:
        return _empty_result()

    logger.debug("parsing_bank_statement", text_length=len(text))

    opening = _extract_balance(text, r"(?:Opening Balance|الرصيد الافتتاحي)")
    closing = _extract_balance(text, r"(?:Closing Balance|الرصيد الختامي)")

    return {
        "bank_name": _extract_bank_name(text),
        "account_holder_name": _extract_account_holder(text),
        "account_number": _extract_account_number(text),
        "iban": _extract_iban(text),
        "account_type": _extract_account_type(text),
        "currency": "AED",
        "statement_period_start": _extract_period_start(text),
        "statement_period_end": _extract_period_end(text),
        "opening_balance": opening,
        "closing_balance": closing,
        "total_debits": _extract_total_debits(text),
        "total_credits": _extract_total_credits(text),
        "is_balance_reconciled": _check_reconciliation(opening, closing, text),
        "transactions": [],
        "transaction_count": _count_transactions(text),
    }


def _get_text(raw_text: str, raw_result: Any) -> str:
    """Get text from raw_text or raw_result."""
    if raw_text and len(raw_text.strip()) > 5:
        return raw_text
    if raw_result is not None and hasattr(raw_result, "raw_extracted_data"):
        data = raw_result.raw_extracted_data
        if isinstance(data, dict) and "markdown" in data:
            return data["markdown"] or ""
        return str(data)
    return ""


def _extract_bank_name(text: str) -> str | None:
    """Extract bank name from statement text."""
    # Common UAE banks
    banks = [
        "Emirates NBD", "EmiratesNBD", "First Abu Dhabi Bank", "FAB",
        "Abu Dhabi Commercial Bank", "ADCB", "Mashreq", "Mashreqbank",
        "Dubai Islamic Bank", "DIB", "Commercial Bank of Dubai", "CBD",
        "HSBC", "Standard Chartered", "Barclays",
    ]
    for bank in banks:
        if bank.lower() in text.lower():
            return bank
    # Generic pattern
    match = re.search(r"(?:Bank|بنك)\s+([A-Za-z][A-Za-z\s]+?)(?:\n|$)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_account_holder(text: str) -> str | None:
    """Extract account holder name."""
    match = re.search(
        r"(?:Account Holder|Account Name|Holder Name|صاحب الحساب)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_account_number(text: str) -> str | None:
    """Extract account number (typically 8-16 digits)."""
    match = re.search(r"(?:Account Number|Account No|A/C No|رقم الحساب)\s*[:\-]?\s*(\d{8,16})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback: look for any 8-16 digit number
    match = re.search(r"\b(\d{8,16})\b", text)
    return match.group(1) if match else None


def _extract_iban(text: str) -> str | None:
    """Extract IBAN (AE + 21 digits)."""
    match = re.search(r"(AE\d{21})", text)
    if match:
        return match.group(1)
    match = re.search(r"(?:IBAN|iban)\s*[:\-]?\s*(AE\d{21})", text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_account_type(text: str) -> str | None:
    """Extract account type."""
    types = ["Savings", "Current", "Salary", "Investment", "Deposit"]
    for acc_type in types:
        if acc_type.lower() in text.lower():
            return acc_type
    return None


def _extract_period_start(text: str) -> date | None:
    """Extract statement period start date."""
    match = re.search(
        r"(?:From|Period Start|Statement From)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))
    return None


def _extract_period_end(text: str) -> date | None:
    """Extract statement period end date."""
    match = re.search(
        r"(?:To|Period End|Statement To|Statement Date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))
    return None


def _extract_balance(text: str, pattern: str) -> Decimal:
    """Extract a balance amount from text."""
    match = re.search(rf"{pattern}\s*[:\-]?\s*([\d,\.]+)", text, re.IGNORECASE)
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_total_debits(text: str) -> Decimal:
    """Extract total debits from statement."""
    match = re.search(
        r"(?:Total Debits|Total Withdrawals|الرصيد المدين)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_total_credits(text: str) -> Decimal:
    """Extract total credits from statement."""
    match = re.search(
        r"(?:Total Credits|Total Deposits|الرصيد الدائن)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _check_reconciliation(opening: Decimal, closing: Decimal, text: str) -> bool:
    """Check if opening + credits - debits ≈ closing."""
    credits = _extract_total_credits(text)
    debits = _extract_total_debits(text)
    expected = opening + credits - debits
    return abs(expected - closing) < Decimal("1.00")


def _count_transactions(text: str) -> int:
    """Estimate transaction count from text."""
    # Count lines that look like transaction entries
    count = 0
    for line in text.split("\n"):
        if re.search(r"\d{4}-\d{2}-\d{2}", line) and re.search(r"[\d,]+\.?\d*", line):
            count += 1
    return max(0, count - 2)  # subtract header lines


def _parse_date(value: str) -> date | None:
    """Parse a date string in various formats."""
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _empty_result() -> dict[str, Any]:
    """Return empty result when no text is available."""
    return {
        "bank_name": None,
        "account_holder_name": None,
        "account_number": None,
        "iban": None,
        "account_type": None,
        "currency": "AED",
        "statement_period_start": None,
        "statement_period_end": None,
        "opening_balance": Decimal("0.00"),
        "closing_balance": Decimal("0.00"),
        "total_debits": Decimal("0.00"),
        "total_credits": Decimal("0.00"),
        "is_balance_reconciled": False,
        "transactions": [],
        "transaction_count": 0,
    }
