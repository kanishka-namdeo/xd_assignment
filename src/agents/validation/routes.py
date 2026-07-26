"""Validation routing logic."""

from __future__ import annotations

from src.agents.state import ApplicantState


def route_after_critique(state: ApplicantState) -> str:
    """Route based on critique node's decision.

    Returns:
        "generate_clarification" if clarification questions needed
        "finalize_validation" if validation complete
        "end" if escalating to manual review
    """
    next_action = state.get("_next_action", "proceed")

    if next_action == "request_clarification":
        return "generate_clarification"
    elif next_action == "escalate":
        return "end"
    else:
        return "finalize_validation"
