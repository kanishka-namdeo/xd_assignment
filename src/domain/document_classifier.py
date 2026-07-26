"""Document type classification from file paths.

Pure domain logic: maps file paths to document types based on
extension and filename patterns. No I/O operations.
"""

from pathlib import Path


def classify_document(file_path: str) -> str:
    """Classify a file into a document type based on extension and filename.

    Rules:
    - png/jpg/jpeg → emirates_id
    - xlsx → assets_liabilities
    - docx → resume
    - pdf → bank_statement, credit_report, or application_form (based on filename keywords)

    Args:
        file_path: Absolute or relative path to the uploaded file.

    Returns:
        Document type key (e.g., "emirates_id", "bank_statement").
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    name_lower = path.stem.lower()

    if ext in {".png", ".jpg", ".jpeg"}:
        return "emirates_id"
    if ext == ".xlsx":
        return "assets_liabilities"
    if ext == ".docx":
        return "resume"
    if ext == ".pdf":
        if "bank" in name_lower or "statement" in name_lower:
            return "bank_statement"
        if "credit" in name_lower or "aecb" in name_lower:
            return "credit_report"
        if "application" in name_lower or "form" in name_lower:
            return "application_form"
        return "bank_statement"
    return "unknown"
