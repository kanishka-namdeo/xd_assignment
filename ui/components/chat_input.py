"""Chat input component with multi-file upload support."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

SUPPORTED_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "xlsx", "docx"]

PHASE_PLACEHOLDERS: dict[str, str] = {
    "authentication": "Enter your Emirates ID number...",
    "intake": "Type your answer...",
    "document_collection": "Attach your documents here (PDF, images, DOCX, XLSX)...",
    "processing": "Please wait while we process your documents...",
    "review": "Type your clarification or attach corrected documents...",
    "decision": "Please wait while we finalize your decision...",
    "enablement": "Ask a follow-up question...",
}

PHASE_HINTS: dict[str, str] = {
    "document_collection": "Accepted formats: PDF, PNG, JPG, DOCX, XLSX. You can upload multiple files at once.",
    "review": "You can attach corrected documents or type your clarification.",
    "enablement": "Have questions about your decision or next steps?",
}


@dataclass
class ChatInputResult:
    """Result of a chat input submission."""

    text: str
    files: list[dict[str, Any]] | None = None


def _get_current_phase() -> str:
    """Return the current application phase from session state."""
    return st.session_state.get("current_phase", "intake")


def render_chat_input() -> ChatInputResult | None:
    """Render the chat input widget and return submitted data, or None.

    Returns a ChatInputResult when the user submits a message, otherwise None.
    """
    phase = _get_current_phase()
    placeholder = PHASE_PLACEHOLDERS.get(phase, "Type your message or attach documents...")

    prompt = st.chat_input(
        placeholder=placeholder,
        accept_file="multiple",
        file_type=SUPPORTED_FILE_TYPES,
        submit_mode="disable",
    )

    hint_text = PHASE_HINTS.get(phase)
    if hint_text:
        st.caption(hint_text)

    if not prompt:
        return None

    result = ChatInputResult(text=prompt.text or "")

    if prompt.files:
        result.files = [
            {"name": f.name, "size": f.size, "data": f} for f in prompt.files
        ]
        logger.info(
            "files_uploaded",
            file_count=len(result.files),
            file_types=list({Path(f["name"]).suffix.lstrip(".") for f in result.files}),
        )

    logger.info("message_submitted", has_files=bool(result.files))

    return result
