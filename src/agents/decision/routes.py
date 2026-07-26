"""Decision routing logic."""

from src.agents.state import ApplicantState


def should_use_react(state: ApplicantState) -> str:
    """Determine whether to use ReAct agent or deterministic synthesis.

    Use ReAct when:
    - Eligibility score is available
    - Validation results are present
    - System is configured for LLM-based decisions

    Otherwise, fall back to deterministic synthesis.
    """
    eligibility_score = state.get("eligibility_score")
    validation_results = state.get("validation_results")

    if eligibility_score is not None and validation_results:
        return "react"
    return "deterministic"
