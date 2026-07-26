"""Eligibility tools: ML predict, feature importance, factor adjustment, explanation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)

# Feature names expected by the ML model (order matters for prediction)
ML_FEATURE_NAMES = [
    "monthly_income",
    "family_size",
    "employment_stability_months",
    "credit_score",
    "debt_to_income_ratio",
    "net_worth",
    "housing_cost_ratio",
    "has_dependents",
]

# Support category adjustments (aligned with EligibilityService)
CATEGORY_ADJUSTMENTS = {
    "divorced": 0.10,
    "abandoned": 0.15,
    "unknown_parentage": 0.12,
    "health_disability": 0.08,
}

# Module-level model cache
_ml_model = None
_ml_model_loaded = False


def _load_ml_model():
    """Load the scikit-learn HistGradientBoostingClassifier if available."""
    global _ml_model, _ml_model_loaded
    if _ml_model_loaded:
        return _ml_model

    model_path = Path(__file__).parent.parent.parent / "models" / "eligibility_model.pkl"
    try:
        import joblib
        if model_path.exists():
            _ml_model = joblib.load(model_path)
            logger.info("ml_model_loaded", model_path=str(model_path))
        else:
            logger.warning("ml_model_not_found", model_path=str(model_path))
            _ml_model = None
    except Exception as e:
        logger.warning("ml_model_load_failed", error=str(e))
        _ml_model = None

    _ml_model_loaded = True
    return _ml_model


def _rule_based_predict(features: dict) -> dict:
    """Fallback rule-based scoring aligned with EligibilityService._compute_score."""
    score = 0.45
    factor_contributions: dict[str, float] = {}

    # Credit score
    credit_score = features.get("credit_score", 600)
    if credit_score >= 750:
        score += 0.20
        factor_contributions["excellent_credit"] = 0.20
    elif credit_score >= 700:
        score += 0.15
        factor_contributions["good_credit"] = 0.15
    elif credit_score >= 650:
        score += 0.08
        factor_contributions["fair_credit"] = 0.08
    elif credit_score >= 500:
        factor_contributions["poor_credit"] = 0.0
    else:
        score -= 0.10
        factor_contributions["very_poor_credit"] = -0.10

    # Debt-to-income ratio
    dti = features.get("debt_to_income_ratio", 0)
    if dti < 0.3:
        score += 0.10
        factor_contributions["low_debt_ratio"] = 0.10
    elif dti < 0.5:
        score += 0.05
        factor_contributions["moderate_debt_ratio"] = 0.05
    elif dti < 0.8:
        # Common range for UAE residents with auto/housing loans; neutral
        factor_contributions["high_debt_ratio"] = 0.0
    else:
        score -= 0.15
        factor_contributions["excessive_debt_ratio"] = -0.15

    # Employment stability
    employment_months = features.get("employment_stability_months", 0)
    employment_status = features.get("employment_status", "")
    if employment_months >= 36:
        score += 0.10
        factor_contributions["stable_employment"] = 0.10
    elif employment_months >= 12:
        score += 0.05
        factor_contributions["adequate_employment"] = 0.05
    elif employment_status == "employed" and employment_months == 0:
        # Resume may not have been extracted; don't penalize employed applicants
        score += 0.03
        factor_contributions["employed_no_resume"] = 0.03
    else:
        score -= 0.05
        factor_contributions["short_employment_history"] = -0.05

    # Net worth
    net_worth = features.get("net_worth", 0)
    if net_worth > 500_000:
        score += 0.08
        factor_contributions["strong_net_worth"] = 0.08
    elif net_worth > 100_000:
        score += 0.04
        factor_contributions["positive_net_worth"] = 0.04
    elif net_worth < 0:
        score -= 0.10
        factor_contributions["negative_net_worth"] = -0.10

    # Support category
    support_category = features.get("support_category", "")
    category_adj = CATEGORY_ADJUSTMENTS.get(support_category, 0)
    if category_adj > 0:
        score += category_adj
        factor_contributions[f"{support_category}_adjustment"] = category_adj

    # Family size
    family_size = features.get("family_size", 1)
    if family_size > 3:
        score += 0.05
        factor_contributions["large_family_support"] = 0.05

    # Housing cost ratio
    housing_ratio = features.get("housing_cost_ratio", 0)
    if housing_ratio <= 0.25:
        score += 0.05
        factor_contributions["affordable_housing"] = 0.05
    elif housing_ratio > 0.4:
        score -= 0.05
        factor_contributions["high_housing_cost"] = -0.05

    score = max(0.0, min(1.0, score))
    predicted_class = "eligible" if score >= 0.60 else "not_eligible"

    return {
        "probability": round(score, 4),
        "predicted_class": predicted_class,
        "method": "rule_based",
        "factor_contributions": factor_contributions,
    }


def _extract_ml_features(applicant_features: dict) -> list[float]:
    """Extract numeric feature vector for ML model."""
    return [
        float(applicant_features.get("monthly_income", 0)),
        float(applicant_features.get("family_size", 1)),
        float(applicant_features.get("employment_stability_months", 0)),
        float(applicant_features.get("credit_score", 600)),
        float(applicant_features.get("debt_to_income_ratio", 0)),
        float(applicant_features.get("net_worth", 0)),
        float(applicant_features.get("housing_cost_ratio", 0)),
        float(applicant_features.get("has_dependents", 0)),
    ]


@tool
def ml_model_predict_tool(applicant_features: dict[str, Any]) -> dict[str, Any]:
    """Call scikit-learn HistGradientBoostingClassifier to predict eligibility.

    Falls back to rule-based scoring if ML model is not available.

    Args:
        applicant_features: Feature dict with keys:
            - monthly_income: float
            - family_size: int
            - employment_stability_months: int
            - credit_score: int
            - debt_to_income_ratio: float
            - net_worth: float
            - housing_cost_ratio: float
            - support_category: str
            - has_dependents: bool
            - employment_status: str

    Returns:
        Dict with probability, predicted_class, method, and factor_contributions.
    """
    start = time.monotonic()

    model = _load_ml_model()
    if model is not None:
        try:
            feature_vector = _extract_ml_features(applicant_features)
            x = np.array([feature_vector])
            probability = float(model.predict_proba(x)[0][1])
            predicted_class = "eligible" if probability >= 0.60 else "not_eligible"

            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "ml_prediction_complete",
                method="ml_model",
                predicted_class=predicted_class,
                probability=round(probability, 4),
                duration_ms=round(duration_ms, 2),
            )

            return {
                "probability": round(probability, 4),
                "predicted_class": predicted_class,
                "method": "ml_model",
                "factor_contributions": {},
            }
        except Exception as e:
            logger.warning("ml_prediction_failed", error=str(e), fallback="rule_based")

    result = _rule_based_predict(applicant_features)
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "ml_prediction_complete",
        method=result["method"],
        predicted_class=result["predicted_class"],
        probability=result["probability"],
        duration_ms=round(duration_ms, 2),
    )
    return result


@tool
def feature_importance_tool(
    applicant_features: dict[str, Any],
    n_top_features: int = 5,
) -> dict[str, Any]:
    """Compute feature importance using SHAP values or permutation importance.

    Falls back to factor_contributions from rule-based scoring if ML model unavailable.

    Args:
        applicant_features: Same feature dict as ml_model_predict_tool.
        n_top_features: Number of top features to return.

    Returns:
        Dict with top_features list and method used.
    """
    start = time.monotonic()

    model = _load_ml_model()
    if model is not None:
        try:
            feature_vector = _extract_ml_features(applicant_features)
            x = np.array([feature_vector])

            try:
                import shap
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(x)
                if isinstance(shap_values, list):
                    shap_values = shap_values[1]
                importances = shap_values[0]
                method = "shap"
            except ImportError:
                from sklearn.inspection import permutation_importance
                full_x = np.tile(x, (50, 1))
                y_placeholder = np.zeros(50)
                perm_result = permutation_importance(model, full_x, y_placeholder, n_repeats=5)
                importances = perm_result.importances_mean
                method = "permutation"

            indexed = list(enumerate(importances))
            indexed.sort(key=lambda t: abs(t[1]), reverse=True)
            top_features = [
                {"feature": ML_FEATURE_NAMES[i], "importance": round(float(v), 4)}
                for i, v in indexed[:n_top_features]
            ]

            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "feature_importance_computed",
                method=method,
                top_feature=top_features[0]["feature"] if top_features else None,
                duration_ms=round(duration_ms, 2),
            )
            return {"top_features": top_features, "method": method}

        except Exception as e:
            logger.warning("feature_importance_ml_failed", error=str(e), fallback="rule_based")

    # Fallback: derive importance from rule-based factor contributions
    rule_result = _rule_based_predict(applicant_features)
    contributions = rule_result["factor_contributions"]
    sorted_factors = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_features = [
        {"feature": name, "importance": round(value, 4)}
        for name, value in sorted_factors[:n_top_features]
    ]

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "feature_importance_computed",
        method="rule_based_factors",
        top_feature=top_features[0]["feature"] if top_features else None,
        duration_ms=round(duration_ms, 2),
    )
    return {"top_features": top_features, "method": "rule_based_factors"}


@tool
def adjust_factor_weighting_tool(
    eligibility_score: float,
    feature_importance: list[dict[str, Any]],
    applicant_context: dict[str, Any],
) -> dict[str, Any]:
    """Adjust eligibility score based on applicant context and support category.

    Provides context-aware interpretation of the ML/rule-based score.

    Args:
        eligibility_score: Raw eligibility score (0-1).
        feature_importance: List of {feature, importance} dicts.
        applicant_context: Dict with support_category, family_size, has_dependents, etc.

    Returns:
        Dict with adjusted_score, adjustment_amount, and reasoning.
    """
    start = time.monotonic()

    support_category = applicant_context.get("support_category", "")
    family_size = applicant_context.get("family_size", 1)
    has_dependents = applicant_context.get("has_dependents", False)
    employment_status = applicant_context.get("employment_status", "")

    adjustment = 0.0
    reasons: list[str] = []

    # Category-based adjustment
    category_adj = CATEGORY_ADJUSTMENTS.get(support_category, 0)
    if category_adj > 0:
        adjustment += category_adj * 0.5  # Half the raw category adjustment for context
        reasons.append(
            f"Support category '{support_category.replace('_', ' ')}' "
            f"warrants additional consideration (+{category_adj * 0.5:.2f})"
        )

    # Large family with dependents
    if has_dependents and family_size > 3:
        dep_adj = 0.03 * (family_size - 3)
        dep_adj = min(dep_adj, 0.10)
        adjustment += dep_adj
        reasons.append(f"Large family with {family_size} members (+{dep_adj:.2f})")

    # Unemployed but seeking support — employment instability is expected
    if employment_status == "unemployed" and support_category in ("divorced", "abandoned"):
        adjustment += 0.03
        reasons.append("Recent life transition may explain employment gap (+0.03)")

    adjustment = round(adjustment, 4)
    adjusted_score = round(max(0.0, min(1.0, eligibility_score + adjustment)), 4)

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "factor_weighting_adjusted",
        original_score=eligibility_score,
        adjusted_score=adjusted_score,
        adjustment=adjustment,
        reasons_count=len(reasons),
        duration_ms=round(duration_ms, 2),
    )

    return {
        "adjusted_score": adjusted_score,
        "adjustment_amount": adjustment,
        "reasoning": "; ".join(reasons) if reasons else "No contextual adjustments needed.",
    }


@tool
def eligibility_explanation_tool(
    eligibility_score: float,
    feature_importance: list[dict[str, Any]],
    applicant_context: dict[str, Any],
    validation_results: dict[str, Any],
) -> dict[str, Any]:
    """Generate human-readable explanation of eligibility decision.

    Args:
        eligibility_score: Final (possibly adjusted) eligibility score (0-1).
        feature_importance: List of {feature, importance} dicts.
        applicant_context: Dict with support_category, family_size, etc.
        validation_results: Dict with validation confidence and status.

    Returns:
        Dict with explanation text, key_factors, and recommendation.
    """
    start = time.monotonic()

    parts: list[str] = []

    # Overall eligibility statement
    if eligibility_score >= 0.70:
        parts.append(
            f"The application meets eligibility criteria with a score of {eligibility_score:.0%}."
        )
    elif eligibility_score >= 0.50:
        parts.append(
            f"The application is borderline with a score of {eligibility_score:.0%} "
            f"and may require manual review."
        )
    else:
        parts.append(
            f"The application does not meet minimum eligibility criteria "
            f"with a score of {eligibility_score:.0%}."
        )

    # Support category context
    support_category = applicant_context.get("support_category", "unknown")
    if support_category and support_category != "unknown":
        parts.append(
            f"Support category: {support_category.replace('_', ' ').title()}."
        )

    # Key factors
    key_factors: list[str] = []
    for fi in feature_importance[:3]:
        name = fi.get("feature", "").replace("_", " ")
        importance = fi.get("importance", 0)
        direction = "positively" if importance > 0 else "negatively"
        key_factors.append(f"{name} ({direction})")

    if key_factors:
        parts.append(f"Key driving factors: {', '.join(key_factors)}.")

    # Credit assessment
    credit_score = applicant_context.get("credit_score", 0)
    if credit_score >= 700:
        parts.append(f"Credit score of {credit_score} is in the good range.")
    elif credit_score >= 500:
        parts.append(f"Credit score of {credit_score} is in the fair range.")
    elif credit_score > 0:
        parts.append(f"Credit score of {credit_score} is below the preferred threshold.")

    # Validation confidence
    val_confidence = validation_results.get("overall_confidence", 0)
    if val_confidence > 0:
        parts.append(f"Data validation confidence: {val_confidence:.0%}.")

    # Recommendation
    if eligibility_score >= 0.60:
        recommendation = "proceed_to_decision"
    elif eligibility_score >= 0.40:
        recommendation = "manual_review"
    else:
        recommendation = "likely_ineligible"

    explanation = " ".join(parts)

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "eligibility_explanation_generated",
        score=eligibility_score,
        recommendation=recommendation,
        explanation_length=len(explanation),
        duration_ms=round(duration_ms, 2),
    )

    return {
        "explanation": explanation,
        "key_factors": key_factors,
        "recommendation": recommendation,
    }
