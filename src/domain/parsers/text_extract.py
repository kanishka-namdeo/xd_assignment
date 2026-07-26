"""Text extraction utilities for PDF and XLSX formats."""


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
