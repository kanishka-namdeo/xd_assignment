"""Decision tools for ReAct reasoning loop."""

import time
from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
def decision_logic_tool(
    eligibility_score: Any = None,
    validation_confidence: Any = None,
    discrepancies: Any = None,
    support_category: Any = None,
) -> dict[str, Any]:
    """Apply decision rules to determine final recommendation.

    Decision rules:
    - eligibility_score > 0.60 AND validation_confidence > 0.80 AND no critical discrepancies -> approved
    - eligibility_score < 0.40 OR validation_confidence < 0.70 OR critical discrepancies unresolved -> soft_decline
    - Otherwise -> manual_review

    Args:
        eligibility_score: Eligibility score from ML model (0-1)
        validation_confidence: Overall validation confidence (0-1)
        discrepancies: List of validation discrepancies
        support_category: Applicant's support category

    Returns:
        Dict with decision, reasoning, and confidence
    """
    start = time.perf_counter()

    if eligibility_score is None or not isinstance(eligibility_score, (int, float)):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_logic", reason="eligibility_score must be a number")
        return {
            "decision": "error",
            "reasoning": "eligibility_score must be a number",
            "eligibility_score": 0.0,
            "validation_confidence": 0.0,
            "critical_discrepancies": 0,
            "error": "eligibility_score must be a number",
            "duration_ms": round(duration_ms, 2),
        }

    if validation_confidence is None or not isinstance(validation_confidence, (int, float)):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_logic", reason="validation_confidence must be a number")
        return {
            "decision": "error",
            "reasoning": "validation_confidence must be a number",
            "eligibility_score": 0.0,
            "validation_confidence": 0.0,
            "critical_discrepancies": 0,
            "error": "validation_confidence must be a number",
            "duration_ms": round(duration_ms, 2),
        }

    if discrepancies is None or not isinstance(discrepancies, list):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_logic", reason="discrepancies must be a list")
        return {
            "decision": "error",
            "reasoning": "discrepancies must be a list",
            "eligibility_score": 0.0,
            "validation_confidence": 0.0,
            "critical_discrepancies": 0,
            "error": "discrepancies must be a list",
            "duration_ms": round(duration_ms, 2),
        }

    if support_category is None or not isinstance(support_category, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_logic", reason="support_category must be a string")
        return {
            "decision": "error",
            "reasoning": "support_category must be a string",
            "eligibility_score": 0.0,
            "validation_confidence": 0.0,
            "critical_discrepancies": 0,
            "error": "support_category must be a string",
            "duration_ms": round(duration_ms, 2),
        }

    critical_discrepancies = [
        d
        for d in discrepancies
        if d.get("discrepancy_type") in ["identity_match", "income_consistency"]
        and d.get("resolution_status") == "unresolved"
    ]

    if validation_confidence < 0.80 or len(critical_discrepancies) > 0:
        decision = "manual_review"
        reasoning = (
            f"Validation confidence {validation_confidence:.2f} < 0.80 or "
            f"{len(critical_discrepancies)} unresolved critical discrepancies."
        )
    elif eligibility_score > 0.60:
        decision = "approved"
        reasoning = (
            f"Eligibility score {eligibility_score:.2f} > 0.60, "
            f"confidence {validation_confidence:.2f} >= 0.80, "
            f"no critical discrepancies."
        )
    elif eligibility_score < 0.40:
        decision = "soft_decline"
        reasoning = f"Eligibility score {eligibility_score:.2f} < 0.40."
    else:
        decision = "manual_review"
        reasoning = f"Borderline eligibility score {eligibility_score:.2f} (0.40-0.60)."

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "decision_logic_applied",
        eligibility_score=eligibility_score,
        validation_confidence=validation_confidence,
        decision=decision,
        critical_discrepancies=len(critical_discrepancies),
        duration_ms=round(duration_ms, 2),
    )

    return {
        "decision": decision,
        "reasoning": reasoning,
        "eligibility_score": eligibility_score,
        "validation_confidence": validation_confidence,
        "critical_discrepancies": len(critical_discrepancies),
        "duration_ms": round(duration_ms, 2),
    }


