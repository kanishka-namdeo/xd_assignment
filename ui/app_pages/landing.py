"""Phase 0: Emirates ID login and application creation."""

import re

import requests
import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

API_BASE = "http://localhost:8000"
MAX_ATTEMPTS = 3

EMIRATES_ID_PATTERN = re.compile(r"^\d{3}-?\d{4}-?\d{7}-?\d$")


def _luhn_check(digits: str) -> bool:
    """Validate Luhn checksum for 14 or 15-digit Emirates ID number."""
    if len(digits) not in (14, 15) or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _normalize_emirates_id(value: str) -> str | None:
    """Strip formatting and return 14 or 15-digit string, or None if malformed."""
    cleaned = value.replace("-", "").replace(" ", "")
    if len(cleaned) in (14, 15) and cleaned.isdigit():
        return cleaned
    return None


def _format_emirates_id(digits: str) -> str:
    """Format a 14 or 15-digit string as 784-YYYY-NNNNNNN-C or 784-YYYY-NNNNNNNN-C."""
    if len(digits) == 14:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:13]}-{digits[13]}"
    elif len(digits) == 15:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14]}"
    return digits


def validate_emirates_id(value: str) -> str | None:
    """Return an error message string on failure, or None on success."""
    if not value:
        return "Please enter your Emirates ID number."
    digits = _normalize_emirates_id(value)
    if digits is None:
        return "Emirates ID must be 14 digits (format: 784-YYYY-NNNNNNN-C)."
    if not _luhn_check(digits):
        return "Invalid Emirates ID checksum. Please check the number and try again."
    return None


def handle_login() -> None:
    """Submit Emirates ID to auth endpoint and transition to chat on success."""
    raw = st.session_state.get("emirates_id_input", "").strip()
    error = validate_emirates_id(raw)
    if error:
        st.session_state.login_error = error
        logger.warning("login_validation_failed", reason="invalid_format")
        return

    digits = _normalize_emirates_id(raw)
    formatted_id = _format_emirates_id(digits)
    attempts = st.session_state.get("login_attempts", 0) + 1
    st.session_state.login_attempts = attempts

    logger.info("login_attempt", attempt=attempts, max_attempts=MAX_ATTEMPTS)

    try:
        resp = requests.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"emirates_id": formatted_id},
            timeout=10,
        )
    except requests.ConnectionError:
        st.session_state.login_error = "Cannot connect to the server. Please try again later."
        logger.error("login_connection_failed")
        return
    except requests.Timeout:
        st.session_state.login_error = "Request timed out. Please try again."
        logger.error("login_timeout")
        return

    if resp.status_code == 200:
        data = resp.json()
        st.session_state.authenticated = True
        st.session_state.applicant_id = data["applicant_id"]
        st.session_state.application_id = data["application_id"]
        st.session_state.current_phase = data.get("current_phase", "intake")
        st.session_state.uploaded_documents = []
        st.session_state.login_attempts = 0
        st.session_state.login_error = None
        st.session_state.login_success = True

        state_snapshot = data.get("state_snapshot")
        if state_snapshot and not data.get("is_new_applicant"):
            st.session_state.state_snapshot = state_snapshot
            if "messages" in state_snapshot:
                st.session_state.messages = state_snapshot["messages"]
            logger.info(
                "login_resumed",
                applicant_id=data["applicant_id"],
                application_id=data["application_id"],
                phase=data.get("current_phase", "intake"),
                message_count=len(st.session_state.messages),
            )
        else:
            st.session_state.state_snapshot = None
            st.session_state.messages = []
            logger.info(
                "login_success",
                applicant_id=data["applicant_id"],
                application_id=data["application_id"],
                phase=data.get("current_phase", "intake"),
            )
    else:
        detail = "Login failed. Please check your Emirates ID."
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        st.session_state.login_error = detail
        logger.warning("login_failed", status_code=resp.status_code, attempt=attempts)

        if attempts >= MAX_ATTEMPTS:
            st.session_state.login_error = (
                "Maximum login attempts reached. Please contact support for assistance."
            )
            st.session_state.login_locked = True
            logger.warning("login_locked", attempt=attempts)


def render() -> None:
    """Render the landing page."""
    logger.debug("landing_page_render")

    # Handle navigation after successful login (set by handle_login callback)
    if st.session_state.get("login_success"):
        st.session_state.login_success = False
        st.switch_page(st.session_state.pages["application"])
        return

    if st.session_state.get("authenticated"):
        st.switch_page(st.session_state.pages["application"])
        return

    st.set_page_config(page_title="Social Support Application", layout="centered")

    st.title("Social Support Application Portal")
    st.markdown(
        "Enter your Emirates ID to start or continue your application. "
        "If this is your first time, a new application will be created automatically."
    )

    if st.session_state.get("login_locked"):
        st.error(
            "Maximum attempts exceeded. Please contact support to continue your application."
        )
        return

    error = st.session_state.get("login_error")
    if error:
        st.error(error)

    attempts = st.session_state.get("login_attempts", 0)
    if attempts > 0:
        st.caption(f"Attempt {attempts} of {MAX_ATTEMPTS}")

    st.text_input(
        label="Emirates ID Number",
        key="emirates_id_input",
        placeholder="784-YYYY-NNNNNNN-C",
        label_visibility="collapsed",
        disabled=st.session_state.get("login_locked", False),
        on_change=lambda: st.session_state.pop("login_error", None),
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        st.button(
            "Continue",
            on_click=handle_login,
            disabled=st.session_state.get("login_locked", False),
            type="primary",
        )

    st.markdown("---")
    st.caption(
        "Your data is processed securely. No account creation is required — "
        "your Emirates ID is your identifier."
    )
