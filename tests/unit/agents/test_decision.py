"""Unit tests for decision agent nodes and tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.decision.nodes import decision_react_node, synthesize_decision_node
from src.agents.decision.routes import should_use_react
from src.agents.decision.tools import (
    decision_explanation_tool,
    decision_formatting_tool,
    decision_logic_tool,
    enablement_recommendation_tool,
)


class TestDecisionLogicTool:
    """Test decision_logic_tool across all decision paths."""

    def test_approved_high_score_high_confidence_no_discrepancies(self):
        """score > 0.60, confidence > 0.80, no discrepancies -> approved."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.75,
            "validation_confidence": 0.92,
            "discrepancies": [],
            "support_category": "divorced",
        })

        assert result["decision"] == "approved"
        assert result["eligibility_score"] == 0.75
        assert result["validation_confidence"] == 0.92
        assert result["critical_discrepancies"] == 0
        assert "0.75" in result["reasoning"]

    def test_soft_decline_low_score(self):
        """score < 0.40 -> soft_decline."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.25,
            "validation_confidence": 0.90,
            "discrepancies": [],
            "support_category": "abandoned",
        })

        assert result["decision"] == "soft_decline"
        assert result["eligibility_score"] == 0.25
        assert "0.25" in result["reasoning"]

    def test_manual_review_low_confidence(self):
        """confidence < 0.80 -> manual_review."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.70,
            "validation_confidence": 0.65,
            "discrepancies": [],
            "support_category": "divorced",
        })

        assert result["decision"] == "manual_review"
        assert result["validation_confidence"] == 0.65

    def test_manual_review_critical_discrepancy(self):
        """critical discrepancy (identity_match unresolved) -> manual_review."""
        discrepancies = [
            {
                "discrepancy_type": "identity_match",
                "resolution_status": "unresolved",
                "severity": "critical",
            }
        ]
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.80,
            "validation_confidence": 0.95,
            "discrepancies": discrepancies,
            "support_category": "divorced",
        })

        assert result["decision"] == "manual_review"
        assert result["critical_discrepancies"] == 1

    def test_manual_review_income_consistency_discrepancy(self):
        """income_consistency unresolved discrepancy -> manual_review."""
        discrepancies = [
            {
                "discrepancy_type": "income_consistency",
                "resolution_status": "unresolved",
                "severity": "critical",
            }
        ]
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.85,
            "validation_confidence": 0.90,
            "discrepancies": discrepancies,
            "support_category": "unknown_parentage",
        })

        assert result["decision"] == "manual_review"
        assert result["critical_discrepancies"] == 1

    def test_borderline_score_manual_review(self):
        """borderline score (0.40-0.60) -> manual_review."""
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.50,
            "validation_confidence": 0.90,
            "discrepancies": [],
            "support_category": "divorced",
        })

        assert result["decision"] == "manual_review"
        assert "0.40-0.60" in result["reasoning"]

    def test_resolved_discrepancy_not_critical(self):
        """Resolved discrepancies should not trigger manual_review."""
        discrepancies = [
            {
                "discrepancy_type": "identity_match",
                "resolution_status": "resolved",
                "severity": "critical",
            }
        ]
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.75,
            "validation_confidence": 0.90,
            "discrepancies": discrepancies,
            "support_category": "divorced",
        })

        assert result["decision"] == "approved"
        assert result["critical_discrepancies"] == 0

    def test_non_critical_discrepancy_ignored(self):
        """Non-critical discrepancy types should not trigger manual_review."""
        discrepancies = [
            {
                "discrepancy_type": "address_mismatch",
                "resolution_status": "unresolved",
                "severity": "low",
            }
        ]
        result = decision_logic_tool.invoke({
            "eligibility_score": 0.75,
            "validation_confidence": 0.90,
            "discrepancies": discrepancies,
            "support_category": "divorced",
        })

        assert result["decision"] == "approved"
        assert result["critical_discrepancies"] == 0


