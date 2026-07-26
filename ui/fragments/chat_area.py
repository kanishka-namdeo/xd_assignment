"""@st.fragment wrapped chat area for the application flow."""

import tempfile
from pathlib import Path
from typing import Any

import requests
import streamlit as st
import structlog

from ui.components.chat_input import ChatInputResult, render_chat_input
from ui.components.decision_card import render_decision_card

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
    files = []
    for path in file_paths:
        files.append(("files", (Path(path).name, open(path, "rb"), "application/octet-stream")))

    resp = requests.post(url, data=form_data, files=files, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _append_user_message(text: str, files: list[dict[str, Any]] | None) -> None:
    """Append a user message to session history."""
    entry: dict[str, Any] = {"role": "user", "content": text}
    if files:
        entry["files"] = [
            {"name": f["name"], "size": f["size"]} for f in files
        ]
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
    st.session_state.messages.append(entry)


def _handle_submission(result: ChatInputResult) -> None:
    """Process a chat input: save files, call API, update state."""
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

    _append_user_message(result.text, result.files)

    file_paths: list[str] = []
    if result.files:
        try:
            file_paths = _save_files(application_id, result.files)
        except OSError:
            st.error("Failed to save uploaded files. Please try again.")
            st.rerun()
            return

    try:
        response = _call_chat_api(application_id, result.text, file_paths)
    except requests.ConnectionError:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Cannot connect to the server. Please try again later.",
        })
        st.rerun()
        return
    except requests.Timeout:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Request timed out. Please try again.",
        })
        st.rerun()
        return
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response else "unknown"
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"⚠️ Server error ({status}). Please try again.",
        })
        st.rerun()
        return
    except Exception:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ An unexpected error occurred. Please try again.",
        })
        st.rerun()
        return

    _append_assistant_message(response)

    # Update phase if the backend returned one
    if response.get("phase"):
        st.session_state.current_phase = response["phase"]

    # Update uploaded documents list if returned
    if response.get("uploaded_documents"):
        st.session_state.uploaded_documents = response["uploaded_documents"]

    logger.info(
        "agent_response_received",
        phase=response.get("phase", st.session_state.get("current_phase", "intake")),
        has_decision=bool(response.get("decision")),
    )

    st.rerun()


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
                if msg.get("content"):
                    st.markdown(msg["content"])
            elif msg["role"] == "assistant" and msg.get("decision"):
                render_decision_card({"decision_type": msg["decision"]})
                if msg.get("content"):
                    st.markdown(msg["content"])
            else:
                st.markdown(msg["content"])
                if msg.get("files"):
                    for f in msg["files"]:
                        size_kb = round(f.get("size", 0) / 1024, 1)
                        st.caption(f"📎 {f['name']} ({size_kb} KB)")

    result = render_chat_input()
    if result:
        _handle_submission(result)
