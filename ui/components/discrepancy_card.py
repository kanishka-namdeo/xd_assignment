"""Structured discrepancy cards for cross-document validation results."""

from typing import Any

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

PRIORITY_COLORS: dict[str, dict[str, str]] = {
    "critical": {"border": "#dc3545", "bg": "#f8d7da", "text": "#721c24", "label": "Critical"},
    "high": {"border": "#fd7e14", "bg": "#fff3cd", "text": "#856404", "label": "High"},
    "medium": {"border": "#ffc107", "bg": "#fff9e6", "text": "#856404", "label": "Medium"},
    "low": {"border": "#007bff", "bg": "#e7f3ff", "text": "#004085", "label": "Low"},
}

DEFAULT_PRIORITY_COLORS: dict[str, str] = {
    "border": "#6c757d",
    "bg": "#f8f9fa",
    "text": "#495057",
    "label": "Info",
}


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_discrepancy_cards(discrepancies: list[dict[str, Any]]) -> None:
    """Render discrepancy data as styled cards.

    Args:
        discrepancies: List of discrepancy dicts with keys:
            - type: discrepancy type (identity_mismatch, income_mismatch, etc.)
            - priority: critical, high, medium, low
            - field: field name
            - value_a: value from first document
            - value_b: value from second document
            - document_a: first document type
            - document_b: second document type
    """
    if not discrepancies:
        return

    logger.info("discrepancy_cards_rendered", count=len(discrepancies))

    st.subheader("Document Discrepancies Detected")
    st.caption("The following inconsistencies were found across your uploaded documents.")

    for disc in discrepancies:
        priority = disc.get("priority", "low").lower()
        colors = PRIORITY_COLORS.get(priority, DEFAULT_PRIORITY_COLORS)

        field = disc.get("field", "Unknown Field")
        value_a = str(disc.get("value_a", "N/A"))
        value_b = str(disc.get("value_b", "N/A"))
        doc_a = disc.get("document_a", "Document A")
        doc_b = disc.get("document_b", "Document B")
        disc_type = disc.get("type", "Unknown")

        card_html = f"""
        <div style='
            background: {colors["bg"]};
            border-left: 5px solid {colors["border"]};
            border-radius: 8px;
            padding: 16px 20px;
            margin: 12px 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        '>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;'>
                <strong style='color:{colors["text"]};font-size:15px;'>{field}</strong>
                <span style='
                    background:{colors["border"]};color:white;
                    padding:2px 10px;border-radius:12px;
                    font-size:11px;font-weight:600;text-transform:uppercase;
                '>{colors["label"]}</span>
            </div>

            <div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;'>
                <div style='
                    background:white;border-radius:6px;padding:10px 14px;
                    border:1px solid #e9ecef;
                '>
                    <p style='margin:0 0 4px 0;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;'>{_escape_html(doc_a)}</p>
                    <p style='margin:0;color:{colors["text"]};font-size:14px;font-weight:500;'>{_escape_html(value_a)}</p>
                </div>
                <div style='
                    background:white;border-radius:6px;padding:10px 14px;
                    border:1px solid #e9ecef;
                '>
                    <p style='margin:0 0 4px 0;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;'>{_escape_html(doc_b)}</p>
                    <p style='margin:0;color:{colors["text"]};font-size:14px;font-weight:500;'>{_escape_html(value_b)}</p>
                </div>
            </div>

            <p style='margin:8px 0 0 0;color:#6c757d;font-size:12px;'>Type: {disc_type}</p>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
