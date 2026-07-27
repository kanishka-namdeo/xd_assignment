"""Phases 1-6: Chat-based application interface."""

import streamlit as st
import structlog

from ui.components.chat_input import render_chat_input
from ui.components.document_status import (
    render_document_progress,
    render_document_status,
    render_document_summary,
)
from ui.components.accessibility_controls import render_accessibility_controls, get_accessibility_css
from ui.components.phase_guidance import render_phase_guidance
from ui.components.phase_tracker import render_phase_tracker
from ui.components.help_panel import render_help_panel
from ui.fragments.chat_area import render_chat_area

logger = structlog.get_logger(__name__)

ALLOWED_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "xlsx", "docx"]

PHASE_LABELS = {
    "authentication": "Authentication",
    "intake": "Intake",
    "document_collection": "Document Collection",
    "processing": "Processing",
    "review": "Review",
    "decision": "Decision",
    "enablement": "Enablement",
}


def _mask_emirates_id(identity_number: str | None) -> str:
    """Mask Emirates ID, showing only the last digit: ***-****-XXXXXXX-C."""
    if not identity_number:
        return "***-****-*******-*"
    digits = identity_number.replace("-", "").replace(" ", "")
    if len(digits) < 1:
        return "***-****-*******-*"
    last = digits[-1]
    return f"***-****-*******-{last}"


def _ensure_authenticated() -> bool:
    """Redirect to landing if not authenticated. Returns True if authenticated."""
    if not st.session_state.get("authenticated"):
        st.switch_page(st.session_state.pages["login"])
        return False
    return True


def _render_header() -> None:
    """Render the page header with phase badge and masked Emirates ID."""
    col_title, col_badge = st.columns([4, 1])
    with col_title:
        st.title("Social Support Application")
    with col_badge:
        phase = st.session_state.get("current_phase", "intake")
        phase_label = PHASE_LABELS.get(phase, phase)
        st.markdown(
            f"""
            <span class="phase-badge">{phase_label}</span>
            """,
            unsafe_allow_html=True,
        )

    identity_number = st.session_state.get("identity_number")
    masked = _mask_emirates_id(identity_number)
    st.markdown(
        f'<div class="header-identity">Emirates ID: {masked}</div>',
        unsafe_allow_html=True,
    )

    render_document_summary(st.session_state.get("uploaded_documents"))

    # Accessibility controls in header
    render_accessibility_controls()


def _render_sidebar() -> None:
    """Render the sidebar with phase tracker, document status, and logout."""
    with st.sidebar:
        st.markdown("### Application")
        st.markdown(
            '<div class="session-saved">Session auto-saved</div>',
            unsafe_allow_html=True,
        )
        render_phase_tracker(st.session_state.get("current_phase", "intake"))

        # Get support category from applicant info for dynamic document requirements
        applicant_info = st.session_state.get("applicant_info", {})
        support_category = applicant_info.get("support_category") if isinstance(applicant_info, dict) else None
        render_document_progress(support_category=support_category)
        uploaded_docs = st.session_state.get("uploaded_documents", {})
        render_document_status(
            list(uploaded_docs.values()) if isinstance(uploaded_docs, dict) else uploaded_docs,
            support_category=support_category,
        )

        render_help_panel()

        st.markdown("---")

        # Logout confirmation flow
        if st.session_state.get("show_logout_confirm"):
            st.warning("Are you sure you want to log out?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, log out", use_container_width=True, key="logout_confirm_yes"):
                    pages = st.session_state.get("pages", {})
                    # Preserve widget keys to avoid stability errors
                    widget_keys = {"emirates_id_input", "chat_input"}
                    preserved = {k: st.session_state[k] for k in widget_keys if k in st.session_state}
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    # Restore preserved widget keys
                    for k, v in preserved.items():
                        st.session_state[k] = v
                    st.session_state.show_logout_confirm = False
                    if "login" in pages:
                        st.switch_page(pages["login"])
            with col_no:
                if st.button("Cancel", use_container_width=True, key="logout_confirm_no"):
                    st.session_state.show_logout_confirm = False
                    st.rerun()
        else:
            if st.button("Log Out", use_container_width=True, key="logout_button"):
                st.session_state.show_logout_confirm = True
                st.rerun()


def _render_session_restore_banner() -> None:
    """Show a one-time session restore banner at the top of the chat area."""
    if st.session_state.get("session_restore_shown"):
        return

    state_snapshot = st.session_state.get("state_snapshot")
    if not state_snapshot:
        st.session_state.session_restore_shown = True
        return

    phase = st.session_state.get("current_phase", "intake")
    phase_label = PHASE_LABELS.get(phase, phase)
    messages = state_snapshot.get("messages", [])
    documents = st.session_state.get("uploaded_documents", [])

    st.markdown(
        f"""
        <div class="session-restore-banner">
            <strong>Session restored.</strong> You are at <strong>Phase {phase_label}</strong>.
            {len(messages)} messages and {len(documents)} document(s) from your previous session are available.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.session_state.session_restore_shown = True


def render() -> None:
    """Render the chat application page."""
    logger.debug("chat_page_render", phase=st.session_state.get("current_phase", "intake"))
    if not _ensure_authenticated():
        return

    # Inject accessibility CSS on every rerun so it picks up session state changes
    st.markdown(
        f"<style>{get_accessibility_css()}</style>",
        unsafe_allow_html=True,
    )

    _render_header()
    _render_sidebar()

    # Show session restore banner on first render after restore
    _render_session_restore_banner()

    # Render per-phase guidance panel
    render_phase_guidance()

    render_chat_area()
