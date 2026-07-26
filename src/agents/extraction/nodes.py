"""Extraction node functions and Gate 1 integration.

Delegates agent construction and per-document processing to
agent_runner.py. Only contains graph-level node orchestration.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from src.agents.extraction.agent_runner import (
    MAX_EXTRACTION_RETRIES,
    build_extraction_agent,
    build_llm_from_settings,
    process_single_document,
)
from src.agents.extraction.output import ExtractionOutput
from src.agents.extraction.parsers import (
    _extract_json_from_text,
    _parse_agent_output,
    _regex_fallback_extraction,
)
from src.agents.gates.document_integrity import validate_document_integrity
from src.agents.state import ApplicantState

# Re-export for backward compatibility with tests
__all__ = [
    "ExtractionOutput",
    "MAX_EXTRACTION_RETRIES",
    "_extract_json_from_text",
    "_parse_agent_output",
    "_regex_fallback_extraction",
    "_build_extraction_agent",
    "validate_document_integrity",
]

# Backward-compatible aliases for tests that patch the old names
_build_extraction_agent = build_extraction_agent

logger = structlog.get_logger(__name__)


async def extract_documents_node(state: ApplicantState) -> dict[str, Any]:
    """Phase 3a: Extract data from uploaded documents using ReAct agent."""
    start = time.monotonic()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    uploaded_documents = state.get("uploaded_documents", [])

    logger.info(
        "node_enter",
        node="extract_documents",
        application_id=application_id,
        applicant_id=applicant_id,
        document_count=len(uploaded_documents),
    )

    if not uploaded_documents:
        logger.warning("no_documents_to_extract", application_id=application_id)
        return {
            "extracted_data": {},
            "extraction_confidence": {},
            "gate_status": "passed",
            "gate_errors": [],
        }

    from src.agents.orchestrator.nodes import _get_llm_client

    llm_client = _get_llm_client()
    if llm_client is None:
        logger.error("llm_client_not_available", application_id=application_id)
        return {
            "extracted_data": {},
            "extraction_confidence": {},
            "gate_status": "failed",
            "gate_errors": ["LLM client not available for extraction agent"],
        }

    try:
        llm = build_llm_from_settings()
        agent = build_extraction_agent(llm)
    except Exception as e:
        logger.exception("agent_build_failed", error=str(e), application_id=application_id)
        return {
            "extracted_data": {},
            "extraction_confidence": {},
            "gate_status": "failed",
            "gate_errors": [f"Failed to build extraction agent: {e}"],
        }

    extracted_data: dict[str, Any] = {}
    extraction_confidence: dict[str, float] = {}
    all_gate_errors: list[str] = []
    gate_passed_all = True

    for doc_info in uploaded_documents:
        doc_id = doc_info.get("document_id", "unknown")
        doc_type = doc_info.get("document_type", "unknown")
        file_path = doc_info.get("file_path", "")

        logger.info(
            "document_extraction_start",
            document_id=doc_id,
            document_type=doc_type,
            file_path=file_path,
        )

        success, fields, confidence, errors = await process_single_document(
            agent, doc_id, doc_type, file_path
        )

        if success and fields is not None:
            extracted_data[doc_id] = fields
            extraction_confidence[doc_id] = confidence
        else:
            gate_passed_all = False
            all_gate_errors.extend(
                [f"Document {doc_id} ({doc_type}): {err}" for err in errors]
            )
            logger.warning(
                "document_extraction_failed",
                document_id=doc_id,
                document_type=doc_type,
                total_attempts=0,
                errors=errors,
            )

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "node_exit",
        node="extract_documents",
        duration_ms=round(duration_ms, 2),
        documents_processed=len(uploaded_documents),
        documents_succeeded=len(extracted_data),
        documents_failed=len(uploaded_documents) - len(extracted_data),
        gate_status="passed" if gate_passed_all else "failed",
    )

    return {
        "extracted_data": extracted_data,
        "extraction_confidence": extraction_confidence,
        "gate_status": "passed" if gate_passed_all else "failed",
        "gate_errors": all_gate_errors,
    }


def summarize_extraction_node(state: ApplicantState) -> dict[str, Any]:
    """Phase 3b: Summarize extraction results and prepare for validation."""
    start = time.monotonic()
    application_id = state.get("application_id")
    extracted_data = state.get("extracted_data", {})
    extraction_confidence = state.get("extraction_confidence", {})
    gate_status = state.get("gate_status", "unknown")
    gate_errors = state.get("gate_errors", [])

    logger.info(
        "node_enter",
        node="summarize_extraction",
        application_id=application_id,
        document_count=len(extracted_data),
        gate_status=gate_status,
    )

    if gate_status == "passed":
        avg_confidence = (
            sum(extraction_confidence.values()) / len(extraction_confidence)
            if extraction_confidence
            else 0.0
        )
        message = (
            f"Document extraction complete. Successfully extracted data from "
            f"{len(extracted_data)} document(s) with average confidence "
            f"{avg_confidence:.2%}. All documents passed integrity checks."
        )
    else:
        error_count = len(gate_errors)
        message = (
            f"Document extraction encountered issues. Extracted data from "
            f"{len(extracted_data)} document(s), but {error_count} integrity "
            f"check(s) failed. These issues will be reviewed in the next phase."
        )

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "node_exit",
        node="summarize_extraction",
        duration_ms=round(duration_ms, 2),
        gate_status=gate_status,
    )

    return {
        "messages": [{"role": "assistant", "content": message}],
    }
