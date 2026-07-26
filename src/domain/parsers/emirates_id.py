"""Emirates ID document parser."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_emirates_id(raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse Emirates ID data from extracted text.

    Args:
        raw_text: Plain text extracted from the Emirates ID document.
        raw_result: Raw parser result object (OCRResult for images, ExtractionResult for PDFs).

    Returns:
        Dict with identity_number, full_name_en, nationality, date_of_birth,
        gender, issue_date, expiry_date, and related fields.
    """
    text = _get_text(raw_text, raw_result)

    if not text or len(text.strip()) < 5:
        return _empty_result()

    logger.debug("parsing_emirates_id", text_length=len(text))

    return {
        "identity_number": _extract_identity_number(text),
        "full_name_en": _extract_name(text),
        "full_name_ar": None,
        "nationality": _extract_nationality(text),
        "date_of_birth": _extract_dob(text),
        "gender": _extract_gender(text),
        "card_number": None,
        "issue_date": None,
        "expiry_date": _extract_expiry(text),
        "is_mrz_verified": False,
        "address": None,
        "occupation": _extract_occupation(text),
        "employer_name": None,
        "marital_status": _extract_marital_status(text),
        "mother_name": None,
        "sponsor_name": None,
        "sponsor_type": None,
        "residency_type": None,
        "residency_number": None,
    }


def _get_text(raw_text: str, raw_result: Any) -> str:
    """Get text from raw_text or raw_result."""
    if raw_text and len(raw_text.strip()) > 5:
        return raw_text
    if raw_result is not None:
        if hasattr(raw_result, "text"):
            return raw_result.text or ""
        if hasattr(raw_result, "raw_extracted_data"):
            data = raw_result.raw_extracted_data
            if isinstance(data, dict) and "markdown" in data:
                return data["markdown"] or ""
            return str(data)
    return ""


def _extract_identity_number(text: str) -> str | None:
    """Extract 15-digit Emirates ID number."""
    match = re.search(r"\b(\d{15})\b", text)
    return match.group(1) if match else None


def _extract_name(text: str) -> str | None:
    """Extract full name from document text."""
    # Try common patterns
    patterns = [
        r"(?:Name|NAME|الاسم)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+)",
        r"(?:Card Holder|CARD HOLDER|اسم حامل البطاقة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: first substantial line that looks like a name
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines:
        if 3 <= len(line) <= 80 and not any(c.isdigit() for c in line):
            return line

    return None


def _extract_nationality(text: str) -> str | None:
    """Extract nationality from document text."""
    match = re.search(
        r"(?:Nationality|NATIONALITY|الجنسية)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF]+)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_dob(text: str) -> date | None:
    """Extract date of birth from document text."""
    # Try ISO format first
    match = re.search(
        r"(?:Date of Birth|DOB|تاريخ الميلاد)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))

    # Try DD/MM/YYYY
    match = re.search(
        r"(?:Date of Birth|DOB|تاريخ الميلاد)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))

    # Try any date-like pattern
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return _parse_date(match.group(1))

    match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", text)
    if match:
        return _parse_date(match.group(1))

    return None


def _extract_expiry(text: str) -> date | None:
    """Extract expiry date from document text."""
    match = re.search(
        r"(?:Expiry|EXP|Date of Expiry|تاريخ الانتهاء)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))

    # Try any date-like pattern near "expir" or "انتهاء"
    if "expir" in text.lower() or "انتهاء" in text:
        match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if match:
            return _parse_date(match.group(1))

    return None


def _extract_gender(text: str) -> str | None:
    """Extract gender from document text."""
    if re.search(r"\bMale\b|ذكر", text, re.IGNORECASE):
        return "Male"
    if re.search(r"\bFemale\b|أنثى", text, re.IGNORECASE):
        return "Female"
    return None


def _extract_occupation(text: str) -> str | None:
    """Extract occupation/profession from document text."""
    match = re.search(
        r"(?:Occupation|Profession|PROFESSION|المهنة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_marital_status(text: str) -> str | None:
    """Extract marital status from document text."""
    text_lower = text.lower()
    statuses = {
        "married": "Married",
        "single": "Single",
        "divorced": "Divorced",
        "widowed": "Widowed",
    }
    for key, value in statuses.items():
        if key in text_lower:
            return value
    return None


def _parse_date(value: str) -> date | None:
    """Parse a date string in various formats."""
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _empty_result() -> dict[str, Any]:
    """Return empty result when no text is available."""
    return {
        "identity_number": None,
        "full_name_en": None,
        "full_name_ar": None,
        "nationality": None,
        "date_of_birth": None,
        "gender": None,
        "card_number": None,
        "issue_date": None,
        "expiry_date": None,
        "is_mrz_verified": False,
        "address": None,
        "occupation": None,
        "employer_name": None,
        "marital_status": None,
        "mother_name": None,
        "sponsor_name": None,
        "sponsor_type": None,
        "residency_type": None,
        "residency_number": None,
    }
