"""Phase 6: Enablement - generate profile-matched enablement recommendations."""

from __future__ import annotations

import time

import structlog
from langgraph.types import interrupt

from src.agents.orchestrator.di import _generate_llm_response, _make_assistant_message
from src.agents.orchestrator.prompts import ENABLEMENT_SYSTEM_PROMPT
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


async def enablement_node(state: ApplicantState) -> ApplicantState:
    """Phase 6: Enablement - generate profile-matched enablement recommendations.

    Uses enablement_recommendation_tool to generate personalized recommendations
    based on employment status, skills, credit score, and decision outcome.
    Uses interrupt() to allow follow-up questions before transitioning to END.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", node="enablement", applicant_id=state.get("applicant_id"), decision=state.get("decision"))

    decision = state.get("decision", "manual_review")
    applicant_info = state.get("applicant_info", {})
    extracted_data = state.get("extracted_data", {})

    # Build applicant context from state for profile-matched recommendations
    family_size_raw = applicant_info.get("family_size", 1)
    try:
        family_size = int(family_size_raw)
    except (ValueError, TypeError):
        family_size = 1
    applicant_context = {
        "employment_status": applicant_info.get("employment_status", "unknown"),
        "has_dependents": family_size > 1,
        "credit_score": extracted_data.get("credit_report", {}).get("credit_score", 0),
        "skills": extracted_data.get("resume", {}).get("skills", []),
    }

    # Use enablement_recommendation_tool for dynamic, profile-matched recommendations
    try:
        from src.agents.decision.tools import enablement_recommendation_tool

        tool_result = enablement_recommendation_tool.invoke({
            "applicant_context": applicant_context,
            "eligibility_score": state.get("eligibility_score", 0.5),
            "decision": decision,
        })
        tool_recommendations = tool_result.get("recommendations", [])
        recommendations = [
            {"title": r.get("title", ""), "description": r.get("description", "")}
            for r in tool_recommendations
        ]
        logger.info(
            "enablement_recommendations_generated",
            recommendation_count=len(recommendations),
            decision=decision,
        )
    except Exception as e:
        logger.warning("enablement_tool_failed", error=str(e))
        # Fallback to basic recommendations
        if decision == "approved":
            recommendations = [
                {"title": "Benefit Processing", "description": "Your support benefits will be processed within 5-7 business days."},
                {"title": "Case Worker Assignment", "description": "A case worker will be assigned to your file."},
            ]
        elif decision == "manual_review":
            recommendations = [
                {"title": "Additional Review", "description": "Your application requires additional review by our team."},
                {"title": "Document Verification", "description": "Please ensure all your documents are complete and accurate."},
            ]
        else:
            recommendations = [
                {"title": "Eligibility Status", "description": "Your application does not currently meet the eligibility criteria."},
                {"title": "Reapplication", "description": "You may reapply if your circumstances change."},
            ]

    recommendation_text = " ".join(f"{r.get('title', '')}: {r.get('description', '')}" for r in recommendations)

    response = (
        f"Your application process is complete. "
        f"Decision: {decision.replace('_', ' ').title()}. "
        f"Next steps: {recommendation_text}"
    )

    system_prompt = ENABLEMENT_SYSTEM_PROMPT
    user_context = (
        f"Decision: {decision}\n"
        f"Support category: {applicant_info.get('support_category', 'unknown')}\n"
        f"Recommendations: {recommendation_text[:200]}"
    )
    llm_response = await _generate_llm_response(system_prompt, user_context, response)

    # Use interrupt() to allow follow-up questions
    user_response = interrupt({
        "question": llm_response,
        "phase": "enablement",
        "recommendations": recommendations,
    })

    # When resumed, check if user has follow-up questions
    if user_response and isinstance(user_response, str) and len(user_response.strip()) > 0:
        # User has a follow-up question - generate a personalized response using LLM
        support_category = applicant_info.get("support_category", "general")
        family_size_raw = applicant_info.get("family_size", 1)
        try:
            family_size = int(family_size_raw)
        except (ValueError, TypeError):
            family_size = 1
        housing_status = applicant_info.get("housing_status", "unknown")
        employment_status = applicant_info.get("employment_status", "unknown")

        follow_up_context = (
            f"Decision: {decision.replace('_', ' ').title()}\n"
            f"Support category: {support_category}\n"
            f"Family size: {family_size}\n"
            f"Housing status: {housing_status}\n"
            f"Employment status: {employment_status}\n"
            f"Available recommendations: {recommendation_text[:200]}\n"
            f"User's follow-up question: {user_response}"
        )

        follow_up_prompt = (
            "You are a compassionate case worker answering a follow-up question "
            "from an applicant about their application decision and next steps. "
            "Use the applicant's profile and the available recommendations to provide "
            "a helpful, personalized answer. Be empathetic and specific."
        )

        follow_up_response = await _generate_llm_response(
            follow_up_prompt, follow_up_context,
            f"Thank you for your question. Based on your situation and the {decision.replace('_', ' ')} decision, I'm here to help guide you through the next steps."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info("node_exit", node="enablement", duration_ms=round(duration_ms, 2), recommendation_count=len(recommendations), decision=decision, follow_up=True)
        return {
            "messages": [_make_assistant_message(follow_up_response)],
            "current_phase": "enablement",
            "enablement_recommendations": recommendations,
        }

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", node="enablement", duration_ms=round(duration_ms, 2), recommendation_count=len(recommendations), decision=decision)

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": "enablement",
        "enablement_recommendations": recommendations,
    }
