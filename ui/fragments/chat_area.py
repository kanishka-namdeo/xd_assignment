"""@st.fragment wrapped chat area for the application flow."""

import tempfile
from pathlib import Path
from typing import Any

import requests
import streamlit as st
import structlog

from ui.components.chat_input import ChatInputResult, render_chat_input
from ui.components.decision_card import render_decision_card
from ui.components.discrepancy_card import render_discrepancy_cards
from ui.components.enablement_section import render_enablement_section

logger = structlog.get_logger(__name__)

API_BASE = "http://localhost:8000"
UPLOAD_DIR = Path("data/uploads")


def _save_files(application_id: str, files: list[dict[str, Any]]) -> list[str]:
    """Persist uploaded files to disk and return their paths."""
    upload_dir = UPLOAD_DIR / application_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []

    for f in files:
        dest = upload_dir / f["name"]
        data = f["data"]
        if hasattr(data, "getvalue"):
            dest.write_bytes(data.getvalue())
        else:
            # Fallback: write directly if already bytes
            dest.write_bytes(data if isinstance(data, bytes) else b"")
        saved_paths.append(str(dest))

    return saved_paths


def _call_chat_api(
    application_id: str, text: str, file_paths: list[str]
) -> dict[str, Any]:
    """POST to the chat endpoint and return the parsed response."""
    url = f"{API_BASE}/api/v1/applications/{application_id}/chat"

    form_data = {"text": text}
    opened_files = []
    for path in file_paths:
        fh = open(path, "rb")
        opened_files.append(("files", (Path(path).name, fh, "application/octet-stream")))

    try:
        resp = requests.post(url, data=form_data, files=opened_files, timeout=60)
        resp.raise_for_status()
        return resp.json()
    finally:
        for _, (_, fh, _) in opened_files:
            fh.close()


def _classify_error(error: Exception) -> tuple[str, str, str]:
    """Classify an error and return (title, message, action_label)."""
    if isinstance(error, requests.exceptions.ConnectionError):
        return (
            "Connection lost",
            "We couldn't reach the server. Your progress is saved.",
            "Retry",
        )
    elif isinstance(error, requests.exceptions.Timeout):
        return (
            "Request timed out",
            "This is taking longer than expected. Your documents may still be processing.",
            "Check Status",
        )
    elif isinstance(error, requests.exceptions.HTTPError):
        status = getattr(error.response, 'status_code', 'unknown') if hasattr(error, 'response') else 'unknown'
        if isinstance(status, int) and status >= 500:
            return (
                "Something went wrong",
                "This is on our end. Please try again in a moment.",
                "Retry",
            )
        else:
            return (
                "Issue with your request",
                f"Server returned status {status}.",
                "Retry",
            )
    else:
        return (
            "Unexpected error",
            "An unexpected error occurred. Please try again.",
            "Retry",
        )


def _get_spinner_message(phase: str) -> str:
    """Return a phase-specific spinner message."""
    messages = {
        "processing": "Extracting data from your documents and validating consistency...",
        "decision": "Computing eligibility score and finalizing decision...",
    }
    return messages.get(phase, "Processing your request...")


def _append_user_message(text: str, files: list[dict[str, Any]] | None) -> None:
    """Append a user message to session history."""
    entry: dict[str, Any] = {"role": "user", "content": text}
    if files:
        entry["files"] = []
        for f in files:
            file_entry: dict[str, Any] = {"name": f["name"], "size": f["size"]}
            # Store raw bytes for image thumbnail rendering
            data = f["data"]
            if hasattr(data, "getvalue"):
                file_entry["data"] = data.getvalue()
            elif isinstance(data, bytes):
                file_entry["data"] = data
            entry["files"].append(file_entry)
    st.session_state.messages.append(entry)


def _append_assistant_message(response: dict[str, Any]) -> None:
    """Append an assistant message from the API response."""
    entry: dict[str, Any] = {
        "role": "assistant",
        "content": response.get("message", "I received your message."),
    }
    if response.get("decision_card"):
        entry["decision_card"] = response["decision_card"]
    elif response.get("decision"):
        entry["decision"] = response["decision"]
    if response.get("enablement_recommendations"):
        entry["enablement_recommendations"] = response["enablement_recommendations"]
    if response.get("discrepancies"):
        entry["discrepancies"] = response["discrepancies"]
    st.session_state.messages.append(entry)


