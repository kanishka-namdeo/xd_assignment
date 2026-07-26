"""Sidebar phase progress indicator."""

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

PHASES: list[tuple[str, str]] = [
    ("authentication", "Authentication"),
    ("intake", "Intake"),
    ("document_collection", "Document Collection"),
    ("processing", "Processing"),
    ("review", "Review"),
    ("decision", "Decision"),
    ("enablement", "Enablement"),
]

PHASE_ORDER = {pid: i for i, (pid, _) in enumerate(PHASES)}


def render_phase_tracker(current_phase: str) -> None:
    """Render the phase progress indicator in the sidebar."""
    st.subheader("Progress")

    previous_phase = st.session_state.get("_previous_phase")
    if previous_phase != current_phase:
        logger.info(
            "phase_transition",
            from_phase=previous_phase,
            to_phase=current_phase,
        )
        st.session_state._previous_phase = current_phase

    current_idx = PHASE_ORDER.get(current_phase, 0)

    for i, (phase_id, label) in enumerate(PHASES):
        if i < current_idx:
            st.markdown(f"✅ {label}")
        elif i == current_idx:
            st.markdown(f"**➡ {label}**")
        else:
            st.markdown(f"⚪ {label}")

    st.markdown("---")


def get_current_phase_label(current_phase: str) -> str:
    """Return the human-readable label for the current phase."""
    return next(
        (lbl for pid, lbl in PHASES if pid == current_phase),
        current_phase.capitalize(),
    )


def render_phase_summary(current_phase: str) -> None:
    """Render a compact phase summary line for the top of the chat page."""
    label = next(
        (lbl for pid, lbl in PHASES if pid == current_phase),
        current_phase.capitalize(),
    )
    st.caption(f"Phase: **{label}**")
