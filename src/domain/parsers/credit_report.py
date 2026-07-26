"""Credit report document parser."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_credit_report(raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse credit report data from extracted text.

    Args:
        raw_text: Plain text extracted from the credit report.
        raw_result: Raw parser result object (ExtractionResult for PDFs).

    Returns:
        Dict with cb_subject_id, identity_number, credit_score, risk_band,
        facilities, payment_history, and related fields.
    """
    text = _get_text(raw_text, raw_result)

    if not text or len(text.strip()) < 5:
        return _empty_result()

    logger.debug("parsing_credit_report", text_length=len(text))

    identity = _extract_identity_number(text)
    score = _extract_credit_score(text)

    return {
        "cb_subject_id": f"CB{identity[:8]}" if identity else None,
        "identity_number": identity,
        "full_name": _extract_name(text),
        "contact_details": _extract_contact(text),
        "employment_info": _extract_employment(text),
        "credit_score": score,
        "risk_band": _risk_band_from_score(score),
        "score_calculation_date": _extract_score_date(text),
        "total_active_accounts": _extract_active_accounts(text),
        "total_closed_accounts": _extract_closed_accounts(text),
        "total_outstanding_balance": _extract_outstanding(text),
        "total_credit_limit": _extract_credit_limit(text),
        "credit_utilization_ratio": _extract_utilization(text),
        "active_facilities": _extract_facilities(text, active=True),
        "closed_facilities": _extract_facilities(text, active=False),
        "payment_history": _extract_payment_history(text),
        "late_payment_count": _extract_late_count(text),
        "defaulted_accounts": _extract_defaults(text),
        "bounced_cheques": _extract_bounced(text),
        "court_judgments": _extract_judgments(text),
        "has_bankruptcy_records": _has_bankruptcy(text),
        "inquiry_count": _extract_inquiries(text),
        "inquiries": [],
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


def _extract_identity_number(text: str) -> str | None:
    """Extract 15-digit identity number."""
    match = re.search(r"\b(\d{15})\b", text)
    return match.group(1) if match else None


def _extract_name(text: str) -> str | None:
    """Extract subject name from credit report."""
    match = re.search(
        r"(?:Name|Subject Name|الاسم)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_contact(text: str) -> dict[str, Any] | None:
    """Extract contact details."""
    contact: dict[str, Any] = {}

    phone_match = re.search(
        r"(?:Phone|Mobile|الهاتف)\s*[:\-]?\s*(\+?\d[\d\s\-]{8,})",
        text,
        re.IGNORECASE,
    )
    if phone_match:
        contact["phone"] = phone_match.group(1).strip()

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if email_match:
        contact["email"] = email_match.group(0)

    return contact if contact else None


def _extract_employment(text: str) -> dict[str, Any] | None:
    """Extract employment information."""
    employment: dict[str, Any] = {}

    employer_match = re.search(
        r"(?:Employer|Employment|العمل)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if employer_match:
        employment["employer"] = employer_match.group(1).strip()

    position_match = re.search(
        r"(?:Position|Designation|الوظيفة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if position_match:
        employment["position"] = position_match.group(1).strip()

    return employment if employment else None


def _extract_credit_score(text: str) -> int | None:
    """Extract credit score (300-900 range)."""
    match = re.search(
        r"(?:Credit Score|Score|النتيجة الائتمانية)\s*[:\-]?\s*(\d{3})",
        text,
        re.IGNORECASE,
    )
    if match:
        score = int(match.group(1))
        if 300 <= score <= 900:
            return score
    # Try any 3-digit number near "score"
    match = re.search(r"(\d{3})\s*(?:Score|score)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _risk_band_from_score(score: int | None) -> str | None:
    """Map credit score to AECB risk band."""
    if score is None:
        return None
    if score >= 750:
        return "A"
    elif score >= 650:
        return "B"
    elif score >= 550:
        return "C"
    elif score >= 450:
        return "D"
    else:
        return "E"


def _extract_score_date(text: str) -> date | None:
    """Extract score calculation date."""
    match = re.search(
        r"(?:Score Date|Report Date|Date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))
    return None


def _extract_active_accounts(text: str) -> int:
    """Extract count of active accounts."""
    match = re.search(
        r"(?:Active Accounts|Total Active|الحسابات النشطة)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


def _extract_closed_accounts(text: str) -> int:
    """Extract count of closed accounts."""
    match = re.search(
        r"(?:Closed Accounts|Total Closed|الحسابات المغلقة)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


def _extract_outstanding(text: str) -> Decimal:
    """Extract total outstanding balance."""
    match = re.search(
        r"(?:Total Outstanding|Outstanding Balance|الرصيد المستحق)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_credit_limit(text: str) -> Decimal:
    """Extract total credit limit."""
    match = re.search(
        r"(?:Total Credit Limit|Credit Limit|الحد الائتماني)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_utilization(text: str) -> Decimal | None:
    """Extract credit utilization ratio."""
    match = re.search(
        r"(?:Utilization|Utilization Ratio)\s*[:\-]?\s*([\d\.]+)%?",
        text,
        re.IGNORECASE,
    )
    if match:
        val = Decimal(match.group(1))
        return val / 100 if val > 1 else val
    return None


def _extract_facilities(text: str, active: bool) -> list[dict[str, Any]]:
    """Extract credit facilities (simplified)."""
    facilities = []
    # Look for facility-like patterns
    lines = text.split("\n")
    for line in lines:
        if re.search(r"(?:Loan|Credit Card|Facility|Mortgage)", line, re.IGNORECASE):
            facilities.append({
                "facility_type": _guess_facility_type(line),
                "lender_name": None,
                "account_number": None,
                "status": "Active" if active else "Closed",
                "opened_date": None,
                "closed_date": None,
                "credit_limit": None,
                "current_balance": None,
                "monthly_payment": None,
                "payment_status": None,
            })
            if len(facilities) >= 10:
                break
    return facilities


def _guess_facility_type(line: str) -> str:
    """Guess facility type from line text."""
    line_lower = line.lower()
    if "personal loan" in line_lower or "personal" in line_lower:
        return "Personal Loan"
    if "credit card" in line_lower or "card" in line_lower:
        return "Credit Card"
    if "mortgage" in line_lower or "home loan" in line_lower:
        return "Mortgage"
    if "auto" in line_lower or "car" in line_lower or "vehicle" in line_lower:
        return "Auto Loan"
    return "Other Loan"


def _extract_payment_history(text: str) -> dict[str, Any] | None:
    """Extract payment history summary."""
    on_time = _extract_count_near(text, r"(?:On Time|Ontime|في الوقت)", 0)
    late_30 = _extract_count_near(text, r"(?:Late 30|30 Days|متأخر 30)", 0)
    late_60 = _extract_count_near(text, r"(?:Late 60|60 Days|متأخر 60)", 0)
    late_90 = _extract_count_near(text, r"(?:Late 90|90 Days|متأخر 90)", 0)

    if on_time == 0 and late_30 == 0:
        return None

    return {
        "on_time": on_time,
        "late_30": late_30,
        "late_60": late_60,
        "late_90": late_90,
    }


def _extract_count_near(text: str, pattern: str, default: int) -> int:
    """Extract a count near a pattern."""
    match = re.search(rf"{pattern}[:\s]+(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return default


def _extract_late_count(text: str) -> int:
    """Extract total late payment count."""
    match = re.search(
        r"(?:Late Payments|Late Count|المدفوعات المتأخرة)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


def _extract_defaults(text: str) -> int:
    """Extract defaulted account count."""
    match = re.search(
        r"(?:Defaulted|Defaults|المتعثرة)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


def _extract_bounced(text: str) -> int:
    """Extract bounced cheque count."""
    match = re.search(
        r"(?:Bounced Cheques|Bounced Checks|الشيكات المرتجعة)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


def _extract_judgments(text: str) -> int:
    """Extract court judgment count."""
    match = re.search(
        r"(?:Court Judgments|Judgments|الأحكام القضائية)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


def _has_bankruptcy(text: str) -> bool:
    """Check for bankruptcy records."""
    return bool(re.search(r"\bBankruptcy\b|إفلاس", text, re.IGNORECASE))


def _extract_inquiries(text: str) -> int:
    """Extract inquiry count."""
    match = re.search(
        r"(?:Inquiries|Enquiries|Inquiry Count|الاستفسارات)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else 0


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
        "cb_subject_id": None,
        "identity_number": None,
        "full_name": None,
        "contact_details": None,
        "employment_info": None,
        "credit_score": None,
        "risk_band": None,
        "score_calculation_date": None,
        "total_active_accounts": 0,
        "total_closed_accounts": 0,
        "total_outstanding_balance": Decimal("0.00"),
        "total_credit_limit": Decimal("0.00"),
        "credit_utilization_ratio": None,
        "active_facilities": [],
        "closed_facilities": [],
        "payment_history": None,
        "late_payment_count": 0,
        "defaulted_accounts": 0,
        "bounced_cheques": 0,
        "court_judgments": 0,
        "has_bankruptcy_records": False,
        "inquiry_count": 0,
        "inquiries": [],
    }
