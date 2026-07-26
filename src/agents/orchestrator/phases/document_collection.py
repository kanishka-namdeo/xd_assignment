"""Phase 2: Document Collection - classify uploaded files and track missing docs."""

from __future__ import annotations

import time
import uuid

import structlog
from langgraph.types import interrupt

from src.agents.orchestrator.di import _make_assistant_message
from src.agents.state import ApplicantState
from src.domain.document_classifier import classify_document

logger = structlog.get_logger(__name__)

REQUIRED_DOCUMENTS: dict[str, list[str]] = {
    "divorced": ["emirates_id", "bank_statement", "credit_report", "application_form"],
    "abandoned": ["emirates_id", "bank_statement", "credit_report", "application_form"],
    "unknown_parentage": ["emirates_id", "bank_statement", "application_form"],
    "health_disability": ["emirates_id", "bank_statement", "credit_report", "application_form", "resume"],
}
DEFAULT_REQUIRED: list[str] = ["emirates_id", "bank_statement", "credit_report", "application_form"]


async def document_collection_node(state: ApplicantState) -> ApplicantState:
    """Phase 2: Document Collection - classify uploaded files and track missing docs.

    Reads state['uploaded_files'], classifies each via classify_document,
    merges into uploaded_documents, compares against REQUIRED_DOCUMENTS,
    and transitions to processing only when all required docs are present.
    Uses interrupt() to pause when documents are missing.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", node="document_collection", current_phase=state.get("current_phase"), applicant_id=state.get("applicant_id"))

    applicant_info = state.get("applicant_info", {})
    support_category = applicant_info.get("support_category", "")
    uploaded_files = state.get("uploaded_files", [])
    existing_docs = list(state.get("uploaded_documents", []))

    # Classify newly uploaded files and merge with existing documents
    existing_file_paths = {d.get("file_path") for d in existing_docs}
    new_doc_entries: list[dict[str, str]] = []
    for fp in uploaded_files:
        if fp in existing_file_paths:
            continue
        doc_type = classify_document(fp)
        new_doc_entries.append({
            "document_id": str(uuid.uuid4()),
            "document_type": doc_type,
            "file_path": fp,
        })
    uploaded_documents = existing_docs + new_doc_entries

    if new_doc_entries:
        logger.info(
            "documents_classified",
            new_count=len(new_doc_entries),
            total_count=len(uploaded_documents),
            doc_types=[d["document_type"] for d in new_doc_entries],
        )

    # Determine required vs. uploaded
    required = REQUIRED_DOCUMENTS.get(support_category, DEFAULT_REQUIRED)
    uploaded_types = {d["document_type"] for d in uploaded_documents}
    missing_types = [doc_type for doc_type in required if doc_type not in uploaded_types]

    if not missing_types:
        response = (
            "Thank you. We have received all required documents. "
            "We will now process them to extract and validate the information. "
            "This typically takes a few moments."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "node_exit",
            node="document_collection",
            duration_ms=round(duration_ms, 2),
            next_phase="processing",
            uploaded_count=len(uploaded_documents),
            required_count=len(required),
            missing_count=0,
        )
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "processing",
            "uploaded_documents": uploaded_documents,
        }

    # Missing documents - use interrupt() to pause and ask the user
    missing_display = ", ".join(t.replace("_", " ").title() for t in missing_types)
    response = (
        f"Thank you for uploading your documents. "
        f"We still need the following required document(s): {missing_display}. "
        f"Please upload them by attaching the files to your message."
    )

    # interrupt() pauses the graph and returns user response when resumed
    user_response = interrupt({
        "question": f"We still need the following required document(s): {missing_display}. Please upload them by attaching the files to your message.",
        "missing_documents": missing_types,
        "phase": "document_collection",
    })

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info(
        "node_exit",
        node="document_collection",
        duration_ms=round(duration_ms, 2),
        next_phase="document_collection",
        uploaded_count=len(uploaded_documents),
        required_count=len(required),
        missing_count=len(missing_types),
    )

    return {
        "messages": [_make_assistant_message(response)],
        "current_phase": "document_collection",
        "uploaded_documents": uploaded_documents,
    }
