"""LLM-based document extraction helpers."""

from __future__ import annotations

import json

import structlog

logger = structlog.get_logger(__name__)

SCHEMA_HINTS: dict[str, str] = {
    "emirates_id": "identity_number, full_name_en, nationality, date_of_birth, gender, issue_date, expiry_date, occupation, employer_name, marital_status",
    "bank_statement": "bank_name, account_holder_name, account_number, iban, currency, statement_period_start, statement_period_end, opening_balance, closing_balance, total_debits, total_credits",
    "credit_report": "cb_subject_id, identity_number, full_name, credit_score, risk_band, total_active_accounts, total_outstanding_balance, total_credit_limit, credit_utilization_ratio, late_payment_count, defaulted_accounts",
    "resume": "full_name, email, phone, location, years_of_experience, current_employer, current_job_title, skills, highest_degree",
    "assets_liabilities": "applicant_name, cash_and_deposits, savings_accounts, investment_accounts, retirement_accounts, real_estate_value, total_assets, mortgage_balance, personal_loans, total_liabilities, net_worth, monthly_income",
    "application_form": "applicant_name, identity_number, date_of_birth, nationality, contact_phone, contact_email, marital_status, family_size, employment_status, employer_name, occupation, monthly_salary, support_category",
}


def get_schema_hints(document_type: str) -> str:
    """Return field hints for LLM-guided extraction."""
    return SCHEMA_HINTS.get(document_type, "relevant fields for this document")


def build_llm_prompt(document_type: str, raw_text: str) -> tuple[str, str]:
    """Build system and user prompts for LLM extraction."""
    schema_hints = get_schema_hints(document_type)
    system_prompt = (
        "You are a document data extraction assistant for UAE Social Support applications. "
        "Extract structured data from the provided document text. "
        "Return ONLY valid JSON matching this schema. Do not include any explanation. "
        f"Document type: {document_type}\n"
        f"Fields to extract: {schema_hints}"
    )
    user_message = f"Extract structured data from this document:\n\n{raw_text[:8000]}"
    return system_prompt, user_message


async def parse_with_llm(
    llm_client,
    document_type: str,
    raw_text: str,
    model: str = "kat-coder-pro-v2.5",
) -> dict | None:
    """Use LLM to extract structured fields from raw document text.

    Returns None if LLM is unavailable or parsing fails.
    """
    if llm_client is None:
        return None

    if not raw_text or len(raw_text.strip()) < 10:
        return None

    system_prompt, user_message = build_llm_prompt(document_type, raw_text)

    try:
        result = await llm_client.structured_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
        )
        content = result.get("content", "").strip()
        parsed = json.loads(content)
        if isinstance(parsed, dict) and parsed:
            return parsed
    except Exception as e:
        logger.warning("llm_extraction_failed", document_type=document_type, error=str(e))

    return None


def extract_text_from_pdf_result(result) -> str:
    """Extract plain text from PDF parser result."""
    raw_data = result.raw_extracted_data
    if isinstance(raw_data, dict) and "markdown" in raw_data:
        return raw_data["markdown"]
    return str(raw_data)


def extract_text_from_xlsx(result: dict) -> str:
    """Extract plain text from XLSX extractor result."""
    parts = []
    for sheet_name, df in result.items():
        parts.append(f"Sheet: {sheet_name}")
        parts.append(df.to_string())
    return "\n".join(parts)
