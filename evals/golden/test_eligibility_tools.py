"""Layer 2: Golden dataset validation — eligibility tools."""

import pytest

from src.agents.eligibility.tools import (
    ml_model_predict_tool,
    feature_importance_tool,
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
)


class TestEligibilityGoldenDataset:
    """Run eligibility tools against golden profile features."""

    def test_ml_predict_approved_profile(self, approved_profile):
        """ML prediction for approved profile returns eligible."""
        applicant = approved_profile.get("applicant", {})
        features = {
            "monthly_income": float(applicant.get("total_monthly_income", 15000)),
            "family_size": int(applicant.get("family_size", 3)),
            "employment_stability_months": 24,
            "credit_score": 720,
            "debt_to_income_ratio": 0.35,
            "net_worth": 50000,
            "housing_cost_ratio": 0.23,
            "support_category": applicant.get("support_category", ""),
            "has_dependents": len(applicant.get("dependents", [])) > 0,
            "employment_status": applicant.get("employment_status", "employed"),
        }
        result = ml_model_predict_tool.invoke({"applicant_features": features})
        assert "predicted_class" in result
        assert "probability" in result
        assert result["method"] in ("ml_model", "rule_based")

    def test_feature_importance(self, approved_profile):
        """Feature importance tool returns ranked features."""
        features = {
            "monthly_income": 15000,
            "credit_score": 720,
            "debt_to_income_ratio": 0.35,
        }
        result = feature_importance_tool.invoke({"applicant_features": features})
        assert "top_features" in result
        assert "method" in result

    def test_factor_weighting_adjustment(self, approved_profile):
        """Factor weighting adjusts score based on context."""
        result = adjust_factor_weighting_tool.invoke({
            "eligibility_score": 0.65,
            "feature_importance": [{"feature": "credit_score", "importance": 0.3}],
            "applicant_context": {
                "support_category": "divorced",
                "family_size": 3,
                "has_dependents": True,
                "employment_status": "employed",
            },
        })
        assert "adjusted_score" in result
        assert "adjustment_amount" in result
        assert "reasoning" in result

    def test_eligibility_explanation(self, approved_profile):
        """Explanation tool generates readable text."""
        result = eligibility_explanation_tool.invoke({
            "eligibility_score": 0.70,
            "feature_importance": [{"feature": "credit_score", "importance": 0.3}],
            "applicant_context": {"support_category": "divorced", "credit_score": 720},
            "validation_results": {"overall_confidence": 0.90},
        })
        assert "explanation" in result
        assert "key_factors" in result
