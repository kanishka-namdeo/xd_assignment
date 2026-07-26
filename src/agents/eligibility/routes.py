"""Eligibility routing logic."""

from __future__ import annotations


def route_after_eligibility_gate(state: dict) -> str:
    """Route based on Gate 3 result.

    Returns 'finalize' if gate passed, 'end' if gate failed.
    """
    gate_status = state.get("gate_status", "unknown")
    if gate_status == "passed":
        return "finalize"
    return "end"
