"""Assets and liabilities document parser."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_assets_liabilities(raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse assets/liabilities data from extracted XLSX text.

    Args:
        raw_text: Plain text extracted from the XLSX statement.
        raw_result: Raw parser result object (dict mapping sheet names to DataFrames).

    Returns:
        Dict with applicant_name, assets, liabilities, net_worth, income.
    """
    # Prefer structured DataFrame extraction from raw_result
    if raw_result is not None and isinstance(raw_result, dict) and raw_result:
        return _parse_from_sheets(raw_result)

    text = _get_text(raw_text, raw_result)

    if not text or len(text.strip()) < 5:
        return _empty_result()

    logger.debug("parsing_assets_liabilities", text_length=len(text))

    return _parse_from_text(text)


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


def _parse_from_sheets(sheets: dict[str, Any]) -> dict[str, Any]:
    """Parse assets/liabilities from DataFrame sheets."""
    import pandas as pd

    result = _empty_result()

    for sheet_name, df in sheets.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue

        logger.debug("parsing_assets_sheet", sheet=sheet_name, rows=len(df))

        sheet_lower = sheet_name.lower()

        if "asset" in sheet_lower or "assets" in sheet_lower:
            _extract_asset_row(result, df)
        elif "liability" in sheet_lower or "liabilities" in sheet_lower:
            _extract_liability_row(result, df)
        elif "income" in sheet_lower:
            _extract_income_row(result, df)
        else:
            # Try to detect by column content
            _auto_classify_sheet(result, df)

    # Compute totals
    result["total_assets"] = (
        result["cash_and_deposits"]
        + result["savings_accounts"]
        + result["investment_accounts"]
        + result["retirement_accounts"]
        + result["real_estate_value"]
        + result["vehicle_value"]
        + result["other_assets"]
    )
    result["total_liabilities"] = (
        result["mortgage_balance"]
        + result["personal_loans"]
        + result["credit_card_debt"]
        + result["student_loans"]
        + result["other_liabilities"]
    )
    result["net_worth"] = result["total_assets"] - result["total_liabilities"]
    result["statement_date"] = date.today()

    return result


def _extract_asset_row(result: dict, df: Any) -> None:
    """Extract asset values from a DataFrame row."""
    import pandas as pd

    for _, row in df.iterrows():
        row_dict = {str(k).strip().lower(): v for k, v in row.items() if pd.notna(v)}

        for key, value in row_dict.items():
            val = _to_decimal(value)
            if val is None:
                continue

            if "cash" in key or "deposit" in key:
                result["cash_and_deposits"] = val
            elif "saving" in key:
                result["savings_accounts"] = val
            elif "investment" in key:
                result["investment_accounts"] = val
            elif "retirement" in key or "pension" in key:
                result["retirement_accounts"] = val
            elif "real estate" in key or "property" in key or "real_estate" in key:
                result["real_estate_value"] = val
            elif "vehicle" in key or "car" in key:
                result["vehicle_value"] = val
            elif "other" in key and "asset" in key:
                result["other_assets"] = val


def _extract_liability_row(result: dict, df: Any) -> None:
    """Extract liability values from a DataFrame row."""
    import pandas as pd

    for _, row in df.iterrows():
        row_dict = {str(k).strip().lower(): v for k, v in row.items() if pd.notna(v)}

        for key, value in row_dict.items():
            val = _to_decimal(value)
            if val is None:
                continue

            if "mortgage" in key:
                result["mortgage_balance"] = val
            elif "personal loan" in key or "personal_loan" in key:
                result["personal_loans"] = val
            elif "credit card" in key or "credit_card" in key:
                result["credit_card_debt"] = val
            elif "student" in key and "loan" in key:
                result["student_loans"] = val
            elif "other" in key and "liability" in key:
                result["other_liabilities"] = val


def _extract_income_row(result: dict, df: Any) -> None:
    """Extract income values from a DataFrame row."""
    import pandas as pd

    for _, row in df.iterrows():
        row_dict = {str(k).strip().lower(): v for k, v in row.items() if pd.notna(v)}

        for key, value in row_dict.items():
            val = _to_decimal(value)
            if val is None:
                continue

            if "monthly" in key or "salary" in key or "income" in key:
                result["monthly_income"] = val
                result["income_sources"] = [{"source": key, "amount": val}]
                break


