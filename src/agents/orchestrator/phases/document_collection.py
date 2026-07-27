"""Phase 2: Document Collection - classify uploaded files and track missing docs."""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path

import structlog
from langgraph.types import interrupt

from src.agents.orchestrator.di import _make_assistant_message
from src.agents.state import ApplicantState
from src.domain.constants.document_types import DEFAULT_REQUIRED_DOCUMENTS, REQUIRED_DOCUMENTS
from src.domain.document_classifier import classify_document
from src.infrastructure.db.models.document import Document
from src.infrastructure.db.repositories.document_repo import DocumentRepository
from src.infrastructure.db.session import get_session_factory
from src.services.document_service import get_file_format

logger = structlog.get_logger(__name__)

# Document persistence is injected before graph compilation.
_session_factory = None
_persist_documents = False


def set_document_persistence(session_factory) -> None:
    """Inject the async session factory for document persistence."""
    global _session_factory
    _session_factory = session_factory


def enable_document_persistence() -> None:
    """Turn on DB persistence for documents (call after set_document_persistence)."""
    global _persist_documents
    _persist_documents = True


async def _persist_document_to_db(
    applicant_id_str: str,
    file_path: str,
    document_type: str,
) -> uuid.UUID | None:
    """Create a Document ORM row and return its UUID.

    Returns None if persistence is disabled or the DB write fails.
    """
    if not _persist_documents or _session_factory is None:
        return None

    try:
        path = Path(file_path)
        if path.exists():
            content = path.read_bytes()
            file_hash = hashlib.sha256(content).hexdigest()
            size_bytes = len(content)
        else:
            file_hash = hashlib.sha256(file_path.encode()).hexdigest()
            size_bytes = None

        session = _session_factory()
        repo = DocumentRepository(session)
        document = await repo.create(
            applicant_id=uuid.UUID(applicant_id_str),
            document_type=document_type,
            file_path=file_path,
            file_format=get_file_format(file_path),
            file_size_bytes=size_bytes,
            file_hash=file_hash,
            processing_status="uploaded",
        )
        logger.info(
            "document_persisted",
            document_id=str(document.id),
            document_type=document_type,
            applicant_id=applicant_id_str,
        )
        return document.id
    except Exception as e:
        logger.exception(
            "document_persist_failed",
            file_path=file_path,
            document_type=document_type,
            error=str(e),
        )
        return None


async def document_collection_node(state: ApplicantState) -> ApplicantState:
    """Phase 2: Document Collection - classify uploaded files and track missing docs.

    Reads state['uploaded_files'], classifies each via classify_document,
    merges into uploaded_documents, compares against REQUIRED_DOCUMENTS,
    and transitions to processing only when all required docs are present.
    Uses interrupt() to pause when documents are missing.
    """
    start_ms = time.perf_counter()
    
    uploaded_files = state.get("uploaded_files", [])
    existing_docs = list(state.get("uploaded_documents", []))
    
    logger.info(
        "node_enter",
        node="document_collection",
        current_phase=state.get("current_phase"),
        applicant_id=state.get("applicant_id"),
        uploaded_files_count=len(uploaded_files),
        uploaded_files=uploaded_files,
        existing_docs_count=len(existing_docs),
    )

    applicant_info = state.get("applicant_info", {})
    support_category = applicant_info.get("support_category", "")

    # Classify newly uploaded files and merge with existing documents
    existing_file_paths = {d.get("file_path") for d in existing_docs}
    new_doc_entries: list[dict[str, str]] = []
    for fp in uploaded_files:
        if fp in existing_file_paths:
            continue
        doc_type = classify_document(fp)
        doc_id = str(uuid.uuid4())
        new_doc_entries.append({
            "document_id": doc_id,
            "document_type": doc_type,
            "file_path": fp,
            "status": "uploaded",
        })
    uploaded_documents = existing_docs + new_doc_entries

    if new_doc_entries:
        logger.info(
            "documents_classified",
            new_count=len(new_doc_entries),
            total_count=len(uploaded_documents),
            doc_types=[d["document_type"] for d in new_doc_entries],
        )

        # Persist newly classified documents to the DB.
        # Replace the in-memory document_id with the DB-generated UUID so
        # downstream extraction can reference the real Document row.
        applicant_id_str = state.get("applicant_id")
        if applicant_id_str:
            for entry in new_doc_entries:
                db_id = await _persist_document_to_db(
                    applicant_id_str,
                    entry["file_path"],
                    entry["document_type"],
                )
                if db_id is not None:
                    entry["document_id"] = str(db_id)
                    logger.info(
                        "document_id_updated",
                        file_path=entry["file_path"],
                        document_type=entry["document_type"],
                        db_document_id=str(db_id),
                    )

    # Determine required vs. uploaded
    required = REQUIRED_DOCUMENTS.get(support_category, DEFAULT_REQUIRED_DOCUMENTS)
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
            "new_documents_uploaded": bool(new_doc_entries),
        }

    # Missing documents - check if we're resuming from an interrupt
    missing_display = ", ".join(t.replace("_", " ").title() for t in missing_types)
    
    # If we have new documents that were just classified, this is a resume after interrupt
    # Return the state update with the classified documents
    if new_doc_entries:
        response = (
            f"We've received your documents. "
            f"We still need the following required document(s): {missing_display}. "
            f"Please upload them by attaching the files to your message."
        )
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
        check_state_size(state, node_name="document_collection", application_id=state.get("applicant_id"))
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "document_collection",
            "uploaded_documents": uploaded_documents,
            "new_documents_uploaded": True,
        }
    
    # No new documents - this is the first time or user didn't upload anything
    # Call interrupt to ask for documents
    if uploaded_files:
        response = (
            f"We've received your files. "
            f"We still need the following required document(s): {missing_display}. "
            f"Please upload them by attaching the files to your message."
        )
    else:
        response = (
            f"I understand you need some help. To continue with your application, "
            f"we still need the following required document(s): {missing_display}. "
            f"Please upload them by attaching the files to your message."
        )
    
    interrupt({
        "question": f"We still need the following required document(s): {missing_display}. Please upload them by attaching the files to your message.",
        "missing_documents": missing_types,
        "phase": "document_collection",
    })
    
    # This return is a fallback (interrupt should prevent reaching here)
    return {
        "messages": [_make_assistant_message(response)],
        "current_phase": "document_collection",
        "uploaded_documents": uploaded_documents,
    }
