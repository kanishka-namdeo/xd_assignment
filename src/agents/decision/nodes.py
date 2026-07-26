"""Decision node functions with ReAct reasoning loop."""

import json
import re
import time
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, ValidationError

from src.agents.decision.prompts import DECISION_SYSTEM_PROMPT
from src.agents.decision.tools import (
    decision_explanation_tool,
    decision_formatting_tool,
    decision_logic_tool,
    enablement_recommendation_tool,
)
from src.agents.state import ApplicantState
from src.config import settings
from src.services.decision_service import DecisionService

logger = structlog.get_logger(__name__)


def _get_llm():
    """Get LangChain ChatModel for ReAct agent."""
    try:
        from langchain_openai import ChatOpenAI

        if settings.LLM_PROVIDER == "streamlake":
            return ChatOpenAI(
                model=settings.STREAMLAKE_MODEL,
                base_url=settings.STREAMLAKE_BASE_URL,
                api_key=settings.STREAMLAKE_API_KEY.get_secret_value(),
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        else:
            return ChatOpenAI(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                api_key=settings.OLLAMA_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
    except ImportError:
        logger.error("langchain_openai_not_installed")
        raise


def _build_applicant_context(state: ApplicantState) -> dict[str, Any]:
    """Build applicant context from state for decision reasoning."""
    return {
        "applicant_id": state.get("applicant_id"),
        "application_id": state.get("application_id"),
        "support_category": state.get("support_category"),
        "identity_number": state.get("identity_number"),
        "eligibility_score": state.get("eligibility_score"),
        "eligibility_factors": state.get("eligibility_factors"),
        "validation_confidence": state.get("validation_results", {}).get("overall_confidence", 0.0),
        "discrepancies": state.get("discrepancies", []),
        "family_size": state.get("extracted_data", {}).get("family_size", 1),
        "employment_status": state.get("extracted_data", {}).get("employment_status", "unknown"),
        "has_dependents": state.get("extracted_data", {}).get("has_dependents", False),
        "credit_score": state.get("extracted_data", {}).get("credit_score", 0),
    }


async def decision_react_node(state: ApplicantState) -> dict[str, Any]:
    """ReAct agent node for decision making.

    Uses LangGraph's create_react_agent with 4 decision tools:
    - decision_logic_tool: Apply decision rules
    - decision_explanation_tool: Generate human-readable explanation
    - enablement_recommendation_tool: Generate personalized recommendations
    - decision_formatting_tool: Format for UI display
    """
    start = time.perf_counter()

    logger.info(
        "decision_react_node_enter",
        application_id=state.get("application_id"),
        eligibility_score=state.get("eligibility_score"),
    )

    try:
        llm = _get_llm()
        tools = [
            decision_logic_tool,
            decision_explanation_tool,
            enablement_recommendation_tool,
            decision_formatting_tool,
        ]

        agent = create_react_agent(llm, tools)

        applicant_context = _build_applicant_context(state)

        messages = [
            SystemMessage(content=DECISION_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Make a decision for application {state.get('application_id')}. "
                    f"Applicant context: {json.dumps(applicant_context, default=str)}"
                )
            ),
        ]

        result = await agent.ainvoke({"messages": messages})

        final_message = result["messages"][-1].content if result["messages"] else ""

        try:
            decision_data = json.loads(final_message)
        except json.JSONDecodeError:
            decision_data = {
                "decision": "manual_review",
                "explanation": final_message,
                "raw_agent_output": True,
            }

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "decision_react_node_complete",
            application_id=state.get("application_id"),
            decision=decision_data.get("decision"),
            duration_ms=round(duration_ms, 2),
        )

        return {
            "decision": decision_data.get("decision"),
            "decision_explanation": decision_data.get("explanation"),
            "messages": result["messages"],
        }

    except Exception as e:
        logger.exception(
            "decision_react_node_failed",
            application_id=state.get("application_id"),
            error=str(e),
        )
        return await _fallback_decision(state)


async def _fallback_decision(state: ApplicantState) -> dict[str, Any]:
    """Fallback to DecisionService when ReAct agent fails."""
    logger.warning(
        "decision_fallback_triggered",
        application_id=state.get("application_id"),
    )

    try:
        from src.infrastructure.db.session import get_session

        async for session in get_session():
            decision_service = DecisionService(session)
            result = await decision_service.make_decision(state.get("application_id"))

            return {
                "decision": result.get("decision"),
                "decision_explanation": result.get("explanation"),
            }
    except Exception as fallback_error:
        logger.exception(
            "decision_fallback_failed",
            application_id=state.get("application_id"),
            error=str(fallback_error),
        )
        return {
            "decision": "manual_review",
            "decision_explanation": "Decision could not be computed automatically. Escalated to manual review.",
        }


async def synthesize_decision_node(state: ApplicantState) -> dict[str, Any]:
    """Synthesize decision from eligibility score, validation results, and context.

    This node applies the decision rules directly without LLM reasoning.
    Used as a deterministic fallback or when LLM is unavailable.
    """
    start = time.perf_counter()

    logger.info(
        "synthesize_decision_node_enter",
        application_id=state.get("application_id"),
    )

    eligibility_score = state.get("eligibility_score") or 0.0
    validation_results = state.get("validation_results", {})
    validation_confidence = validation_results.get("overall_confidence", 0.0)
    discrepancies = state.get("discrepancies", [])
    support_category = state.get("support_category", "general")

    critical_discrepancies = [
        d
        for d in discrepancies
        if d.get("discrepancy_type") in ["identity_match", "income_consistency"]
        and d.get("resolution_status") == "unresolved"
    ]

    if validation_confidence < 0.80 or len(critical_discrepancies) > 0:
        decision = "manual_review"
        explanation = (
            f"Validation confidence {validation_confidence:.2f} < 0.80 or "
            f"{len(critical_discrepancies)} unresolved critical discrepancies."
        )
    elif eligibility_score > 0.60:
        decision = "approved"
        explanation = (
            f"Eligibility score {eligibility_score:.2f} > 0.60, "
            f"confidence {validation_confidence:.2f} >= 0.80, "
            f"no critical discrepancies."
        )
    elif eligibility_score < 0.40:
        decision = "soft_decline"
        explanation = f"Eligibility score {eligibility_score:.2f} < 0.40."
    else:
        decision = "manual_review"
        explanation = f"Borderline eligibility score {eligibility_score:.2f} (0.40-0.60)."

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "synthesize_decision_node_complete",
        application_id=state.get("application_id"),
        decision=decision,
        eligibility_score=eligibility_score,
        validation_confidence=validation_confidence,
        duration_ms=round(duration_ms, 2),
    )

    return {
        "decision": decision,
        "decision_explanation": explanation,
    }
