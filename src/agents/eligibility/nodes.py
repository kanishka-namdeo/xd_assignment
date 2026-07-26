"""Eligibility node functions with direct tool calls and Gate 3 integration."""

from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from src.agents.eligibility.tools import (
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
    feature_importance_tool,
    ml_model_predict_tool,
)
from src.agents.gates.eligibility_rules import check_hard_eligibility_rules

logger = structlog.get_logger(__name__)


def _build_applicant_features(state: dict) -> dict[str, Any]:
    """Extract applicant features from state for ML prediction."""
    extracted_data = state.get("extracted_data", {})
    validation_results = state.get("validation_results", {})

    # Extract features from extracted data
    features: dict[str, Any] = {}

    # From application form
    app_form = extracted_data.get("application_form", {})
    features["monthly_income"] = float(app_form.get("total_monthly_income", 0))
    features["family_size"] = int(app_form.get("family_size", 1))
    features["support_category"] = app_form.get("support_category", "")
    features["employment_status"] = app_form.get("employment_status", "")
    features["has_dependents"] = features["family_size"] > 1

    # From credit report
    credit_report = extracted_data.get("credit_report", {})
    features["credit_score"] = int(credit_report.get("credit_score", 600))

    # Calculate monthly debt payments from active facilities
    active_facilities = credit_report.get("active_facilities", [])
    monthly_debt_payments = sum(
        float(facility.get("monthly_payment", 0))
        for facility in active_facilities
        if isinstance(facility, dict)
    )
    
    # Debt-to-income ratio: monthly debt payments / monthly income
    monthly_income = features["monthly_income"]
    if monthly_income > 0:
        features["debt_to_income_ratio"] = monthly_debt_payments / monthly_income
    else:
        features["debt_to_income_ratio"] = 0.0

    # From assets/liabilities
    assets = extracted_data.get("assets_liabilities", {})
    features["net_worth"] = float(assets.get("net_worth", 0))

    # Housing cost ratio
    monthly_rent = float(app_form.get("monthly_rent", 0))
    monthly_mortgage = float(app_form.get("monthly_mortgage", 0))
    if monthly_income > 0:
        features["housing_cost_ratio"] = (monthly_rent + monthly_mortgage) / monthly_income
    else:
        features["housing_cost_ratio"] = 0.0

    # From resume (employment stability)
    resume = extracted_data.get("resume", {})
    work_exp = resume.get("work_experience", [])
    if isinstance(work_exp, list) and work_exp:
        total_months = sum(exp.get("duration_months", 0) for exp in work_exp)
        features["employment_stability_months"] = total_months
    else:
        features["employment_stability_months"] = 0

    logger.debug(
        "applicant_features_extracted",
        monthly_income=features.get("monthly_income"),
        family_size=features.get("family_size"),
        credit_score=features.get("credit_score"),
        debt_to_income_ratio=round(features.get("debt_to_income_ratio", 0), 2),
    )

    return features