@tool
def decision_explanation_tool(
    decision: Any = None,
    eligibility_score: Any = None,
    validation_confidence: Any = None,
    applicant_context: Any = None,
) -> dict[str, str]:
    """Generate human-readable explanation of the decision.

    Args:
        decision: The decision made (approved/soft_decline/manual_review)
        eligibility_score: Eligibility score (0-1)
        validation_confidence: Validation confidence (0-1)
        applicant_context: Applicant context (name, support_category, etc.)

    Returns:
        Dict with explanation text and key factors
    """
    start = time.perf_counter()

    if decision is None or not isinstance(decision, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_explanation", reason="decision must be a string")
        return {
            "explanation": "Unable to generate explanation: decision must be a string.",
            "key_factors": [],
            "support_category": "unknown",
            "error": "decision must be a string",
            "duration_ms": round(duration_ms, 2),
        }

    if eligibility_score is None or not isinstance(eligibility_score, (int, float)):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_explanation", reason="eligibility_score must be a number")
        return {
            "explanation": "Unable to generate explanation: eligibility_score must be a number.",
            "key_factors": [],
            "support_category": "unknown",
            "error": "eligibility_score must be a number",
            "duration_ms": round(duration_ms, 2),
        }

    if validation_confidence is None or not isinstance(validation_confidence, (int, float)):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_explanation", reason="validation_confidence must be a number")
        return {
            "explanation": "Unable to generate explanation: validation_confidence must be a number.",
            "key_factors": [],
            "support_category": "unknown",
            "error": "validation_confidence must be a number",
            "duration_ms": round(duration_ms, 2),
        }

    if applicant_context is None or not isinstance(applicant_context, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_explanation", reason="applicant_context must be a dict")
        return {
            "explanation": "Unable to generate explanation: applicant_context must be a dict.",
            "key_factors": [],
            "support_category": "unknown",
            "error": "applicant_context must be a dict",
            "duration_ms": round(duration_ms, 2),
        }

    support_category = applicant_context.get("support_category", "general")
    family_size = applicant_context.get("family_size", 1)

    def _score_label(score: float) -> str:
        if score >= 0.80:
            return "very strong"
        if score >= 0.60:
            return "strong"
        if score >= 0.40:
            return "moderate"
        if score >= 0.20:
            return "below average"
        return "low"

    def _confidence_label(confidence: float) -> str:
        if confidence >= 0.90:
            return "very high"
        if confidence >= 0.80:
            return "high"
        if confidence >= 0.70:
            return "moderate"
        return "below the required threshold"

    eligibility_label = _score_label(eligibility_score)
    confidence_label = _confidence_label(validation_confidence)

    if decision == "approved":
        explanation = (
            f"Your application has been approved. Your eligibility profile is "
            f"{eligibility_label} and your documentation has been validated with "
            f"{confidence_label} confidence. You qualify for {support_category} support. "
            f"You will receive assistance tailored to your household of {family_size}."
        )
        key_factors = [
            f"Eligibility profile: {eligibility_label}",
            f"Document validation: {confidence_label} confidence",
            "All required documents validated",
        ]
    elif decision == "soft_decline":
        explanation = (
            f"Unfortunately, your application cannot be approved at this time. "
            f"Your eligibility profile is currently {eligibility_label}, which is "
            f"below the required threshold. You may reapply when your circumstances change."
        )
        key_factors = [
            f"Eligibility profile: {eligibility_label} (below threshold)",
            "Consider improving income stability or reducing debt",
        ]
    else:
        explanation = (
            f"Your application requires additional review. Your eligibility profile is "
            f"{eligibility_label}, which shows potential, but some aspects of your "
            f"documentation need further verification (confidence: {confidence_label}). "
            f"A caseworker will contact you within 5 business days."
        )
        key_factors = [
            f"Eligibility profile: {eligibility_label}",
            f"Document validation confidence: {confidence_label}",
            "Additional documentation or clarification needed",
        ]

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "decision_explanation_generated",
        decision=decision,
        duration_ms=round(duration_ms, 2),
    )

    return {
        "explanation": explanation,
        "key_factors": key_factors,
        "support_category": support_category,
        "duration_ms": round(duration_ms, 2),
    }


@tool
def enablement_recommendation_tool(
    applicant_context: Any = None,
    eligibility_score: Any = None,
    decision: Any = None,
) -> dict[str, Any]:
    """Generate personalized enablement recommendations.

    Args:
        applicant_context: Applicant context (employment_status, skills, etc.)
        eligibility_score: Eligibility score (0-1)
        decision: The decision made

    Returns:
        Dict with list of recommendations tailored to applicant's profile
    """
    start = time.perf_counter()

    if applicant_context is None or not isinstance(applicant_context, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="enablement_recommendation", reason="applicant_context must be a dict")
        return {
            "recommendations": [],
            "total_count": 0,
            "error": "applicant_context must be a dict",
            "duration_ms": round(duration_ms, 2),
        }

    if eligibility_score is None or not isinstance(eligibility_score, (int, float)):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="enablement_recommendation", reason="eligibility_score must be a number")
        return {
            "recommendations": [],
            "total_count": 0,
            "error": "eligibility_score must be a number",
            "duration_ms": round(duration_ms, 2),
        }

    if decision is None or not isinstance(decision, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="enablement_recommendation", reason="decision must be a string")
        return {
            "recommendations": [],
            "total_count": 0,
            "error": "decision must be a string",
            "duration_ms": round(duration_ms, 2),
        }

    recommendations = []

    employment_status = applicant_context.get("employment_status", "unknown")
    has_dependents = applicant_context.get("has_dependents", False)
    credit_score = applicant_context.get("credit_score", 0)

    if decision == "approved":
        if employment_status in ["unemployed", "part_time"]:
            recommendations.append({
                "type": "job_matching",
                "title": "Job Matching Service",
                "description": "Connect with employers seeking your skills",
                "priority": "high",
            })
        if credit_score < 650:
            recommendations.append({
                "type": "financial_literacy",
                "title": "Financial Literacy Program",
                "description": "Improve credit score and financial management",
                "priority": "medium",
            })
        if has_dependents:
            recommendations.append({
                "type": "childcare_support",
                "title": "Childcare Support",
                "description": "Subsidized childcare services",
                "priority": "medium",
            })
        recommendations.append({
            "type": "upskilling",
            "title": "Skills Development",
            "description": "Free training programs to enhance employability",
            "priority": "low",
        })
    elif decision == "manual_review":
        recommendations.append({
            "type": "documentation_assistance",
            "title": "Document Preparation Help",
            "description": "Assistance gathering required documentation",
            "priority": "high",
        })
        recommendations.append({
            "type": "caseworker_consultation",
            "title": "Caseworker Consultation",
            "description": "Meet with a caseworker to discuss your situation",
            "priority": "high",
        })
    else:
        recommendations.append({
            "type": "financial_counseling",
            "title": "Financial Counseling",
            "description": "Free counseling to improve financial stability",
            "priority": "high",
        })
        recommendations.append({
            "type": "reapplication_guidance",
            "title": "Reapplication Guidance",
            "description": "Learn what changes could improve eligibility",
            "priority": "medium",
        })

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "enablement_recommendations_generated",
        decision=decision,
        recommendation_count=len(recommendations),
        duration_ms=round(duration_ms, 2),
    )

    return {
        "recommendations": recommendations,
        "total_count": len(recommendations),
        "duration_ms": round(duration_ms, 2),
    }