class TestDecisionExplanationTool:
    """Test decision_explanation_tool for each decision type."""

    def test_explanation_approved(self):
        """Generate explanation for approved decision."""
        result = decision_explanation_tool.invoke({
            "decision": "approved",
            "eligibility_score": 0.78,
            "validation_confidence": 0.92,
            "applicant_context": {
                "support_category": "divorced",
                "family_size": 3,
            },
        })

        assert "approved" in result["explanation"].lower()
        assert "0.78" in result["explanation"]
        assert result["support_category"] == "divorced"
        assert len(result["key_factors"]) == 3
        assert "0.78" in result["key_factors"][0]

    def test_explanation_soft_decline(self):
        """Generate explanation for soft_decline decision."""
        result = decision_explanation_tool.invoke({
            "decision": "soft_decline",
            "eligibility_score": 0.30,
            "validation_confidence": 0.85,
            "applicant_context": {
                "support_category": "abandoned",
                "family_size": 1,
            },
        })

        assert "cannot be approved" in result["explanation"].lower()
        assert "0.30" in result["explanation"]
        assert result["support_category"] == "abandoned"
        assert len(result["key_factors"]) == 2

    def test_explanation_manual_review(self):
        """Generate explanation for manual_review decision."""
        result = decision_explanation_tool.invoke({
            "decision": "manual_review",
            "eligibility_score": 0.55,
            "validation_confidence": 0.75,
            "applicant_context": {
                "support_category": "unknown_parentage",
                "family_size": 4,
            },
        })

        assert "additional review" in result["explanation"].lower()
        assert "0.55" in result["explanation"]
        assert result["support_category"] == "unknown_parentage"
        assert len(result["key_factors"]) == 3

    def test_explanation_default_context(self):
        """Explanation works with minimal applicant context."""
        result = decision_explanation_tool.invoke({
            "decision": "approved",
            "eligibility_score": 0.80,
            "validation_confidence": 0.95,
            "applicant_context": {},
        })

        assert result["support_category"] == "general"
        assert "household of 1" in result["explanation"]


