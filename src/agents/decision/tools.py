"""Decision tools for ReAct reasoning loop."""

import time
from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
def decision_logic_tool(
    eligibility_score: float,
    validation_confidence: float,
    discrepancies: list[dict[str, Any]],
    support_category: str,
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
    }


@tool
def decision_explanation_tool(
    decision: str,
    eligibility_score: float,
    validation_confidence: float,
    applicant_context: dict[str, Any],
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

    support_category = applicant_context.get("support_category", "general")
    family_size = applicant_context.get("family_size", 1)

    if decision == "approved":
        explanation = (
            f"Your application has been approved. Based on your eligibility score "
            f"of {eligibility_score:.2f} and validated documentation, you qualify "
            f"for {support_category} support. "
            f"You will receive assistance tailored to your household of {family_size}."
        )
        key_factors = [
            f"Strong eligibility score: {eligibility_score:.2f}",
            f"High validation confidence: {validation_confidence:.2f}",
            "All required documents validated",
        ]
    elif decision == "soft_decline":
        explanation = (
            f"Unfortunately, your application cannot be approved at this time. "
            f"Your eligibility score of {eligibility_score:.2f} is below the threshold. "
            f"You may reapply when your circumstances change."
        )
        key_factors = [
            f"Eligibility score below threshold: {eligibility_score:.2f}",
            "Consider improving income stability or reducing debt",
        ]
    else:
        explanation = (
            f"Your application requires additional review. While your eligibility score "
            f"of {eligibility_score:.2f} shows potential, some aspects need verification. "
            f"A caseworker will contact you within 5 business days."
        )
        key_factors = [
            f"Eligibility score: {eligibility_score:.2f}",
            f"Validation confidence: {validation_confidence:.2f}",
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
    }


@tool
def enablement_recommendation_tool(
    applicant_context: dict[str, Any],
    eligibility_score: float,
    decision: str,
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
    }


@tool
def decision_formatting_tool(
    decision: str,
    explanation: str,
    enablement_recommendations: dict[str, Any] | None,
    applicant_context: dict[str, Any],
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

    return formatted_card
