"""Phase 5: Decision - invoke eligibility and decision agents."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from src.agents.orchestrator.di import _make_assistant_message, get_services
from src.utils.circuit_breaker import CircuitBreaker
from src.utils.retry import retry_transient

if TYPE_CHECKING:
    from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)

# Circuit breakers for subgraph invocations
_eligibility_circuit = CircuitBreaker(
    failure_threshold=3, recovery_timeout=300, name="eligibility_subgraph"
)
_decision_circuit = CircuitBreaker(
    failure_threshold=3, recovery_timeout=300, name="decision_subgraph"
)


async def _eligibility_fallback(state: dict[str, Any]) -> dict[str, Any]:
    """Fallback when eligibility circuit is open."""
    logger.warning(
        "eligibility_circuit_open_using_fallback",
        application_id=state.get("application_id"),
    )
    return {
        "eligibility_score": 0.5,
        "eligibility_factors": {"error": "Eligibility service temporarily unavailable"},
        "gate_status": "passed",
    }


async def _decision_fallback(state: dict[str, Any]) -> dict[str, Any]:
    """Fallback when decision circuit is open."""
    logger.warning(
        "decision_circuit_open_using_fallback",
        application_id=state.get("application_id"),
    )
    return {
        "decision": "manual_review",
        "decision_explanation": "Decision service temporarily unavailable - requires manual review",
    }


@_eligibility_circuit(fallback=_eligibility_fallback)
@retry_transient(max_retries=3, base_delay=1.0)
async def _invoke_eligibility_subgraph(graph: Any, state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Invoke eligibility subgraph with retry and circuit breaker logic."""
    return await graph.ainvoke(state, config=config)


@_decision_circuit(fallback=_decision_fallback)
@retry_transient(max_retries=3, base_delay=1.0)
async def _invoke_decision_subgraph(agent: Any, state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Invoke decision agent with retry and circuit breaker logic."""
    return await agent.ainvoke(state, config=config)


async def decision_node(state: "ApplicantState") -> "ApplicantState":
    """Phase 5: Decision - invoke eligibility and decision agents."""

    start_ms = time.perf_counter()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    logger.info("node_enter", node="decision", application_id=application_id, applicant_id=applicant_id)

    decision = "manual_review"
    decision_explanation = "Unable to compute eligibility - agent invocation failed."
    eligibility_score = 0.5
    eligibility_factors: dict = {}

    # Invoke eligibility agent subgraph
    try:
        from src.agents.eligibility.graph import get_eligibility_graph

        eligibility_graph = get_eligibility_graph()
        config = {"configurable": {"thread_id": f"{application_id}_eligibility", "recursion_limit": 10}}
        eligibility_result = await _invoke_eligibility_subgraph(eligibility_graph, state, config)
        eligibility_score = eligibility_result.get("eligibility_score", 0.5)
        eligibility_factors = eligibility_result.get("eligibility_factors", {})
        logger.info("eligibility_agent_complete", score=eligibility_score, gate_status=eligibility_result.get("gate_status"))

        if eligibility_result.get("gate_status") == "failed":
            logger.warning("eligibility_gate_failed", gate_errors=eligibility_result.get("gate_errors"))
            # Gate 3 failed, but we still proceed to decision agent if we have a score.
            # The decision agent will use the eligibility score for its deterministic logic.
            # Only hard-decline if score is very low (< 0.40).
            if eligibility_score < 0.40:
                decision = "soft_decline"
                decision_explanation = "Application does not meet hard eligibility requirements."
                return {
                    "messages": [_make_assistant_message(f"We have reached a decision on your application. Decision: {decision.replace('_', ' ').title()}. {decision_explanation}")],
                    "current_phase": "enablement", "decision": decision, "decision_explanation": decision_explanation,
                    "eligibility_score": eligibility_score, "eligibility_factors": eligibility_factors,
                    "gate_status": "failed", "gate_errors": eligibility_result.get("gate_errors", []),
                }
            logger.info("gate_failed_but_score_sufficient", score=eligibility_score)
    except Exception as e:
        logger.exception("eligibility_agent_failed", error=str(e))
        services = get_services()
        eligibility_service = services.get("eligibility")
        if eligibility_service and application_id:
            try:
                eligibility_result = await eligibility_service.compute_eligibility(application_id)
                eligibility_score = eligibility_result.get("eligibility_score", 0.5)
                eligibility_factors = eligibility_result.get("factors", {})
                logger.info("eligibility_service_fallback", score=eligibility_score)
            except Exception as e2:
                logger.exception("eligibility_service_fallback_failed", error=str(e2))

    # Invoke decision agent subgraph
    try:
        from src.agents.decision.graph import get_decision_agent

        decision_agent = get_decision_agent()

        decision_state = {**state, "eligibility_score": eligibility_score, "eligibility_factors": eligibility_factors}
        config = {"configurable": {"thread_id": f"{application_id}_decision", "recursion_limit": 10}}
        decision_result = await _invoke_decision_subgraph(decision_agent, decision_state, config)
        decision = decision_result.get("decision", "manual_review")
        decision_explanation = decision_result.get("decision_explanation", decision_explanation)
        logger.info("decision_agent_complete", decision=decision)
    except Exception as e:
        logger.exception("decision_agent_failed", error=str(e))
        services = get_services()
        decision_service = services.get("decision")
        if decision_service and application_id:
            try:
                decision_result = await decision_service.make_decision(application_id)
                decision = decision_result.get("decision", "manual_review")
                decision_explanation = decision_result.get("explanation", decision_explanation)
                logger.info("decision_service_fallback", decision=decision)
            except Exception as e2:
                logger.exception("decision_service_fallback_failed", error=str(e2))
        elif eligibility_score >= 0.7:
            decision = "approved"
            decision_explanation = f"Application approved with eligibility score {eligibility_score:.0%}."
        elif eligibility_score >= 0.5:
            decision = "manual_review"
            decision_explanation = f"Application requires manual review. Score: {eligibility_score:.0%}."
        else:
            decision = "soft_decline"
            decision_explanation = f"Application declined with eligibility score {eligibility_score:.0%}."

    duration_ms = (time.perf_counter() - start_ms) * 1000
    validation_confidence = state.get("validation_confidence")
    if validation_confidence is None:
        validation_confidence = state.get("validation_results", {}).get("overall_confidence")
    if validation_confidence is None:
        validation_confidence = 0.0
    logger.info(
        "node_exit",
        node="decision",
        duration_ms=round(duration_ms, 2),
        decision=decision,
        eligibility_score=eligibility_score,
        validation_confidence=validation_confidence,
    )

    return {
        "messages": [_make_assistant_message(f"We have reached a decision on your application. Decision: {decision.replace('_', ' ').title()}. {decision_explanation}")],
        "current_phase": "enablement",
        "decision": decision,
        "decision_explanation": decision_explanation,
        "eligibility_score": eligibility_score,
        "eligibility_factors": eligibility_factors,
        "validation_confidence": validation_confidence,
    }
