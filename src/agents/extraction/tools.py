"""Extraction tools for the ReAct extraction agent.

Six tools wrapping the document-processing infrastructure layer.
Each tool is a thin synchronous adapter that delegates to the async
infrastructure classes via ``asyncio.run`` so they can be invoked by
LangGraph's ``create_react_agent`` (which runs tools synchronously).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from synchronous tool context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _file_exists(file_path: str) -> bool:
    return Path(file_path).exists()


# ---------------------------------------------------------------------------
# Tool 1: OCR Extract
# ---------------------------------------------------------------------------

@tool
def ocr_extract_tool(file_path: Any = None, language: str = "en+ar") -> dict:
    """Extract text from images using PaddleOCR.

    Use for: Scanned documents, images (Emirates ID, application forms).
    Returns: Extracted text with bounding boxes and confidence scores.

    Args:
        file_path: Absolute path to the image file (PNG, JPG, JPEG).
        language: OCR language code. Default "en+ar" for English + Arabic.

    Returns:
        Dict with keys: text, blocks, confidence, language, duration_ms.
    """
    start = time.monotonic()

    if file_path is None or not isinstance(file_path, str) or not file_path:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("tool_invalid_input", tool="ocr_extract", reason="file_path must be a non-empty string")
        return {"error": "file_path must be a non-empty string", "duration_ms": round(duration_ms, 2)}

    logger.info("tool_enter", tool="ocr_extract", file_path=file_path, language=language)

    if not _file_exists(file_path):
        return {"error": f"File not found: {file_path}", "duration_ms": 0}

    try:
        from src.infrastructure.document_processing.ocr import OCREngine

        engine = OCREngine(language=language)
        result = _run_async(engine.extract(file_path))

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool_complete",
            tool="ocr_extract",
            duration_ms=round(duration_ms, 2),
            text_length=len(result.text),
            confidence=round(result.confidence, 4),
        )
        return {
            "text": result.text,
            "blocks": result.blocks,
            "confidence": result.confidence,
            "language": result.language,
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("tool_failed", tool="ocr_extract", error=str(e), duration_ms=round(duration_ms, 2))
        return {"error": str(e), "duration_ms": round(duration_ms, 2)}


# ---------------------------------------------------------------------------
# Tool 2: PDF Parse
# ---------------------------------------------------------------------------

@tool
def pdf_parse_tool(file_path: Any = None, pages: list[int] | None = None, extract_tables: bool = True) -> dict:
    """Parse digital PDF using PyMuPDF4LLM.

    Use for: Digital PDFs with text layer (credit reports, bank statements).
    Returns: Markdown or JSON with extracted text, tables, and metadata.

    Args:
        file_path: Absolute path to the PDF file.
        pages: Specific pages to extract (0-indexed). None means all pages.
        extract_tables: Whether to extract tables. Default True.

    Returns:
        Dict with keys: markdown, json_structure, confidence, field_count, duration_ms.
    """
    start = time.monotonic()

    if file_path is None or not isinstance(file_path, str) or not file_path:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("tool_invalid_input", tool="pdf_parse", reason="file_path must be a non-empty string")
        return {"error": "file_path must be a non-empty string", "duration_ms": round(duration_ms, 2)}

    logger.info("tool_enter", tool="pdf_parse", file_path=file_path, pages=pages)

    if not _file_exists(file_path):
        return {"error": f"File not found: {file_path}", "duration_ms": 0}

    try:
        from src.infrastructure.document_processing.pdf_parser import PDFParser

        parser = PDFParser()
        result = _run_async(parser.extract(file_path, pages=pages, extract_tables=extract_tables))

        raw = result.raw_extracted_data
        markdown = raw.get("markdown", "") if isinstance(raw, dict) else str(raw)

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool_complete",
            tool="pdf_parse",
            duration_ms=round(duration_ms, 2),
            field_count=len(result.fields),
            confidence=round(result.overall_confidence, 4),
        )
        return {
            "markdown": markdown,
            "json_structure": raw.get("json_structure") if isinstance(raw, dict) else {},
            "confidence": result.overall_confidence,
            "field_count": len(result.fields),
            "document_type": result.document_type,
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("tool_failed", tool="pdf_parse", error=str(e), duration_ms=round(duration_ms, 2))
        return {"error": str(e), "duration_ms": round(duration_ms, 2)}


# ---------------------------------------------------------------------------
# Tool 3: Table Extract
# ---------------------------------------------------------------------------

@tool
def table_extract_tool(file_path: Any = None, flavor: str = "auto", pages: list[int] | None = None) -> dict:
    """Extract tables from PDF using Camelot.

    Use for: Tabular data in PDFs (bank statements, assets/liabilities).
    Returns: Extracted tables as list of DataFrames (serialised to dicts).

    Args:
        file_path: Absolute path to the PDF file.
        flavor: Table detection flavor — "auto", "lattice", "stream", or "network".
        pages: Page numbers to extract (0-indexed). None means all pages.

    Returns:
        Dict with keys: tables (list of list-of-dicts), table_count, confidence, flavor, duration_ms.
    """
    start = time.monotonic()

    if file_path is None or not isinstance(file_path, str) or not file_path:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("tool_invalid_input", tool="table_extract", reason="file_path must be a non-empty string")
        return {"error": "file_path must be a non-empty string", "duration_ms": round(duration_ms, 2)}

    logger.info("tool_enter", tool="table_extract", file_path=file_path, flavor=flavor)

    if not _file_exists(file_path):
        return {"error": f"File not found: {file_path}", "duration_ms": 0}

    try:
        from src.infrastructure.document_processing.table_extractor import TableExtractor

        extractor = TableExtractor(flavor=flavor)
        pages_str = ",".join(str(p + 1) for p in pages) if pages else "all"
        result = _run_async(extractor.extract(file_path, pages=pages_str))

        tables_serialised = [df.to_dict(orient="records") for df in result.tables]

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool_complete",
            tool="table_extract",
            duration_ms=round(duration_ms, 2),
            table_count=result.table_count,
            confidence=round(result.confidence, 4),
        )
        return {
            "tables": tables_serialised,
            "table_count": result.table_count,
            "confidence": result.confidence,
            "flavor": result.flavor,
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("tool_failed", tool="table_extract", error=str(e), duration_ms=round(duration_ms, 2))
        return {"error": str(e), "duration_ms": round(duration_ms, 2)}


# ---------------------------------------------------------------------------
# Tool 4: Resume Parse
# ---------------------------------------------------------------------------

@tool
def resume_parse_tool(file_path: Any = None) -> dict:
    """Parse resume/CV using SmartResume.

    Use for: Resumes in DOCX or PDF format.
    Returns: Structured resume data (contact, experience, education, skills).

    Args:
        file_path: Absolute path to the resume file (DOCX or PDF).

    Returns:
        Dict with keys: full_name, email, phone, work_experience, education,
        skills, total_positions, current_employer, confidence, duration_ms.
    """
    start = time.monotonic()

    if file_path is None or not isinstance(file_path, str) or not file_path:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("tool_invalid_input", tool="resume_parse", reason="file_path must be a non-empty string")
        return {"error": "file_path must be a non-empty string", "duration_ms": round(duration_ms, 2)}

    logger.info("tool_enter", tool="resume_parse", file_path=file_path)

    if not _file_exists(file_path):
        return {"error": f"File not found: {file_path}", "duration_ms": 0}

    try:
        from src.infrastructure.document_processing.resume_parser import ResumeParser

        parser = ResumeParser()
        result = _run_async(parser.parse(file_path))

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool_complete",
            tool="resume_parse",
            duration_ms=round(duration_ms, 2),
            full_name=result.full_name,
            positions=result.total_positions,
        )
        return {
            "full_name": result.full_name,
            "email": result.email,
            "phone": result.phone,
            "location": result.location,
            "summary": result.summary,
            "years_of_experience": result.years_of_experience,
            "work_experience": [
                {
                    "job_title": exp.job_title,
                    "company": exp.company,
                    "start_date": str(exp.start_date) if exp.start_date else None,
                    "end_date": str(exp.end_date) if exp.end_date else None,
                    "is_current": exp.is_current,
                }
                for exp in (result.work_experience or [])
            ],
            "total_positions": result.total_positions,
            "current_employer": result.current_employer,
            "current_job_title": result.current_job_title,
            "education": [
                {
                    "degree": edu.degree,
                    "institution": edu.institution,
                    "field_of_study": edu.field_of_study,
                }
                for edu in (result.education or [])
            ],
            "highest_degree": result.highest_degree,
            "skills": result.skills or [],
            "skill_count": result.skill_count,
            "certifications": result.certifications or [],
            "confidence": result.extraction_confidence,
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("tool_failed", tool="resume_parse", error=str(e), duration_ms=round(duration_ms, 2))
        return {"error": str(e), "duration_ms": round(duration_ms, 2)}


# ---------------------------------------------------------------------------
# Tool 5: XLSX Extract
# ---------------------------------------------------------------------------

@tool
def xlsx_extract_tool(file_path: Any = None, sheet_name: str | None = None) -> dict:
    """Extract data from Excel file using openpyxl + pandas.

    Use for: Assets/liabilities statements in XLSX format.
    Returns: Extracted data as dict of sheet names to row data.

    Args:
        file_path: Absolute path to the Excel file.
        sheet_name: Specific sheet to extract. None means all sheets.

    Returns:
        Dict with keys: sheets (dict of sheet_name → list of row dicts),
        sheet_count, duration_ms.
    """
    start = time.monotonic()

    if file_path is None or not isinstance(file_path, str) or not file_path:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("tool_invalid_input", tool="xlsx_extract", reason="file_path must be a non-empty string")
        return {"error": "file_path must be a non-empty string", "duration_ms": round(duration_ms, 2)}

    logger.info("tool_enter", tool="xlsx_extract", file_path=file_path, sheet_name=sheet_name)

    if not _file_exists(file_path):
        return {"error": f"File not found: {file_path}", "duration_ms": 0}

    try:
        from src.infrastructure.document_processing.xlsx_extractor import XLSXExtractor

        extractor = XLSXExtractor()
        result = _run_async(extractor.extract(file_path, sheet_name=sheet_name))

        sheets_serialised = {
            name: df.to_dict(orient="records")
            for name, df in result.items()
        }

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool_complete",
            tool="xlsx_extract",
            duration_ms=round(duration_ms, 2),
            sheet_count=len(result),
        )
        return {
            "sheets": sheets_serialised,
            "sheet_count": len(result),
            "sheet_names": list(result.keys()),
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("tool_failed", tool="xlsx_extract", error=str(e), duration_ms=round(duration_ms, 2))
        return {"error": str(e), "duration_ms": round(duration_ms, 2)}


# ---------------------------------------------------------------------------
# Tool 6: Confidence Score
# ---------------------------------------------------------------------------

@tool
def confidence_score_tool(extracted_data: Any = None, document_type: str = "") -> dict:
    """Compute field-level confidence scores for extracted data.

    Use for: Assessing extraction quality after extraction.
    Returns: Confidence scores per field and overall document.

    Args:
        extracted_data: The extracted data dictionary for the document.
        document_type: One of emirates_id, bank_statement, credit_report,
            resume, assets_liabilities, application_form.

    Returns:
        Dict with keys: overall_confidence, routing_decision,
        field_confidences, low_confidence_fields.
    """
    start = time.monotonic()

    if extracted_data is None or not isinstance(extracted_data, dict):
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("tool_invalid_input", tool="confidence_score", reason="extracted_data must be a dict")
        return {
            "overall_confidence": 0.0,
            "routing_decision": "reject",
            "field_confidences": {},
            "low_confidence_fields": [],
            "error": "extracted_data must be a dict",
            "duration_ms": round(duration_ms, 2),
        }

    logger.info("tool_enter", tool="confidence_score", document_type=document_type)

    try:
        from src.infrastructure.document_processing.confidence import ConfidenceScorer

        scorer = ConfidenceScorer()

        # Build a lightweight object with attributes for the scorer
        class _DataProxy:
            def __init__(self, data: dict):
                self.__dict__.update(data)

        proxy = _DataProxy(extracted_data)

        # Attempt to use typed scorer; fall back to generic scoring
        score = scorer.compute_confidence(proxy, extracted_data.get("extraction_confidence"))

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool_complete",
            tool="confidence_score",
            duration_ms=round(duration_ms, 2),
            overall_confidence=round(score.overall_confidence, 4),
            routing_decision=score.routing_decision,
        )
        return {
            "overall_confidence": score.overall_confidence,
            "routing_decision": score.routing_decision,
            "field_confidences": score.field_confidences,
            "low_confidence_fields": score.low_confidence_fields,
            "duration_ms": round(duration_ms, 2),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("tool_failed", tool="confidence_score", error=str(e), duration_ms=round(duration_ms, 2))
        return {
            "overall_confidence": 0.5,
            "routing_decision": "spot_check",
            "field_confidences": {},
            "low_confidence_fields": [],
            "error": str(e),
            "duration_ms": round(duration_ms, 2),
        }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

ALL_EXTRACTION_TOOLS = [
    ocr_extract_tool,
    pdf_parse_tool,
    table_extract_tool,
    resume_parse_tool,
    xlsx_extract_tool,
    confidence_score_tool,
]
