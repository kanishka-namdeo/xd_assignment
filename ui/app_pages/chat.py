"""Phases 1-6: Chat-based application interface."""

import streamlit as st

from ui.components.chat_input import render_chat_input
from ui.components.document_status import (
    render_document_status,
    render_document_summary,
)
from ui.components.phase_tracker import render_phase_tracker
from ui.fragments.chat_area import render_chat_area

ALLOWED_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "xlsx", "docx"]


def _ensure_authenticated() -> bool:
    """Redirect to landing if not authenticated. Returns True if authenticated."""
    if not st.session_state.get("authenticated"):
        st.switch_page("app_pages/landing.py")
        return False
    return True


def _render_header() -> None:
    """Render the page header with phase info."""
    st.title("Social Support Application")
    phase = st.session_state.get("current_phase", "intake")
    render_document_summary(st.session_state.get("uploaded_documents"))


def _render_sidebar() -> None:
    """Render the sidebar with phase tracker and document status."""
    with st.sidebar:
        st.markdown("### Application")
        render_phase_tracker(st.session_state.get("current_phase", "intake"))
        render_document_status(st.session_state.get("uploaded_documents"))

        st.markdown("---")
        if st.button("Log Out", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.switch_page("app_pages/landing.py")


def render() -> None:
    """Render the chat application page."""
    if not _ensure_authenticated():
        return

    st.set_page_config(page_title="Application Chat", layout="wide")

    _render_header()
    _render_sidebar()

    render_chat_area()
