"""Layer 2: Golden dataset validation — decision tools."""

import time

import pytest
import structlog

from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)

logger = structlog.get_logger(__name__)


class TestDecisionGoldenDataset:
    """Run decision tools against golden profile scores."""

    def test_decision_logic_approved(self, approved_profile):
        """High score + high confidence + no discrepancies = approved."""
        start = time.perf_counter()
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "discrepancies": [],
            "support_category": "divorced",
        })
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "tool_invoked",
            tool="decision_logic_tool",
            duration_ms=round(duration_ms, 2),
            decision=result.get("decision"),
        )
        assert result["decision"] == "approved"

    def test_decision_logic_soft_decline(self, soft_decline_profile):
        """Low score = soft_decline."""
        start = time.perf_counter()
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.25,
            "validation_confidence": 0.90,
            "discrepancies": [],
            "support_category": "unknown_parentage",
        })
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "tool_invoked",
            tool="decision_logic_tool",
            duration_ms=round(duration_ms, 2),
            decision=result.get("decision"),
        )
        assert result["decision"] == "soft_decline"

    def test_decision_explanation(self, approved_profile):
        """Explanation tool generates decision-specific text."""
        start = time.perf_counter()
        result = decision_explanation_tool.invoke({
            "decision": "approved",
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "applicant_context": {
                "support_category": "divorced",
                "family_size": 3,
            },
        })
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "tool_invoked",
            tool="decision_explanation_tool",
            duration_ms=round(duration_ms, 2),
            decision="approved",
            has_explanation="explanation" in result,
        )
        assert "explanation" in result
        assert "key_factors" in result

    def test_enablement_recommendations(self, approved_profile):
        """Enablement tool returns recommendations for approved decision."""
        start = time.perf_counter()
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "employed",
                "has_dependents": True,
                "credit_score": 720,
            },
            "eligibility_score": 0.75,
            "decision": "approved",
        })
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "tool_invoked",
            tool="enablement_recommendation_tool",
            duration_ms=round(duration_ms, 2),
            recommendation_count=len(result.get("recommendations", [])),
        )
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    def test_decision_formatting(self, approved_profile):
        """Formatting tool produces a decision card."""
        start = time.perf_counter()
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Your application is approved.",
            "enablement_recommendations": {"recommendations": []},
            "applicant_context": {"support_category": "divorced"},
        })
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "tool_invoked",
            tool="decision_formatting_tool",
            duration_ms=round(duration_ms, 2),
            title=result.get("title"),
            color=result.get("color"),
        )
        assert result["title"] == "Application Approved"
        assert result["color"] == "green"
        assert result["icon"] == "check_circle"
