"""Application form document parser."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_application_form(raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse application form data from extracted text.

    Args:
        raw_text: Plain text extracted from the handwritten form.
        raw_result: Raw parser result object (OCRResult for images, ExtractionResult for PDFs).

    Returns:
        Dict with applicant_name, identity_number, demographics,
        employment, income, housing, and support category.
    """
    text = _get_text(raw_text, raw_result)

    if not text or len(text.strip()) < 5:
        return _empty_result()

    logger.debug("parsing_application_form", text_length=len(text))

    identity = _extract_identity_number(text)
    monthly_salary = _extract_monthly_salary(text)
    other_income = _extract_other_income(text)

    return {
        "applicant_name": _extract_name(text),
        "identity_number": identity,
        "date_of_birth": _extract_dob(text),
        "nationality": _extract_nationality(text),
        "contact_phone": _extract_phone(text),
        "contact_email": _extract_email(text),
        "address": _extract_address(text),
        "marital_status": _extract_marital_status(text),
        "family_size": _extract_family_size(text),
        "dependents": _extract_dependents(text),
        "employment_status": _extract_employment_status(text),
        "employer_name": _extract_employer(text),
        "occupation": _extract_occupation(text),
        "monthly_salary": monthly_salary,
        "other_income": other_income,
        "total_monthly_income": (monthly_salary or Decimal("0")) + (other_income or Decimal("0")),
        "housing_status": _extract_housing_status(text),
        "monthly_rent": _extract_rent(text),
        "monthly_mortgage": _extract_mortgage(text),
        "support_category": _infer_support_category(text),
        "supporting_documents": _extract_supporting_docs(text),
        "is_declaration_signed": _check_declaration(text),
        "declaration_date": _extract_declaration_date(text),
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


def _extract_name(text: str) -> str | None:
    """Extract applicant full name."""
    match = re.search(
        r"(?:Applicant Name|Full Name|Name|الاسم الكامل|اسم المتقدم)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_identity_number(text: str) -> str | None:
    """Extract 15-digit Emirates ID number."""
    match = re.search(r"\b(\d{15})\b", text)
    return match.group(1) if match else None


def _extract_dob(text: str) -> date | None:
    """Extract date of birth."""
    match = re.search(
        r"(?:Date of Birth|DOB|تاريخ الميلاد)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))
    return None


def _extract_nationality(text: str) -> str | None:
    """Extract nationality."""
    match = re.search(
        r"(?:Nationality|الجنسية)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF]+)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_phone(text: str) -> str | None:
    """Extract contact phone number."""
    match = re.search(r"(\+?\d{1,3}[-.\s]?\d{7,15})", text)
    return match.group(1).replace(" ", "") if match else None


def _extract_email(text: str) -> str | None:
    """Extract email address."""
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else None


def _extract_address(text: str) -> dict[str, Any]:
    """Extract address information."""
    address: dict[str, Any] = {}

    # Emirate
    emirates = ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain", "Al Ain"]
    for emirate in emirates:
        if emirate.lower() in text.lower():
            address["emirate"] = emirate
            break

    # Area
    area_match = re.search(
        r"(?:Area|Area Name|المنطقة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if area_match:
        address["area"] = area_match.group(1).strip()

    return address if address else None


def _extract_marital_status(text: str) -> str | None:
    """Extract marital status."""
    text_lower = text.lower()
    statuses = {
        "married": "Married",
        "single": "Single",
        "divorced": "Divorced",
        "widowed": "Widowed",
        "separated": "Separated",
    }
    for key, value in statuses.items():
        if key in text_lower:
            return value
    return None


def _extract_family_size(text: str) -> int | None:
    """Extract family size (number of family members)."""
    match = re.search(
        r"(?:Family Size|Number of Dependents|family size|عدد الأفراد)\s*[:\-]?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def _extract_dependents(text: str) -> list[dict[str, Any]] | None:
    """Extract dependent children information."""
    dependents = []

    # Look for patterns like "Child Name: X, Age: Y"
    pattern = r"(?:Child|Dependent|الابن|الابنة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)\s*(?:,|Age|العمر)\s*[:\-]?\s*(\d+)"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        dependents.append({
            "name": match.group(1).strip(),
            "age": int(match.group(2)),
        })

    return dependents if dependents else None


def _extract_employment_status(text: str) -> str | None:
    """Extract employment status."""
    text_lower = text.lower()
    statuses = {
        "employed": "Employed",
        "unemployed": "Unemployed",
        "self-employed": "Self-employed",
        "retired": "Retired",
        "student": "Student",
    }
    for key, value in statuses.items():
        if key in text_lower:
            return value
    return None


def _extract_employer(text: str) -> str | None:
    """Extract employer name."""
    match = re.search(
        r"(?:Employer|Company|الجهة العاملة|اسم الشركة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_occupation(text: str) -> str | None:
    """Extract occupation/profession."""
    match = re.search(
        r"(?:Occupation|Profession|الوظيفة|المهنة)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_monthly_salary(text: str) -> Decimal:
    """Extract monthly salary amount."""
    match = re.search(
        r"(?:Monthly Salary|Salary|Basic Salary|الراتب الشهري|الراتب الأساسي)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_other_income(text: str) -> Decimal:
    """Extract other income sources."""
    match = re.search(
        r"(?:Other Income|Additional Income|دخل إضافي|دخل آخر)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_housing_status(text: str) -> str | None:
    """Extract housing status."""
    text_lower = text.lower()
    statuses = {
        "owned": "Owned",
        "rented": "Rented",
        "mortgaged": "Mortgaged",
        "family provided": "Family Provided",
    }
    for key, value in statuses.items():
        if key in text_lower:
            return value
    return None


def _extract_rent(text: str) -> Decimal:
    """Extract monthly rent amount."""
    match = re.search(
        r"(?:Monthly Rent|Rent|الإيجار الشهري)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _extract_mortgage(text: str) -> Decimal:
    """Extract monthly mortgage payment."""
    match = re.search(
        r"(?:Monthly Mortgage|Mortgage|القسط الشهري)\s*[:\-]?\s*([\d,\.]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _infer_support_category(text: str) -> str | None:
    """Infer support category from application content."""
    text_lower = text.lower()

    # Check for explicit category selection
    categories = ["divorced", "abandoned", "unknown_parentage", "health_disability", "orphan", "widow"]
    for cat in categories:
        if cat.replace("_", " ") in text_lower or cat in text_lower:
            return cat

    # Infer from marital status + other clues
    marital = _extract_marital_status(text)
    if marital == "Divorced":
        return "divorced"
    elif marital == "Widowed":
        return "widow"

    return None


def _extract_supporting_docs(text: str) -> list[str] | None:
    """Extract list of supporting documents mentioned."""
    docs = []
    doc_types = ["emirates_id", "passport", "bank_statement", "credit_report", "salary_certificate",
                 "employment_letter", "tenancy_contract", "marriage_certificate", "divorce_decree",
                 "birth_certificate", "medical_report"]
    for doc in doc_types:
        if doc.replace("_", " ") in text.lower() or doc in text.lower():
            docs.append(doc)
    return docs if docs else None


def _check_declaration(text: str) -> bool:
    """Check if declaration is signed."""
    return bool(re.search(r"(?:I declare|I hereby|أقر|Signature|توقيع)", text, re.IGNORECASE))


def _extract_declaration_date(text: str) -> date | None:
    """Extract declaration/signature date."""
    match = re.search(
        r"(?:Date|Date of Declaration|التاريخ)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date(match.group(1))
    return None


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
        "applicant_name": None,
        "identity_number": None,
        "date_of_birth": None,
        "nationality": None,
        "contact_phone": None,
        "contact_email": None,
        "address": None,
        "marital_status": None,
        "family_size": None,
        "dependents": None,
        "employment_status": None,
        "employer_name": None,
        "occupation": None,
        "monthly_salary": Decimal("0.00"),
        "other_income": Decimal("0.00"),
        "total_monthly_income": Decimal("0.00"),
        "housing_status": None,
        "monthly_rent": Decimal("0.00"),
        "monthly_mortgage": Decimal("0.00"),
        "support_category": None,
        "supporting_documents": None,
        "is_declaration_signed": False,
        "declaration_date": None,
    }