async def eligibility_react_node(state: dict) -> dict:
    """Assess eligibility by calling tools directly in sequence."""
    start = time.monotonic()
    logger.info("node_enter", node="eligibility_assessment", state_keys=list(state.keys()))

    applicant_id = state.get("applicant_id", "unknown")
    application_id = state.get("application_id", "unknown")

    try:
        # Build applicant features from extracted data
        applicant_features = _build_applicant_features(state)

        # Step 1: ML prediction
        ml_result = ml_model_predict_tool.invoke({"applicant_features": applicant_features})

        # Step 2: Feature importance
        importance_result = feature_importance_tool.invoke(
            {"applicant_features": applicant_features, "n_top_features": 5}
        )

        # Step 3: Adjust factor weighting
        adjust_result = adjust_factor_weighting_tool.invoke(
            {
                "eligibility_score": ml_result["probability"],
                "feature_importance": importance_result["top_features"],
                "applicant_context": applicant_features,
            }
        )

        # Step 4: Generate explanation
        explanation_result = eligibility_explanation_tool.invoke(
            {
                "eligibility_score": adjust_result["adjusted_score"],
                "feature_importance": importance_result["top_features"],
                "applicant_context": applicant_features,
                "validation_results": state.get("validation_results", {}),
            }
        )

        eligibility_score = adjust_result["adjusted_score"]
        eligibility_factors = ml_result.get("factor_contributions", {})

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "eligibility_assessment_complete",
            applicant_id=applicant_id,
            application_id=application_id,
            eligibility_score=eligibility_score,
            method=ml_result["method"],
            duration_ms=round(duration_ms, 2),
        )

        return {
            "eligibility_score": eligibility_score,
            "eligibility_factors": eligibility_factors,
            "messages": [
                HumanMessage(
                    content=(
                        f"Eligibility assessment complete. Score: {eligibility_score:.2f}. "
                        f"Explanation: {explanation_result['explanation']}"
                    )
                )
            ],
        }

    except Exception as e:
        logger.exception(
            "eligibility_assessment_failed",
            applicant_id=applicant_id,
            application_id=application_id,
            error=str(e),
        )
        # Fallback to rule-based scoring (bypass tool layer to avoid re-triggering failure)
        from src.agents.eligibility.tools import _rule_based_predict

        applicant_features = _build_applicant_features(state)
        ml_result = _rule_based_predict(applicant_features)
        return {
            "eligibility_score": ml_result["probability"],
            "eligibility_factors": ml_result.get("factor_contributions", {}),
            "messages": [
                HumanMessage(
                    content=f"Eligibility assessment failed. Using fallback score: {ml_result['probability']:.2f}"
                )
            ],
        }


async def eligibility_gate_node(state: dict) -> dict:
    """Run Gate 3: Hard eligibility rules validation."""
    start = time.monotonic()
    logger.info("node_enter", node="eligibility_gate", state_keys=list(state.keys()))

    applicant_id = state.get("applicant_id", "unknown")
    application_id = state.get("application_id", "unknown")

    extracted_data = state.get("extracted_data", {})
    validation_results = state.get("validation_results", {})

    # Run hard eligibility rules
    passes, failure_reason = check_hard_eligibility_rules(extracted_data, validation_results)

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "eligibility_gate_complete",
        applicant_id=applicant_id,
        application_id=application_id,
        gate_passed=passes,
        failure_reason=failure_reason,
        duration_ms=round(duration_ms, 2),
    )

    if passes:
        return {
            "gate_status": "passed",
            "gate_errors": [],
            "messages": [HumanMessage(content="Gate 3 (eligibility rules) passed.")],
        }
    else:
        return {
            "gate_status": "failed",
            "gate_errors": [failure_reason],
            "messages": [
                HumanMessage(
                    content=f"Gate 3 failed: {failure_reason}. Eligibility cannot be assessed."
                )
            ],
        }


async def eligibility_finalize_node(state: dict) -> dict:
    """Finalize eligibility results and prepare for decision agent."""
    start = time.monotonic()
    logger.info("node_enter", node="eligibility_finalize", state_keys=list(state.keys()))

    applicant_id = state.get("applicant_id", "unknown")
    application_id = state.get("application_id", "unknown")
    eligibility_score = state.get("eligibility_score")
    gate_status = state.get("gate_status", "unknown")

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "eligibility_finalize_complete",
        applicant_id=applicant_id,
        application_id=application_id,
        eligibility_score=eligibility_score,
        gate_status=gate_status,
        duration_ms=round(duration_ms, 2),
    )

    if gate_status == "passed" and eligibility_score is not None:
        return {
            "messages": [
                HumanMessage(
                    content=(
                        f"Eligibility assessment complete. Score: {eligibility_score:.2f}. "
                        f"Proceeding to decision agent."
                    )
                )
            ]
        }
    else:
        return {
            "messages": [
                HumanMessage(
                    content="Eligibility assessment incomplete or gate failed. Cannot proceed to decision."
                )
            ]
        }
