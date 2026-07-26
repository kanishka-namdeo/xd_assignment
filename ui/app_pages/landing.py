"""Phase 0: Emirates ID login and application creation."""

import re

import requests
import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

API_BASE = "http://localhost:8000"
MAX_ATTEMPTS = 3

EMIRATES_ID_PATTERN = re.compile(r"^\d{3}-?\d{4}-?\d{7}-?\d$")

PHASE_LABELS = {
    "auth": "Authentication",
    "intake": "Intake",
    "document_collection": "Document Collection",
    "processing": "Processing",
    "review": "Review",
    "decision": "Decision",
    "enablement": "Enablement",
}


def _get_phase_welcome_message(phase: str) -> str:
    """Generate a phase-appropriate welcome message for new or returning users."""
    messages = {
        "intake": "Welcome to the Social Support Application! I'm here to guide you through the process.\n\nTo get started, please tell me:\n\n1. **What type of support are you applying for?** (e.g., financial assistance, housing support, family support)\n2. **Your current marital status**\n3. **Your employment status**\n\nYou can type your answers below, or if you prefer, you can upload documents first and I'll extract the information from them.",
        "document_collection": "Welcome back! You're at the document collection stage.\n\nPlease upload your supporting documents (Emirates ID, bank statements, credit report, application form, etc.). You can drag and drop files or click to browse.\n\nOnce you've uploaded everything, let me know and we'll continue.",
        "processing": "Welcome back! Your documents are being processed.\n\nI'm extracting information and validating your documents. This usually takes a few moments. I'll let you know when it's complete.",
        "review": "Welcome back! We've processed your documents and need your review.\n\nI'll show you the extracted information and ask you to confirm or correct any details. Please review carefully.",
        "decision": "Welcome back! Your application is ready for decision.\n\nBased on the information you've provided, I'll now compute your eligibility and provide a decision.",
        "enablement": "Welcome back! Your application has been processed.\n\nI'm here to help you understand your decision and explore next steps. What would you like to know?",
    }
    return messages.get(phase, messages["intake"])


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


def _auto_format_emirates_id() -> None:
    """on_change callback that formats the Emirates ID input as the user types."""
    raw = st.session_state.get("emirates_id_input", "")
    if not raw:
        return
    digits = _normalize_emirates_id(raw)
    if digits:
        st.session_state.emirates_id_input = _format_emirates_id(digits)


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
        st.session_state.login_attempts = 0
        st.session_state.login_error = None
        st.session_state.login_success = True

        state_snapshot = data.get("state_snapshot")
        if state_snapshot and not data.get("is_new_applicant"):
            st.session_state.state_snapshot = state_snapshot
            if "messages" in state_snapshot and state_snapshot["messages"]:
                st.session_state.messages = state_snapshot["messages"]
            else:
                # Returning user with empty messages - add phase-appropriate welcome
                phase = data.get("current_phase", "intake")
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": _get_phase_welcome_message(phase),
                    }
                ]
            if "uploaded_documents" in state_snapshot:
                st.session_state.uploaded_documents = state_snapshot["uploaded_documents"]
            else:
                st.session_state.uploaded_documents = []
            logger.info(
                "login_resumed",
                applicant_id=data["applicant_id"],
                application_id=data["application_id"],
                phase=data.get("current_phase", "intake"),
                message_count=len(st.session_state.messages),
                document_count=len(st.session_state.uploaded_documents),
            )
        else:
            st.session_state.state_snapshot = None
            st.session_state.uploaded_documents = []
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": _get_phase_welcome_message("intake"),
                }
            ]
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


