"""Document parser registry.

Central registry mapping document types to their parsing functions.
"""

from typing import Any

from src.domain.parsers.application_form import parse_application_form
from src.domain.parsers.assets_liabilities import parse_assets_liabilities
from src.domain.parsers.bank_statement import parse_bank_statement
from src.domain.parsers.credit_report import parse_credit_report
from src.domain.parsers.emirates_id import parse_emirates_id
from src.domain.parsers.resume import parse_resume

PARSERS: dict[str, Any] = {
    "emirates_id": parse_emirates_id,
    "bank_statement": parse_bank_statement,
    "credit_report": parse_credit_report,
    "resume": parse_resume,
    "assets_liabilities": parse_assets_liabilities,
    "application_form": parse_application_form,
}


def parse_document(document_type: str, raw_text: str, raw_result: Any) -> dict[str, Any]:
    """Parse raw extraction result into structured fields for a document type.

    Args:
        document_type: One of emirates_id, bank_statement, credit_report,
            resume, assets_liabilities, application_form.
        raw_text: Plain text extracted from the document.
        raw_result: Raw parser result object (format depends on parser used).

    Returns:
        Dict of structured fields for the document type.
    """
    parser = PARSERS.get(document_type)
    if parser is None:
        return {"raw_text": raw_text[:500] if raw_text else "", "parsed": False}
    return parser(raw_text, raw_result)


# Alias used by extraction pipeline
parse_by_document_type = parse_document