@tool
def decision_formatting_tool(
    decision: Any = None,
    explanation: Any = None,
    enablement_recommendations: Any = None,
    applicant_context: Any = None,
) -> dict[str, Any]:
    """Format the final decision for display in the chat interface.

    Args:
        decision: The decision made (approved/soft_decline/manual_review)
        explanation: Human-readable explanation
        enablement_recommendations: Optional enablement recommendations
        applicant_context: Applicant context

    Returns:
        Dict with formatted decision card and styling information
    """
    start = time.perf_counter()

    if decision is None or not isinstance(decision, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_formatting", reason="decision must be a string")
        return {
            "title": "Error",
            "decision": "error",
            "color": "red",
            "icon": "error",
            "explanation": "decision must be a string",
            "next_steps": [],
            "enablement_section": None,
            "error": "decision must be a string",
            "duration_ms": round(duration_ms, 2),
        }

    if explanation is None or not isinstance(explanation, str):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_formatting", reason="explanation must be a string")
        return {
            "title": "Error",
            "decision": "error",
            "color": "red",
            "icon": "error",
            "explanation": "explanation must be a string",
            "next_steps": [],
            "enablement_section": None,
            "error": "explanation must be a string",
            "duration_ms": round(duration_ms, 2),
        }

    if applicant_context is None or not isinstance(applicant_context, dict):
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning("tool_invalid_input", tool="decision_formatting", reason="applicant_context must be a dict")
        return {
            "title": "Error",
            "decision": "error",
            "color": "red",
            "icon": "error",
            "explanation": "applicant_context must be a dict",
            "next_steps": [],
            "enablement_section": None,
            "error": "applicant_context must be a dict",
            "duration_ms": round(duration_ms, 2),
        }

    if decision == "approved":
        color = "green"
        icon = "check_circle"
        title = "Application Approved"
    elif decision == "soft_decline":
        color = "red"
        icon = "cancel"
        title = "Application Not Approved"
    else:
        color = "orange"
        icon = "pending"
        title = "Application Under Review"

    formatted_card = {
        "title": title,
        "decision": decision,
        "color": color,
        "icon": icon,
        "explanation": explanation,
        "next_steps": [],
        "enablement_section": None,
    }

    if decision == "approved":
        formatted_card["next_steps"] = [
            "You will receive a confirmation email shortly",
            "Support will be disbursed within 5 business days",
            "Check your dashboard for support details",
        ]
    elif decision == "manual_review":
        formatted_card["next_steps"] = [
            "A caseworker will review your application",
            "You may be contacted for additional information",
            "Decision expected within 10 business days",
        ]
    else:
        formatted_card["next_steps"] = [
            "You can reapply after 3 months",
            "Consider the recommendations below to improve eligibility",
            "Contact support for clarification",
        ]

    if enablement_recommendations and enablement_recommendations.get("recommendations"):
        formatted_card["enablement_section"] = {
            "title": "Recommended Support Programs",
            "items": enablement_recommendations["recommendations"],
        }

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "decision_formatted",
        decision=decision,
        duration_ms=round(duration_ms, 2),
    )

    formatted_card["duration_ms"] = round(duration_ms, 2)
    return formatted_card
