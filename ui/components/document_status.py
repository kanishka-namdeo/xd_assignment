"""Sidebar document checklist and status display."""

from typing import Any

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

STATUS_ICONS: dict[str, str] = {
    "uploaded": "✅",
    "verified": "✅",
    "pending": "⏳",
    "processing": "⏳",
    "missing": "❌",
    "rejected": "❌",
    "failed": "❌",
}

# Document requirements by support category (matches spec)
# TODO: Replace with centralized constants from src.domain.constants.document_types once populated
REQUIRED_DOCS_BY_CATEGORY: dict[str, list[str]] = {
    "divorced": ["emirates_id", "bank_statement", "credit_report", "application_form"],
    "abandoned": ["emirates_id", "bank_statement", "credit_report", "application_form"],
    "unknown_parentage": ["emirates_id", "bank_statement", "application_form"],
    "health_disability": ["emirates_id", "bank_statement", "credit_report", "application_form", "resume"],
}

# Default required docs if category is unknown
DEFAULT_REQUIRED_DOCS: list[str] = ["emirates_id", "bank_statement", "credit_report", "application_form"]

try:
    from src.domain.constants.document_types import (
        DEFAULT_REQUIRED_DOCUMENTS as _central_default,
        REQUIRED_DOCUMENTS as _central_required,
    )

    if _central_required:
        REQUIRED_DOCS_BY_CATEGORY = _central_required
    if _central_default:
        DEFAULT_REQUIRED_DOCS = _central_default
except ImportError:
    pass

# Display names for document types
DOC_DISPLAY_NAMES: dict[str, str] = {
    "emirates_id": "Emirates ID",
    "bank_statement": "Bank Statement",
    "credit_report": "Credit Report",
    "resume": "Resume",
    "assets_liabilities": "Assets & Liabilities",
    "application_form": "Application Form",
}


def get_required_docs_for_category(support_category: str | None) -> list[str]:
    """Return the list of required document types for a given support category."""
    if support_category:
        return REQUIRED_DOCS_BY_CATEGORY.get(support_category, DEFAULT_REQUIRED_DOCS)
    return DEFAULT_REQUIRED_DOCS


def render_document_progress(support_category: str | None = None) -> None:
    """Render a progress bar showing document upload completion."""
    uploaded_docs = st.session_state.get("uploaded_documents", {}) or {}
    required = get_required_docs_for_category(support_category)

    # uploaded_docs is a dict keyed by doc_type
    uploaded_types = {k.lower() for k in uploaded_docs.keys()}
    uploaded_count = len([doc for doc in required if doc.lower() in uploaded_types])
    total_count = len(required)
    progress = uploaded_count / total_count if total_count > 0 else 0

    st.markdown(f"**Documents:** {uploaded_count} of {total_count} uploaded")
    st.progress(progress)

    if uploaded_count == total_count and total_count > 0:
        st.success("All required documents uploaded!")

    logger.debug(
        "document_progress_rendered",
        uploaded=uploaded_count,
        total=total_count,
        progress=progress,
    )


def render_document_status(
    documents: list[dict[str, Any]] | None,
    support_category: str | None = None,
) -> None:
    """Render the document checklist in the sidebar.

    Args:
        documents: List of uploaded document dicts with doc_type and status.
        support_category: The applicant's support category to determine required docs.
    """
    required_docs = get_required_docs_for_category(support_category)
    required_display = [DOC_DISPLAY_NAMES.get(doc, doc.replace("_", " ").title()) for doc in required_docs]

    if not documents:
        logger.debug("document_status_rendered", document_count=0)
        st.subheader("Documents")
        st.caption("No documents uploaded yet.")
        st.markdown("---")
        return

    st.subheader("Documents")
    logger.debug(
        "document_status_rendered",
        document_count=len(documents),
        statuses=[doc.get("status") for doc in documents],
    )

    uploaded_names = {doc.get("doc_type", "").lower(): doc for doc in documents}

    for doc_type in required_docs:
        display_name = DOC_DISPLAY_NAMES.get(doc_type, doc_type.replace("_", " ").title())
        if doc_type in uploaded_names:
            doc = uploaded_names[doc_type]
            icon = STATUS_ICONS.get(doc.get("status", "pending"), "⏳")
            status = doc.get("status", "pending").replace("_", " ").title()
            st.markdown(f"{icon} {display_name} — {status}")
        else:
            st.markdown(f"❌ {display_name} — Missing")

    st.markdown("---")

    uploaded_count = sum(
        1 for doc in documents if doc.get("status") in ("uploaded", "verified")
    )
    st.caption(f"{uploaded_count}/{len(required_docs)} required documents verified")


def render_document_summary(documents: list[dict[str, Any]] | None) -> None:
    """Render a compact document summary for the chat page header area."""
    if not documents:
        return
    uploaded = sum(1 for d in documents if d.get("status") in ("uploaded", "verified"))
    total = len(documents)
    if uploaded == total:
        st.success(f"All {total} documents verified ✅")
    elif uploaded > 0:
        st.info(f"{uploaded}/{total} documents verified")
