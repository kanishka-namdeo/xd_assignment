"""Conditional edge routing logic."""

from src.agents.state import ApplicantState


def route_by_phase(state: ApplicantState) -> str:
    """Route to the node matching the current phase."""
    return state.get("current_phase", "intake")