def _render_process_steps() -> None:
    """Render the 4-step visual process explainer."""
    steps = [
        ("784-", "Enter ID", "card"),
        ("YYYY-", "Provide Info", "form"),
        ("NNNNNNN-", "Upload Documents", "upload"),
        ("C", "Get Decision", "check"),
    ]

    st.markdown(
        "<div style='text-align:center;margin-bottom:8px;color:#555;font-size:14px;font-weight:500;'>How it works</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    icons = {"card": "💳", "form": "📝", "upload": "📤", "check": "✅"}
    labels = {
        "card": "Enter ID",
        "form": "Provide Info",
        "upload": "Upload Documents",
        "check": "Get Decision",
    }

    for i, (prefix, key, icon_key) in enumerate(steps):
        with cols[i]:
            st.markdown(
                f"""
                <div class="step-card">
                    <div class="step-number">{i + 1}</div>
                    <div class="step-icon">{icons[icon_key]}</div>
                    <div class="step-label">{labels[icon_key]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_welcome_back_banner() -> None:
    """Show a welcome back banner if a previous session snapshot exists."""
    state_snapshot = st.session_state.get("state_snapshot")
    application_id = st.session_state.get("application_id")

    if not state_snapshot and not application_id:
        return

    phase = st.session_state.get("current_phase", "intake")
    phase_label = PHASE_LABELS.get(phase, phase)
    doc_count = len(st.session_state.get("uploaded_documents", []))

    st.markdown(
        f"""
        <div class="welcome-banner">
            <strong>Welcome back!</strong> Your application was in progress at <strong>Phase {phase_label}</strong>
            with {doc_count} document(s) uploaded. You can continue where you left off.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_returning_user_continue() -> None:
    """Show a prominent continue button for returning users with state snapshot."""
    state_snapshot = st.session_state.get("state_snapshot")
    if not state_snapshot:
        return

    phase = st.session_state.get("current_phase", "intake")
    phase_label = PHASE_LABELS.get(phase, phase)
    doc_count = len(st.session_state.get("uploaded_documents", []))
    identity_number = st.session_state.get("identity_number", "")

    st.markdown(
        f"""
        <div style='
            background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
            border: 2px solid #006633;
            border-radius: 12px;
            padding: 20px 24px;
            margin: 16px 0;
            text-align: center;
        '>
            <div style='font-size:18px;font-weight:600;color:#1b5e20;margin-bottom:8px;'>
                Welcome back! You were at Phase {phase_label}
            </div>
            <div style='color:#2e7d32;font-size:14px;margin-bottom:16px;'>
                {doc_count} document(s) uploaded · {len(state_snapshot.get("messages", []))} messages in history
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Continue Application", type="primary", use_container_width=True, key="continue_returning"):
        if identity_number:
            st.session_state.emirates_id_input = _format_emirates_id(identity_number)
        handle_login()


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

    # Welcome back banner
    _render_welcome_back_banner()

    st.title("Social Support Application Portal")
    st.markdown(
        "Enter your Emirates ID to start or continue your application. "
        "If this is your first time, a new application will be created automatically."
    )

    # 4-step process explainer
    _render_process_steps()

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

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

    # Returning user continue banner
    _render_returning_user_continue()

    with st.form("login_form"):
        emirates_id_value = st.text_input(
            label="Emirates ID Number",
            placeholder="784-YYYY-NNNNNNN-C",
            label_visibility="collapsed",
            disabled=st.session_state.get("login_locked", False),
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            submitted = st.form_submit_button(
                "Continue",
                disabled=st.session_state.get("login_locked", False),
                type="primary",
            )

        if submitted:
            st.session_state.emirates_id_input = emirates_id_value
            _auto_format_emirates_id()
            handle_login()

    st.markdown("---")

    # "How it works" expandable section
    with st.expander("How it works — 7-phase process"):
        st.markdown(
            """
            **Phase 0 — Authentication:** Enter your Emirates ID to identify yourself and start or resume your application.

            **Phase 1 — Intake:** Provide your personal information including marital status, employment, dependents, and monthly income.

            **Phase 2 — Document Collection:** Upload supporting documents such as Emirates ID, bank statements, credit report, and application form.

            **Phase 3 — Processing:** Our system extracts data from your documents, validates them, and checks for consistency across all uploads.

            **Phase 4 — Review:** You review the extracted information and confirm or correct any details before the final decision.

            **Phase 5 — Decision:** An eligibility score is computed and a decision is made: Approved, Manual Review, or Not Approved.

            **Phase 6 — Enablement:** If approved, you receive details about your support package and recommended programs.
            """
        )

    st.caption(
        "Your data is processed securely. No account creation is required — "
        "your Emirates ID is your identifier."
    )
