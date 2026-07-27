"""Layer 2: Golden dataset validation — decision tools."""

import pytest

from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)


class TestDecisionGoldenDataset:
    """Run decision tools against golden profile scores."""

    def test_decision_logic_approved(self, approved_profile):
        """High score + high confidence + no discrepancies = approved."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "discrepancies": [],
            "support_category": "divorced",
        })
        assert result["decision"] == "approved"

    def test_decision_logic_soft_decline(self, soft_decline_profile):
        """Low score = soft_decline."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.25,
            "validation_confidence": 0.90,
            "discrepancies": [],
            "support_category": "unknown_parentage",
        })
        assert result["decision"] == "soft_decline"

    def test_decision_explanation(self, approved_profile):
        """Explanation tool generates decision-specific text."""
        result = decision_explanation_tool.invoke({
            "decision": "approved",
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "applicant_context": {
                "support_category": "divorced",
                "family_size": 3,
            },
        })
        assert "explanation" in result
        assert "key_factors" in result

    def test_enablement_recommendations(self, approved_profile):
        """Enablement tool returns recommendations for approved decision."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "employed",
                "has_dependents": True,
                "credit_score": 720,
            },
            "eligibility_score": 0.75,
            "decision": "approved",
        })
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    def test_decision_formatting(self, approved_profile):
        """Formatting tool produces a decision card."""
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Your application is approved.",
            "enablement_recommendations": {"recommendations": []},
            "applicant_context": {"support_category": "divorced"},
        })
        assert result["title"] == "Application Approved"
        assert result["color"] == "green"
        assert result["icon"] == "check_circle"
