"""Extraction output parsing helpers for ReAct agent responses."""

from __future__ import annotations

import json
import re

import structlog
from langchain_core.messages import BaseMessage

logger = structlog.get_logger(__name__)

_REGEX_PATTERNS = {
    "identity_number": r"\b(784-\d{4}-\d{7}-\d)\b",
    "full_name": r"(?:Name|الاسم)[:\s]+([A-Za-z\s]+)",
    "date_of_birth": r"(?:DOB|Date of Birth|تاريخ الميلاد)[:\s]+(\d{4}-\d{2}-\d{2})",
    "nationality": r"(?:Nationality|الجنسية)[:\s]+([A-Za-z\s]+)",
    "gender": r"(?:Gender|الجنس)[:\s]+(Male|Female|ذكر|أنثى)",
}


def _extract_json_from_text(text: str) -> str | None:
    """Extract JSON block from text using regex."""
    code_block_pattern = r"```(?:json)?\s*\n([\s\S]*?)\n\s*```"
    match = re.search(code_block_pattern, text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    json_pattern = r"\{[\s\S]*\}"
    match = re.search(json_pattern, text)
    if match:
        return match.group(0).strip()

    return None


def _regex_fallback_extraction(text: str, doc_type: str) -> dict:
    """Fallback extraction using regex patterns when JSON parsing fails."""
    logger.info("regex_fallback_extraction", doc_type=doc_type)

    result: dict = {
        "document_type": doc_type,
        "extraction_confidence": 0.3,
        "_extraction_method": "regex_fallback",
    }

    for field, pattern in _REGEX_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()

    if len(result) > 3:
        return result
    return {}


def _parse_agent_output(message: BaseMessage | None, doc_type: str) -> dict:
    """Parse the final message from the ReAct agent into structured data."""
    from src.agents.extraction.output import ExtractionOutput
    from pydantic import ValidationError

    if message is None:
        return {}

    content = message.content if hasattr(message, "content") else str(message)

    json_str = _extract_json_from_text(content)
    if not json_str:
        logger.warning("agent_output_no_json_found", content_preview=content[:200] if content else "")
        return {}

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("agent_output_json_parse_failed", error=str(e), json_preview=json_str[:200])
        return _regex_fallback_extraction(content, doc_type)

    if not isinstance(parsed, dict):
        logger.warning("agent_output_not_dict", output_type=type(parsed).__name__)
        return {}

    try:
        if "document_type" not in parsed:
            parsed["document_type"] = doc_type
        validated = ExtractionOutput(**parsed)
        return validated.model_dump()
    except ValidationError as e:
        logger.warning("agent_output_pydantic_validation_failed", error=str(e), json_preview=json_str[:200])
        return parsed