def _handle_submission(result: ChatInputResult, skip_user_message: bool = False) -> None:
    """Process a chat input: save files, call API, update state.

    Args:
        result: The chat input result containing text and files.
        skip_user_message: If True, don't append the user message to history.
            Used for retry paths where the message was already appended.
    """
    application_id = st.session_state.get("application_id")
    if not application_id:
        st.error("No active application found. Please log in again.")
        return

    logger.info(
        "user_message_submitted",
        phase=st.session_state.get("current_phase", "intake"),
        has_files=bool(result.files),
        file_count=len(result.files) if result.files else 0,
    )

    if not skip_user_message:
        _append_user_message(result.text, result.files)

    file_paths: list[str] = []
    if result.files:
        try:
            file_paths = _save_files(application_id, result.files)
        except OSError:
            st.error("Failed to save uploaded files. Please try again.")
            st.rerun()
            return

    previous_phase = st.session_state.get("current_phase", "intake")

    # Store last request for retry
    st.session_state.last_request = {
        "message": result.text,
        "files": result.files,
    }

    try:
        with st.spinner(_get_spinner_message(previous_phase)):
            response = _call_chat_api(application_id, result.text, file_paths)
    except Exception as error:
        title, message, action_label = _classify_error(error)
        logger.exception("chat_api_error", error_type=type(error).__name__)

        st.error(f"**{title}** — {message}")

        retry_count = st.session_state.get("last_retry_count", 0)
        if retry_count >= 3:
            st.error(
                "**Maximum retries reached.** "
                f"Please contact support with your application ID: {application_id}"
            )
            if st.button("Return to Login"):
                st.session_state.current_phase = "authentication"
                st.rerun()
        else:
            if st.button(action_label, key=f"retry_{retry_count}"):
                st.session_state.last_retry_count = retry_count + 1
                # Re-submit the last request without re-appending the user message
                last_request = st.session_state.get("last_request", {})
                if last_request:
                    # Create a synthetic ChatInputResult for retry
                    retry_result = ChatInputResult(
                        text=last_request.get("message", ""),
                        files=last_request.get("files", []),
                    )
                    _handle_submission(retry_result, skip_user_message=True)
                st.rerun()
        return

    _append_assistant_message(response)

    # Reset retry count on success so transient errors don't permanently lock out retries
    st.session_state.last_retry_count = 0

    # Update phase if the backend returned one
    if response.get("phase"):
        st.session_state.current_phase = response["phase"]

    # Notify if phase changed
    new_phase = response.get("phase", previous_phase)
    if new_phase != previous_phase:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Phase updated to {new_phase}",
        })

    # Show document classification confirmations
    if response.get("uploaded_documents"):
        existing_docs = st.session_state.get("uploaded_documents", {})
        # Normalize API list response to dict keyed by doc_type
        st.session_state.uploaded_documents = {
            doc.get("doc_type", "unknown"): doc for doc in response["uploaded_documents"]
        }
        for doc in response["uploaded_documents"]:
            doc_type = doc.get("doc_type", "Document")
            file_path = doc.get("file_path", "")
            doc_name = Path(file_path).name if file_path else "Unknown"
            is_reupload = doc_type in existing_docs

            if is_reupload:
                confirmation = f"🔄 Updated: {doc_name} replaces previous {doc_type} upload"
            else:
                confirmation = f"✓ {doc_name} uploaded and classified as {doc_type}"

            st.session_state.messages.append({
                "role": "system",
                "content": confirmation,
            })

    logger.info(
        "agent_response_received",
        phase=response.get("phase", st.session_state.get("current_phase", "intake")),
        has_decision=bool(response.get("decision")),
    )

    st.rerun()


FILE_ICONS: dict[str, str] = {
    "pdf": "📄",
    "xlsx": "📊",
    "xls": "📊",
    "docx": "📝",
    "doc": "📝",
}


def _render_file_attachments(files: list[dict[str, Any]]) -> None:
    """Render uploaded file attachments with thumbnails and icons."""
    st.caption("Attachments:")
    for f in files:
        ext = Path(f["name"]).suffix.lstrip(".").lower()
        size_kb = round(f.get("size", 0) / 1024, 1)

        if ext in ("png", "jpg", "jpeg"):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(f["data"], width=100)
            with col2:
                st.caption(f"{f['name']} ({size_kb} KB)")
        else:
            icon = FILE_ICONS.get(ext, "📎")
            st.caption(f"{icon} {f['name']} ({size_kb} KB)")


@st.fragment
def render_chat_area() -> None:
    """Render the chat message history and input widget."""
    if not st.session_state.get("messages") and st.session_state.get("state_snapshot"):
        snapshot = st.session_state["state_snapshot"]
        if "messages" in snapshot:
            st.session_state.messages = snapshot["messages"]
            logger.info("messages_restored_from_snapshot", count=len(st.session_state.messages))

    messages = st.session_state.get("messages", [])

    for msg in messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and msg.get("decision_card"):
                render_decision_card(msg["decision_card"])
                if msg.get("enablement_recommendations"):
                    render_enablement_section(msg["enablement_recommendations"])
                if msg.get("discrepancies"):
                    render_discrepancy_cards(msg["discrepancies"])
                if msg.get("content"):
                    st.markdown(msg["content"])
            elif msg["role"] == "assistant" and msg.get("decision"):
                render_decision_card({"decision_type": msg["decision"]})
                if msg.get("enablement_recommendations"):
                    render_enablement_section(msg["enablement_recommendations"])
                if msg.get("discrepancies"):
                    render_discrepancy_cards(msg["discrepancies"])
                if msg.get("content"):
                    st.markdown(msg["content"])
            elif msg["role"] == "user" and msg.get("files"):
                st.markdown(msg["content"] if msg.get("content") else "Attachments:")
                _render_file_attachments(msg["files"])
            else:
                st.markdown(msg["content"])
                if msg.get("files"):
                    _render_file_attachments(msg["files"])

        # Render interrupt/clarification data after the message content
        if msg.get("interrupt"):
            interrupt = msg["interrupt"]
            st.info(f"**Question:** {interrupt.get('question', '')}")
            if interrupt.get("missing_fields"):
                st.warning("Missing fields: " + ", ".join(interrupt["missing_fields"]))
            if interrupt.get("missing_documents"):
                st.warning("Missing documents: " + ", ".join(interrupt["missing_documents"]))
            if interrupt.get("discrepancies"):
                render_discrepancy_cards(interrupt["discrepancies"])

    result = render_chat_input()
    if result:
        _handle_submission(result)
