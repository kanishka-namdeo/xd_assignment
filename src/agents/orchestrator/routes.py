"""Conditional edge routing logic."""

import structlog
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


def route_by_phase(state: ApplicantState) -> str:
    """Route to the node matching the current phase."""
    phase = state.get("current_phase", "authentication")
    logger.info("routing_decision", event="routing_decision", phase=phase, applicant_id=state.get("applicant_id"), application_id=state.get("application_id"))
    return phase