class TestEnablementRecommendationTool:
    """Test enablement_recommendation_tool per applicant context."""

    def test_unemployed_approved_gets_job_matching(self):
        """Unemployed approved applicant -> job_matching recommendation."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "unemployed",
                "has_dependents": False,
                "credit_score": 750,
            },
            "eligibility_score": 0.70,
            "decision": "approved",
        })

        types = [r["type"] for r in result["recommendations"]]
        assert "job_matching" in types
        assert "upskilling" in types

    def test_low_credit_score_gets_financial_literacy(self):
        """Approved applicant with credit_score < 650 -> financial_literacy."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "employed",
                "has_dependents": False,
                "credit_score": 600,
            },
            "eligibility_score": 0.65,
            "decision": "approved",
        })

        types = [r["type"] for r in result["recommendations"]]
        assert "financial_literacy" in types

    def test_dependents_get_childcare_support(self):
        """Approved applicant with dependents -> childcare_support."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "employed",
                "has_dependents": True,
                "credit_score": 700,
            },
            "eligibility_score": 0.70,
            "decision": "approved",
        })

        types = [r["type"] for r in result["recommendations"]]
        assert "childcare_support" in types

    def test_manual_review_recommendations(self):
        """manual_review decision -> documentation_assistance + caseworker_consultation."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "unknown",
                "has_dependents": False,
                "credit_score": 0,
            },
            "eligibility_score": 0.50,
            "decision": "manual_review",
        })

        types = [r["type"] for r in result["recommendations"]]
        assert "documentation_assistance" in types
        assert "caseworker_consultation" in types
        assert result["total_count"] == 2

    def test_soft_decline_recommendations(self):
        """soft_decline decision -> financial_counseling + reapplication_guidance."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {
                "employment_status": "unemployed",
                "has_dependents": False,
                "credit_score": 500,
            },
            "eligibility_score": 0.25,
            "decision": "soft_decline",
        })

        types = [r["type"] for r in result["recommendations"]]
        assert "financial_counseling" in types
        assert "reapplication_guidance" in types

    def test_default_context_values(self):
        """Tool works with default context values."""
        result = enablement_recommendation_tool.invoke({
            "applicant_context": {},
            "eligibility_score": 0.70,
            "decision": "approved",
        })

        assert result["total_count"] >= 1
        assert "upskilling" in [r["type"] for r in result["recommendations"]]


class TestDecisionFormattingTool:
    """Test decision_formatting_tool for each decision type."""

    def test_approved_green_card(self):
        """approved -> green card, check_circle icon."""
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Eligibility score meets threshold.",
            "enablement_recommendations": None,
            "applicant_context": {},
        })

        assert result["color"] == "green"
        assert result["icon"] == "check_circle"
        assert result["title"] == "Application Approved"
        assert result["decision"] == "approved"
        assert len(result["next_steps"]) == 3

    def test_soft_decline_red_card(self):
        """soft_decline -> red card, cancel icon."""
        result = decision_formatting_tool.invoke({
            "decision": "soft_decline",
            "explanation": "Score below threshold.",
            "enablement_recommendations": None,
            "applicant_context": {},
        })

        assert result["color"] == "red"
        assert result["icon"] == "cancel"
        assert result["title"] == "Application Not Approved"
        assert len(result["next_steps"]) == 3

    def test_manual_review_orange_card(self):
        """manual_review -> orange card, pending icon."""
        result = decision_formatting_tool.invoke({
            "decision": "manual_review",
            "explanation": "Requires additional verification.",
            "enablement_recommendations": None,
            "applicant_context": {},
        })

        assert result["color"] == "orange"
        assert result["icon"] == "pending"
        assert result["title"] == "Application Under Review"
        assert len(result["next_steps"]) == 3

    def test_enablement_section_with_recommendations(self):
        """enablement_section populated when recommendations provided."""
        recommendations = {
            "recommendations": [
                {"type": "job_matching", "title": "Job Matching"},
            ],
        }
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Eligible.",
            "enablement_recommendations": recommendations,
            "applicant_context": {},
        })

        assert result["enablement_section"] is not None
        assert result["enablement_section"]["title"] == "Recommended Support Programs"
        assert len(result["enablement_section"]["items"]) == 1

    def test_no_enablement_section_without_recommendations(self):
        """enablement_section is None when no recommendations."""
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Eligible.",
            "enablement_recommendations": None,
            "applicant_context": {},
        })

        assert result["enablement_section"] is None

    def test_empty_recommendations_dict(self):
        """Empty recommendations dict -> no enablement_section."""
        result = decision_formatting_tool.invoke({
            "decision": "approved",
            "explanation": "Eligible.",
            "enablement_recommendations": {"recommendations": []},
            "applicant_context": {},
        })

        assert result["enablement_section"] is None


class TestRouting:
    """Test should_use_react routing logic."""

    def test_react_when_both_present(self, sample_state):
        """eligibility_score and validation_results present -> react."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
            "validation_results": {"overall_confidence": 0.90},
        }
        assert should_use_react(state) == "react"

    def test_deterministic_when_no_eligibility_score(self, sample_state):
        """eligibility_score missing -> deterministic."""
        state = {
            **sample_state,
            "eligibility_score": None,
            "validation_results": {"overall_confidence": 0.90},
        }
        assert should_use_react(state) == "deterministic"

    def test_deterministic_when_no_validation_results(self, sample_state):
        """validation_results missing -> deterministic."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
            "validation_results": {},
        }
        assert should_use_react(state) == "deterministic"

    def test_deterministic_when_both_missing(self, sample_state):
        """Both missing -> deterministic."""
        state = {
            **sample_state,
            "eligibility_score": None,
            "validation_results": {},
        }
        assert should_use_react(state) == "deterministic"

    def test_react_with_zero_score(self, sample_state):
        """eligibility_score=0.0 is not None -> react."""
        state = {
            **sample_state,
            "eligibility_score": 0.0,
            "validation_results": {"overall_confidence": 0.85},
        }
        assert should_use_react(state) == "react"


class TestDecisionReactNode:
    """Test decision_react_node with mocked LLM."""

    @pytest.mark.asyncio
    async def test_react_node_parses_json_output(self, sample_state):
        """ReAct agent JSON output is parsed correctly."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
            "validation_results": {"overall_confidence": 0.92},
        }

        final_msg = MagicMock()
        final_msg.content = json.dumps({
            "decision": "approved",
            "explanation": "Strong eligibility score.",
        })

        mock_result = {"messages": [MagicMock(), final_msg]}

        with patch("src.agents.decision.nodes._get_llm"), \
             patch("src.agents.decision.nodes.create_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.ainvoke = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_agent

            result = await decision_react_node(state)

        assert result["decision"] == "approved"
        assert result["decision_explanation"] == "Strong eligibility score."

    @pytest.mark.asyncio
    async def test_react_node_fallback_on_invalid_json(self, sample_state):
        """Invalid JSON from agent -> manual_review with raw output as explanation."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
            "validation_results": {"overall_confidence": 0.92},
        }

        final_msg = MagicMock()
        final_msg.content = "This is not valid JSON at all"

        mock_result = {"messages": [final_msg]}

        with patch("src.agents.decision.nodes._get_llm"), \
             patch("src.agents.decision.nodes.create_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.ainvoke = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_agent

            result = await decision_react_node(state)

        assert result["decision"] == "manual_review"
        assert result["decision_explanation"] == "This is not valid JSON at all"

    @pytest.mark.asyncio
    async def test_react_node_handles_empty_messages(self, sample_state):
        """Empty messages list -> empty string parse attempt."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
        }

        mock_result = {"messages": []}

        with patch("src.agents.decision.nodes.create_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.ainvoke = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_agent

            result = await decision_react_node(state)

        assert result["decision"] == "manual_review"

    @pytest.mark.asyncio
    async def test_react_node_fallback_on_exception(self, sample_state):
        """LLM exception -> fallback to manual_review with explanation."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
        }

        with patch("src.agents.decision.nodes._get_llm") as mock_get_llm:
            mock_get_llm.side_effect = RuntimeError("LLM unavailable")

            result = await decision_react_node(state)

        assert result["decision"] == "manual_review"
        assert "Escalated to manual review" in result["decision_explanation"]


class TestSynthesizeDecisionNode:
    """Test deterministic decision synthesis in synthesize_decision_node."""

    @pytest.mark.asyncio
    async def test_approved_high_score_high_confidence(self, sample_state):
        """score > 0.60, confidence >= 0.80, no critical discrepancies -> approved."""
        state = {
            **sample_state,
            "eligibility_score": 0.75,
            "validation_results": {"overall_confidence": 0.90},
            "discrepancies": [],
        }

        result = await synthesize_decision_node(state)

        assert result["decision"] == "approved"
        assert "0.75" in result["decision_explanation"]
        assert "0.90" in result["decision_explanation"]

    @pytest.mark.asyncio
    async def test_soft_decline_low_score(self, sample_state):
        """score < 0.40 -> soft_decline."""
        state = {
            **sample_state,
            "eligibility_score": 0.25,
            "validation_results": {"overall_confidence": 0.95},
            "discrepancies": [],
        }

        result = await synthesize_decision_node(state)

        assert result["decision"] == "soft_decline"
        assert "0.25" in result["decision_explanation"]

    @pytest.mark.asyncio
    async def test_manual_review_low_confidence(self, sample_state):
        """confidence < 0.80 -> manual_review."""
        state = {
            **sample_state,
            "eligibility_score": 0.70,
            "validation_results": {"overall_confidence": 0.65},
            "discrepancies": [],
        }

        result = await synthesize_decision_node(state)

        assert result["decision"] == "manual_review"

    @pytest.mark.asyncio
    async def test_manual_review_critical_discrepancy(self, sample_state):
        """Unresolved critical discrepancy -> manual_review regardless of score."""
        state = {
            **sample_state,
            "eligibility_score": 0.85,
            "validation_results": {"overall_confidence": 0.95},
            "discrepancies": [
                {
                    "discrepancy_type": "identity_match",
                    "resolution_status": "unresolved",
                },
            ],
        }

        result = await synthesize_decision_node(state)

        assert result["decision"] == "manual_review"
        assert "critical discrepancies" in result["decision_explanation"]

    @pytest.mark.asyncio
    async def test_borderline_score_manual_review(self, sample_state):
        """score 0.40-0.60 -> manual_review."""
        state = {
            **sample_state,
            "eligibility_score": 0.50,
            "validation_results": {"overall_confidence": 0.90},
            "discrepancies": [],
        }

        result = await synthesize_decision_node(state)

        assert result["decision"] == "manual_review"
        assert "0.40-0.60" in result["decision_explanation"]

    @pytest.mark.asyncio
    async def test_default_values_when_missing(self):
        """Node handles missing state fields gracefully."""
        state = {
            "messages": [],
            "current_phase": "processing",
            "applicant_id": "test-001",
            "application_id": "test-001",
        }

        result = await synthesize_decision_node(state)

        # Default score 0.0, default confidence 0.0 -> confidence < 0.80 -> manual_review
        assert result["decision"] == "manual_review"
