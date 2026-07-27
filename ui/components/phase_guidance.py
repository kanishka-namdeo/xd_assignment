"""Per-phase guidance panel for applicant clarity."""

import structlog
import streamlit as st

logger = structlog.get_logger(__name__)

PHASE_GUIDANCE = {
    "authentication": {
        "where": "Enter your Emirates ID to start or resume your application",
        "expect": [
            "Your ID is validated instantly using the Luhn algorithm",
            "Returning applicants can continue where they left off",
        ],
        "need": "Your 15-digit Emirates ID number (format: 784-YYYY-NNNNNNN-C)",
    },
    "intake": {
        "where": "Provide your personal information",
        "expect": [
            "We'll ask about your family, employment, and living situation",
            "Answer at your own pace — you can take your time",
        ],
        "need": "Your personal details (name, date of birth, nationality, contact, address, marital status)",
    },
    "document_collection": {
        "where": "Upload your supporting documents",
        "expect": [
            "Upload clear photos or PDFs of your documents",
            "We'll confirm each file as it's received and classified",
            "You can replace documents if needed",
        ],
        "need": "Emirates ID, bank statement, credit report, and other supporting documents",
    },
    "processing": {
        "where": "We're reviewing your application",
        "expect": [
            "Our system extracts and validates information from your documents",
            "This may take a few minutes — please be patient",
        ],
        "need": "No action needed — please wait for processing to complete",
    },
    "review": {
        "where": "Check and clarify any discrepancies",
        "expect": [
            "If we found differences between your documents, we'll show them here",
            "You can clarify or re-upload documents to resolve discrepancies",
        ],
        "need": "Review the discrepancies shown and respond to clarification questions",
    },
    "decision": {
        "where": "Your application decision",
        "expect": [
            "You'll receive a decision card explaining the outcome",
            "The card includes next steps specific to your result",
        ],
        "need": "Review your decision carefully and note the next steps",
    },
    "enablement": {
        "where": "Personalized recommendations",
        "expect": [
            "Based on your profile, we'll suggest programs that can help you",
            "Recommendations are tailored to your situation and goals",
        ],
        "need": "Explore the recommendations and note any programs of interest",
    },
}


def _get_guidance_state_key(phase: str) -> str:
    return f"phase_guidance_dismissed_{phase}"


def render_phase_guidance() -> None:
    """Render the per-phase guidance panel with auto-expand on first visit."""
    phase = st.session_state.get("current_phase", "authentication")
    guidance = PHASE_GUIDANCE.get(phase)

    if not guidance:
        return

    state_key = _get_guidance_state_key(phase)
    has_interacted = st.session_state.get(state_key, False)

    # Auto-expand on first visit to this phase
    expanded = not has_interacted

    with st.expander(
        f"📋 Guidance: {phase.replace('_', ' ').title()}",
        expanded=expanded,
    ):
        st.markdown(f"**Where you are:** {guidance['where']}")
        st.markdown("**What to expect:**")
        for item in guidance["expect"]:
            st.markdown(f"- {item}")
        st.markdown(f"**What you need:** {guidance['need']}")

        # Mark as interacted when user sees guidance
        if not has_interacted:
            st.session_state[state_key] = True

    logger.debug("phase_guidance_rendered", phase=phase, first_visit=not has_interacted)
