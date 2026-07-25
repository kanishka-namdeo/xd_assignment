"""Sidebar document checklist and status display."""

from typing import Any

import streamlit as st

STATUS_ICONS: dict[str, str] = {
    "uploaded": "✅",
    "verified": "✅",
    "pending": "⏳",
    "processing": "⏳",
    "missing": "❌",
    "rejected": "❌",
    "failed": "❌",
}

REQUIRED_DOCS: list[str] = [
    "Emirates ID",
    "Bank Statement",
    "Credit Report",
    "Resume",
    "Assets & Liabilities",
    "Application Form",
]


def render_document_status(documents: list[dict[str, Any]] | None) -> None:
    """Render the document checklist in the sidebar."""
    if not documents:
        st.subheader("Documents")
        st.caption("No documents uploaded yet.")
        st.markdown("---")
        return

    st.subheader("Documents")

    uploaded_names = {doc.get("doc_type", "").lower(): doc for doc in documents}

    for required in REQUIRED_DOCS:
        key = required.lower()
        if key in uploaded_names:
            doc = uploaded_names[key]
            icon = STATUS_ICONS.get(doc.get("status", "pending"), "⏳")
            status = doc.get("status", "pending").replace("_", " ").title()
            st.markdown(f"{icon} {required} — {status}")
        else:
            st.markdown(f"❌ {required} — Missing")

    st.markdown("---")

    uploaded_count = sum(
        1 for doc in documents if doc.get("status") in ("uploaded", "verified")
    )
    st.caption(f"{uploaded_count}/{len(documents)} documents verified")


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
