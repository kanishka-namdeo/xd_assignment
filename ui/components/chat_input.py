"""Chat input component with multi-file upload support."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

SUPPORTED_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "xlsx", "docx"]


@dataclass
class ChatInputResult:
    """Result of a chat input submission."""

    text: str
    files: list[dict[str, Any]] | None = None


def render_chat_input() -> ChatInputResult | None:
    """Render the chat input widget and return submitted data, or None.

    Returns a ChatInputResult when the user submits a message, otherwise None.
    """
    prompt = st.chat_input(
        placeholder="Type your message or attach documents...",
        accept_file="multiple",
        file_type=SUPPORTED_FILE_TYPES,
        submit_mode="disable",
    )

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