def _auto_classify_sheet(result: dict, df: Any) -> None:
    """Auto-classify sheet columns into assets/liabilities."""
    import pandas as pd

    for col in df.columns:
        col_lower = str(col).strip().lower()
        if col_lower in ("name", "applicant", "description", "notes", "date"):
            continue

        # Get the first non-null value
        for val in df[col]:
            if pd.isna(val):
                continue
            decimal_val = _to_decimal(val)
            if decimal_val is None:
                continue

            # Classify by column name
            if "asset" in col_lower or "cash" in col_lower or "deposit" in col_lower:
                if "cash" in col_lower or "deposit" in col_lower:
                    result["cash_and_deposits"] = decimal_val
                elif "saving" in col_lower:
                    result["savings_accounts"] = decimal_val
                elif "investment" in col_lower:
                    result["investment_accounts"] = decimal_val
                elif "real estate" in col_lower or "property" in col_lower:
                    result["real_estate_value"] = decimal_val
                elif "vehicle" in col_lower or "car" in col_lower:
                    result["vehicle_value"] = decimal_val
            elif "liability" in col_lower or "loan" in col_lower or "debt" in col_lower:
                if "mortgage" in col_lower:
                    result["mortgage_balance"] = decimal_val
                elif "personal" in col_lower:
                    result["personal_loans"] = decimal_val
                elif "credit" in col_lower:
                    result["credit_card_debt"] = decimal_val
            elif "income" in col_lower or "salary" in col_lower:
                result["monthly_income"] = decimal_val
            break


def _parse_from_text(text: str) -> dict[str, Any]:
    """Parse assets/liabilities from plain text (fallback)."""
    result = _empty_result()

    result["cash_and_deposits"] = _extract_amount(text, r"(?:Cash|Deposits|النقد)\s*[:\-]?\s*([\d,\.]+)")
    result["savings_accounts"] = _extract_amount(text, r"(?:Savings|مدخرات)\s*[:\-]?\s*([\d,\.]+)")
    result["investment_accounts"] = _extract_amount(text, r"(?:Investments|استثمارات)\s*[:\-]?\s*([\d,\.]+)")
    result["retirement_accounts"] = _extract_amount(text, r"(?:Retirement|Pension|تقاعد)\s*[:\-]?\s*([\d,\.]+)")
    result["real_estate_value"] = _extract_amount(text, r"(?:Real Estate|Property|العقارات)\s*[:\-]?\s*([\d,\.]+)")
    result["vehicle_value"] = _extract_amount(text, r"(?:Vehicle|Car|المركبات)\s*[:\-]?\s*([\d,\.]+)")
    result["other_assets"] = _extract_amount(text, r"(?:Other Assets|أصول أخرى)\s*[:\-]?\s*([\d,\.]+)")

    result["mortgage_balance"] = _extract_amount(text, r"(?:Mortgage|الرهن)\s*[:\-]?\s*([\d,\.]+)")
    result["personal_loans"] = _extract_amount(text, r"(?:Personal Loans|القروض الشخصية)\s*[:\-]?\s*([\d,\.]+)")
    result["credit_card_debt"] = _extract_amount(text, r"(?:Credit Card|البطاقات الائتمانية)\s*[:\-]?\s*([\d,\.]+)")
    result["student_loans"] = _extract_amount(text, r"(?:Student Loans|القروض الدراسية)\s*[:\-]?\s*([\d,\.]+)")
    result["other_liabilities"] = _extract_amount(text, r"(?:Other Liabilities|خصوم أخرى)\s*[:\-]?\s*([\d,\.]+)")

    result["monthly_income"] = _extract_amount(text, r"(?:Monthly Income|Salary|الراتب الشهري)\s*[:\-]?\s*([\d,\.]+)")

    # Compute totals
    result["total_assets"] = (
        result["cash_and_deposits"]
        + result["savings_accounts"]
        + result["investment_accounts"]
        + result["retirement_accounts"]
        + result["real_estate_value"]
        + result["vehicle_value"]
        + result["other_assets"]
    )
    result["total_liabilities"] = (
        result["mortgage_balance"]
        + result["personal_loans"]
        + result["credit_card_debt"]
        + result["student_loans"]
        + result["other_liabilities"]
    )
    result["net_worth"] = result["total_assets"] - result["total_liabilities"]
    result["statement_date"] = date.today()

    return result


def _extract_amount(text: str, pattern: str) -> Decimal:
    """Extract a decimal amount from text matching pattern."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return Decimal("0.00")


def _to_decimal(value: Any) -> Decimal | None:
    """Convert a value to Decimal."""
    if value is None:
        return None
    try:
        if hasattr(value, "item"):  # numpy types
            value = value.item()
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return None


def _empty_result() -> dict[str, Any]:
    """Return empty result when no data is available."""
    return {
        "applicant_name": None,
        "statement_date": None,
        "cash_and_deposits": Decimal("0.00"),
        "savings_accounts": Decimal("0.00"),
        "investment_accounts": Decimal("0.00"),
        "retirement_accounts": Decimal("0.00"),
        "real_estate_value": Decimal("0.00"),
        "vehicle_value": Decimal("0.00"),
        "other_assets": Decimal("0.00"),
        "total_assets": Decimal("0.00"),
        "mortgage_balance": Decimal("0.00"),
        "personal_loans": Decimal("0.00"),
        "credit_card_debt": Decimal("0.00"),
        "student_loans": Decimal("0.00"),
        "other_liabilities": Decimal("0.00"),
        "total_liabilities": Decimal("0.00"),
        "net_worth": Decimal("0.00"),
        "monthly_income": None,
        "income_sources": None,
        "asset_details": [],
        "liability_details": [],
    }
