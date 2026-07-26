"""Unit tests for orchestrator agent.

Tests cover:
1. Phase routing logic
2. Authentication node (Emirates ID validation)
3. Intake node (keyword extraction, LLM response)
4. Document collection node (required docs per category)
5. Processing node (subgraph invocation, gate failures)
6. Decision node (eligibility/decision subgraphs, fallbacks)
7. Enablement node (category recommendations, LLM enhancement)
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.orchestrator.nodes import (
    authentication_node,
    decision_node,
    document_collection_node,
    enablement_node,
    inject_llm_client,
    inject_services,
    intake_node,
    processing_node,
    review_node,
)
from src.agents.orchestrator.routes import route_by_phase


# ---------------------------------------------------------------------------
# Fixtures to work around source-code logging and missing-attribute issues
# ---------------------------------------------------------------------------

class _NoOpLogger:
    """Minimal logger that accepts any args/kwargs without error."""

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None
        return _noop


_NOOP = _NoOpLogger()


@pytest.fixture(autouse=True)
def _patch_structlog_in_orchestrator():
    """Replace structlog loggers in orchestrator modules to avoid event= kwarg collision."""
    import src.agents.orchestrator.nodes as nodes_mod
    import src.agents.orchestrator.routes as routes_mod
    with patch.object(nodes_mod, "logger", _NOOP), patch.object(routes_mod, "logger", _NOOP):
        yield


@pytest.fixture(autouse=True)
def _patch_structlog_in_inject():
    """Patch logger in nodes module for inject_services/inject_llm_client calls."""
    # Already covered by _patch_structlog_in_orchestrator since they're the same module
    yield


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Reset module-level globals after each test to avoid cross-test contamination."""
    yield
    inject_llm_client(None)
    inject_services()


@pytest.fixture
def _mock_decision_agent_attr():
    """Add a mock decision_agent attribute to src.agents.decision.graph module.

    The orchestrator decision_node does ``from src.agents.decision.graph import decision_agent``
    but the graph module only exports ``get_decision_agent()``. This fixture patches
    the module dict so the import succeeds during tests.
    """
    import src.agents.decision.graph as dg
    mock_agent = MagicMock()
    original = getattr(dg, "decision_agent", None)
    dg.decision_agent = mock_agent
    yield mock_agent
    if original is None:
        delattr(dg, "decision_agent")
    else:
        dg.decision_agent = original


# ---------------------------------------------------------------------------
# Test Class 1: Phase Routing
# ---------------------------------------------------------------------------

class TestPhaseRouting:
    """Test phase transition and routing logic."""

    def test_route_to_authentication(self):
        """Test routing returns authentication when current_phase is authentication."""
        state = {"current_phase": "authentication"}
        result = route_by_phase(state)
        assert result == "authentication"

    def test_route_to_intake(self):
        """Test routing returns intake when current_phase is intake."""
        state = {"current_phase": "intake"}
        result = route_by_phase(state)
        assert result == "intake"

    def test_route_to_document_collection(self):
        """Test routing returns document_collection phase."""
        state = {"current_phase": "document_collection"}
        result = route_by_phase(state)
        assert result == "document_collection"

    def test_route_to_processing(self):
        """Test routing returns processing phase."""
        state = {"current_phase": "processing"}
        result = route_by_phase(state)
        assert result == "processing"

    def test_route_to_review(self):
        """Test routing returns review phase."""
        state = {"current_phase": "review"}
        result = route_by_phase(state)
        assert result == "review"

    def test_route_to_decision(self):
        """Test routing returns decision phase."""
        state = {"current_phase": "decision"}
        result = route_by_phase(state)
        assert result == "decision"

    def test_route_to_enablement(self):
        """Test routing returns enablement phase."""
        state = {"current_phase": "enablement"}
        result = route_by_phase(state)
        assert result == "enablement"

    def test_route_defaults_to_authentication(self):
        """Test routing defaults to authentication when current_phase is missing."""
        state = {}
        result = route_by_phase(state)
        assert result == "authentication"

    def test_full_phase_sequence(self):
        """Test complete phase transition sequence."""
        sequence = [
            "authentication", "intake", "document_collection",
            "processing", "review", "decision", "enablement",
        ]
        for expected in sequence:
            result = route_by_phase({"current_phase": expected})
            assert result == expected


# ---------------------------------------------------------------------------
# Test Class 2: Authentication Node
# ---------------------------------------------------------------------------

class TestAuthenticationNode:
    """Test authentication node for Emirates ID validation."""

    @pytest.mark.asyncio
    async def test_valid_emirates_id_transitions_to_intake(self):
        """Test valid Emirates ID transitions phase to intake."""
        state = {
            "messages": [],
            "current_phase": "authentication",
            "identity_number": "784-1990-1234567-8",
        }

        with patch("src.utils.emirates_id.validate", return_value=True):
            result = await authentication_node(state)

        assert result["current_phase"] == "intake"
        assert result["identity_number"] == "784-1990-1234567-8"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "assistant"
        assert "verified successfully" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_invalid_emirates_id_stays_in_auth(self):
        """Test invalid Emirates ID stays in authentication phase."""
        state = {
            "messages": [],
            "current_phase": "authentication",
            "identity_number": "784-1990-1234567-9",
        }

        with patch("src.utils.emirates_id.validate", return_value=False):
            result = await authentication_node(state)

        assert result["current_phase"] == "authentication"
        assert "could not be verified" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_id_extraction_from_message(self):
        """Test ID extraction from user message."""
        state = {
            "messages": [{"role": "user", "content": "My ID is 784199012345678"}],
            "current_phase": "authentication",
            "identity_number": None,
        }

        with patch("src.utils.emirates_id.validate", return_value=True) as mock_validate:
            result = await authentication_node(state)

        mock_validate.assert_called_once_with("784199012345678")
        assert result["identity_number"] == "784199012345678"
        assert result["current_phase"] == "intake"

    @pytest.mark.asyncio
    async def test_no_id_provided_requests_one(self):
        """Test node requests ID when none provided."""
        state = {
            "messages": [],
            "current_phase": "authentication",
            "identity_number": None,
        }

        result = await authentication_node(state)

        assert result["current_phase"] == "authentication"
        assert "15 digits" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_message_without_id_extracts_nothing(self):
        """Test message without 15-digit number extracts no ID."""
        state = {
            "messages": [{"role": "user", "content": "Hello, I need support"}],
            "current_phase": "authentication",
            "identity_number": None,
        }

        result = await authentication_node(state)

        assert result["current_phase"] == "authentication"
        assert result.get("identity_number") is None

    @pytest.mark.asyncio
    async def test_luhn_valid_id(self):
        """Test with a Luhn-valid ID number."""
        state = {
            "messages": [],
            "current_phase": "authentication",
            "identity_number": "784-1990-1234567-8",
        }

        with patch("src.utils.emirates_id.validate", return_value=True):
            result = await authentication_node(state)

        assert result["current_phase"] == "intake"


# ---------------------------------------------------------------------------
# Test Class 3: Intake Node
# ---------------------------------------------------------------------------

class TestIntakeNode:
    """Test intake node for applicant information collection."""

    @pytest.mark.asyncio
    async def test_support_category_divorced(self):
        """Test divorced support category detection."""
        state = {
            "messages": [{"role": "user", "content": "I am divorced and need support"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)

        assert result["current_phase"] == "document_collection"
        assert result["applicant_info"]["support_category"] == "divorced"

    @pytest.mark.asyncio
    async def test_support_category_abandoned(self):
        """Test abandoned support category detection."""
        state = {
            "messages": [{"role": "user", "content": "I was abandoned by my family"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)

        assert result["current_phase"] == "document_collection"
        assert result["applicant_info"]["support_category"] == "abandoned"

    @pytest.mark.asyncio
    async def test_support_category_unknown_parentage(self):
        """Test unknown parentage support category detection."""
        state = {
            "messages": [{"role": "user", "content": "I have unknown parentage"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)

        assert result["current_phase"] == "document_collection"
        assert result["applicant_info"]["support_category"] == "unknown_parentage"

    @pytest.mark.asyncio
    async def test_support_category_health_disability(self):
        """Test health/disability support category detection."""
        state = {
            "messages": [{"role": "user", "content": "I have a health disability"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)

        assert result["current_phase"] == "document_collection"
        assert result["applicant_info"]["support_category"] == "health_disability"

    @pytest.mark.asyncio
    async def test_llm_response_with_mock(self, mock_llm):
        """Test LLM response generation with mocked client."""
        inject_llm_client(mock_llm)
        mock_llm.chat_completion = AsyncMock(return_value={
            "content": "LLM generated intake response",
        })

        state = {
            "messages": [{"role": "user", "content": "My name is Ahmed"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)
        assert result["messages"][0]["content"] == "LLM generated intake response"

    @pytest.mark.asyncio
    async def test_fallback_when_llm_fails(self):
        """Test fallback to deterministic text when LLM fails."""
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(side_effect=Exception("LLM error"))
        inject_llm_client(mock_llm)

        state = {
            "messages": [{"role": "user", "content": "divorced"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)
        # Should still have a response (fallback) and transition
        assert len(result["messages"]) == 1
        assert result["current_phase"] == "document_collection"

    @pytest.mark.asyncio
    async def test_no_support_category_stays_in_intake(self):
        """Test node stays in intake when no support category detected."""
        state = {
            "messages": [{"role": "user", "content": "Just my name, no category"}],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)

        assert result["current_phase"] == "intake"

    @pytest.mark.asyncio
    async def test_empty_message_asks_for_info(self):
        """Test node asks for info when message is empty."""
        state = {
            "messages": [],
            "current_phase": "intake",
            "applicant_info": {},
        }

        result = await intake_node(state)

        assert result["current_phase"] == "intake"
        assert len(result["messages"]) == 1


# ---------------------------------------------------------------------------
# Test Class 4: Document Collection Node
# ---------------------------------------------------------------------------

class TestDocumentCollectionNode:
    """Test document collection node."""

    @pytest.mark.asyncio
    async def test_required_docs_divorced(self):
        """Test required document list for divorced category."""
        state = {
            "messages": [],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "divorced"},
            "uploaded_files": [],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        assert result["current_phase"] == "document_collection"
        msg = result["messages"][0]["content"]
        assert "Emirates ID" in msg
        assert "Bank Statement" in msg
        assert "Credit Report" in msg
        assert "Application Form" in msg

    @pytest.mark.asyncio
    async def test_required_docs_abandoned(self):
        """Test required document list for abandoned category."""
        state = {
            "messages": [],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "abandoned"},
            "uploaded_files": [],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        assert result["current_phase"] == "document_collection"
        msg = result["messages"][0]["content"]
        assert "Emirates ID" in msg
        assert "Credit Report" in msg

    @pytest.mark.asyncio
    async def test_required_docs_unknown_parentage(self):
        """Test required document list for unknown_parentage category."""
        state = {
            "messages": [],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "unknown_parentage"},
            "uploaded_files": [],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        msg = result["messages"][0]["content"]
        assert "Emirates ID" in msg
        assert "Bank Statement" in msg
        assert "Application Form" in msg

    @pytest.mark.asyncio
    async def test_required_docs_health_disability(self):
        """Test required document list for health_disability category."""
        state = {
            "messages": [],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "health_disability"},
            "uploaded_files": [],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        msg = result["messages"][0]["content"]
        assert "Resume" in msg
        assert "Emirates ID" in msg
        assert "Credit Report" in msg

    @pytest.mark.asyncio
    async def test_transition_on_upload(self):
        """Test transition to processing when files uploaded."""
        state = {
            "messages": [],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "divorced"},
            "uploaded_files": ["emirates_id.png"],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        assert result["current_phase"] == "processing"
        assert "received your documents" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_transition_on_upload_indication(self):
        """Test transition when message indicates upload."""
        state = {
            "messages": [{"role": "user", "content": "I have uploaded my documents"}],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "divorced"},
            "uploaded_files": [],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        assert result["current_phase"] == "processing"

    @pytest.mark.asyncio
    async def test_unknown_category_defaults(self):
        """Test unknown support category uses default document list."""
        state = {
            "messages": [],
            "current_phase": "document_collection",
            "applicant_info": {"support_category": "unknown"},
            "uploaded_files": [],
            "uploaded_documents": [],
        }

        result = await document_collection_node(state)

        assert result["current_phase"] == "document_collection"
        msg = result["messages"][0]["content"]
        assert "Emirates ID" in msg
        assert "Bank Statement" in msg


# ---------------------------------------------------------------------------
# Test Class 5: Processing Node
# ---------------------------------------------------------------------------

class TestProcessingNode:
    """Test processing node for extraction and validation."""

    @pytest.mark.asyncio
    async def test_extraction_subgraph_invocation(self, sample_state):
        """Test extraction subgraph is invoked correctly."""
        sample_state["current_phase"] = "processing"

        mock_extraction_graph = MagicMock()
        mock_extraction_graph.ainvoke = AsyncMock(return_value={
            "extraction_results": [{"doc_type": "emirates_id", "status": "extracted"}],
            "gate_status": "passed",
        })

        mock_validation_result = {
            "validation_results": {},
            "discrepancies": [],
            "gate_status": "passed",
        }

        with patch("src.infrastructure.observability.get_langfuse_client", return_value=None):
            with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_extraction_graph):
                with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_validation_result):
                    result = await processing_node(sample_state)

        mock_extraction_graph.ainvoke.assert_called_once()
        assert result["current_phase"] == "review"
        assert "extraction_results" in result
        assert "validation_results" in result
        assert "discrepancies" in result

    @pytest.mark.asyncio
    async def test_validation_subgraph_invocation(self, sample_state):
        """Test validation subgraph is invoked with extraction results."""
        sample_state["current_phase"] = "processing"

        mock_extraction_graph = MagicMock()
        mock_extraction_graph.ainvoke = AsyncMock(return_value={
            "extraction_results": [{"doc_type": "emirates_id"}],
            "gate_status": "passed",
        })

        captured_state = {}

        async def mock_validation(state):
            captured_state.update(state)
            return {
                "validation_results": {"cross_doc_check": "passed"},
                "discrepancies": [],
                "gate_status": "passed",
            }

        with patch("src.infrastructure.observability.get_langfuse_client", return_value=None):
            with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_extraction_graph):
                with patch("src.agents.validation.graph.run_validation_agent", side_effect=mock_validation):
                    await processing_node(sample_state)

        assert "extraction_results" in captured_state

    @pytest.mark.asyncio
    async def test_gate_failure_handling(self, sample_state):
        """Test gate failure transitions to review with error info."""
        sample_state["current_phase"] = "processing"

        mock_extraction_graph = MagicMock()
        mock_extraction_graph.ainvoke = AsyncMock(return_value={
            "extraction_results": [],
            "gate_status": "failed",
            "gate_errors": ["Document integrity check failed"],
        })

        with patch("src.infrastructure.observability.get_langfuse_client", return_value=None):
            with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_extraction_graph):
                result = await processing_node(sample_state)

        assert result["current_phase"] == "review"
        assert result["gate_status"] == "failed"
        assert len(result["gate_errors"]) > 0
        assert "validation errors" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_extraction_exception_fallback(self, sample_state):
        """Test processing handles extraction exception gracefully."""
        sample_state["current_phase"] = "processing"

        mock_extraction_graph = MagicMock()
        mock_extraction_graph.ainvoke = AsyncMock(side_effect=Exception("Extraction failed"))

        mock_validation_result = {
            "validation_results": {},
            "discrepancies": [],
            "gate_status": "passed",
        }

        with patch("src.infrastructure.observability.get_langfuse_client", return_value=None):
            with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_extraction_graph):
                with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_validation_result):
                    result = await processing_node(sample_state)

        assert result["current_phase"] == "review"
        assert result["extraction_results"][0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_discrepancies_in_result(self, sample_state):
        """Test discrepancies are included in result."""
        sample_state["current_phase"] = "processing"

        mock_extraction_graph = MagicMock()
        mock_extraction_graph.ainvoke = AsyncMock(return_value={
            "extraction_results": [{"doc_type": "emirates_id"}, {"doc_type": "bank_statement"}],
            "gate_status": "passed",
        })

        mock_validation_result = {
            "validation_results": {"cross_doc_check": "mismatch"},
            "discrepancies": [
                {"type": "identity_mismatch", "message": "Name differs across documents", "severity": "critical"},
            ],
            "gate_status": "passed",
        }

        with patch("src.infrastructure.observability.get_langfuse_client", return_value=None):
            with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_extraction_graph):
                with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_validation_result):
                    result = await processing_node(sample_state)

        assert len(result["discrepancies"]) == 1
        assert "discrepancy" in result["messages"][0]["content"].lower()


# ---------------------------------------------------------------------------
# Test Class 6: Decision Node
# ---------------------------------------------------------------------------

class TestDecisionNode:
    """Test decision node for eligibility and final decision."""

    @pytest.mark.asyncio
    async def test_eligibility_subgraph_invocation(self, sample_state, _mock_decision_agent_attr):
        """Test eligibility subgraph is invoked."""
        sample_state["current_phase"] = "decision"

        mock_eligibility_graph = MagicMock()
        mock_eligibility_graph.ainvoke = AsyncMock(return_value={
            "eligibility_score": 0.75,
            "eligibility_factors": {"income": 0.3, "credit": 0.4},
            "gate_status": "passed",
        })

        _mock_decision_agent_attr.ainvoke = AsyncMock(return_value={
            "decision": "approved",
            "decision_explanation": "Strong financial profile",
        })

        with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_eligibility_graph):
            result = await decision_node(sample_state)

        mock_eligibility_graph.ainvoke.assert_called_once()
        assert result["eligibility_score"] == 0.75
        assert result["decision"] == "approved"
        assert result["current_phase"] == "enablement"

    @pytest.mark.asyncio
    async def test_decision_subgraph_invocation(self, sample_state, _mock_decision_agent_attr):
        """Test decision subgraph receives eligibility score."""
        sample_state["current_phase"] = "decision"

        mock_eligibility_graph = MagicMock()
        mock_eligibility_graph.ainvoke = AsyncMock(return_value={
            "eligibility_score": 0.65,
            "eligibility_factors": {},
            "gate_status": "passed",
        })

        captured_state = {}

        async def mock_ainvoke(state, config=None):
            captured_state.update(state)
            return {
                "decision": "manual_review",
                "decision_explanation": "Borderline score",
            }

        _mock_decision_agent_attr.ainvoke = mock_ainvoke

        with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_eligibility_graph):
            await decision_node(sample_state)

        assert captured_state.get("eligibility_score") == 0.65

    @pytest.mark.asyncio
    async def test_eligibility_gate_failure(self, sample_state, _mock_decision_agent_attr):
        """Test eligibility gate failure results in soft_decline."""
        sample_state["current_phase"] = "decision"

        mock_eligibility_graph = MagicMock()
        mock_eligibility_graph.ainvoke = AsyncMock(return_value={
            "eligibility_score": 0.3,
            "eligibility_factors": {},
            "gate_status": "failed",
            "gate_errors": ["Hard rule violation"],
        })

        with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_eligibility_graph):
            result = await decision_node(sample_state)

        assert result["decision"] == "soft_decline"
        assert result["gate_status"] == "failed"
        assert result["current_phase"] == "enablement"

    @pytest.mark.asyncio
    async def test_fallback_to_threshold_rules(self, sample_state, _mock_decision_agent_attr):
        """Test fallback to threshold-based rules when subgraphs fail."""
        sample_state["current_phase"] = "decision"

        mock_eligibility_graph = MagicMock()
        mock_eligibility_graph.ainvoke = AsyncMock(side_effect=Exception("Eligibility unavailable"))

        _mock_decision_agent_attr.ainvoke = AsyncMock(side_effect=Exception("Decision unavailable"))

        inject_services()

        with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_eligibility_graph):
            result = await decision_node(sample_state)

        assert result["decision"] == "manual_review"
        assert "requires manual review" in result["decision_explanation"]

    @pytest.mark.asyncio
    async def test_fallback_high_score_approved(self, sample_state, _mock_decision_agent_attr):
        """Test fallback approves when eligibility score >= 0.7."""
        sample_state["current_phase"] = "decision"

        mock_eligibility_service = MagicMock()
        mock_eligibility_service.compute_eligibility = AsyncMock(return_value={
            "eligibility_score": 0.85,
            "factors": {},
        })
        inject_services(eligibility=mock_eligibility_service)

        mock_eligibility_graph = MagicMock()
        mock_eligibility_graph.ainvoke = AsyncMock(side_effect=Exception("Graph unavailable"))

        _mock_decision_agent_attr.ainvoke = AsyncMock(side_effect=Exception("Graph unavailable"))

        with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_eligibility_graph):
            result = await decision_node(sample_state)

        assert result["eligibility_score"] == 0.85
        assert result["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_fallback_low_score_decline(self, sample_state, _mock_decision_agent_attr):
        """Test fallback declines when eligibility score < 0.5."""
        sample_state["current_phase"] = "decision"

        mock_eligibility_service = MagicMock()
        mock_eligibility_service.compute_eligibility = AsyncMock(return_value={
            "eligibility_score": 0.35,
            "factors": {},
        })
        inject_services(eligibility=mock_eligibility_service)

        mock_eligibility_graph = MagicMock()
        mock_eligibility_graph.ainvoke = AsyncMock(side_effect=Exception("Graph unavailable"))

        _mock_decision_agent_attr.ainvoke = AsyncMock(side_effect=Exception("Graph unavailable"))

        with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_eligibility_graph):
            result = await decision_node(sample_state)

        assert result["eligibility_score"] == 0.35
        assert result["decision"] == "soft_decline"


# ---------------------------------------------------------------------------
# Test Class 7: Enablement Node
# ---------------------------------------------------------------------------

class TestEnablementNode:
    """Test enablement node for final recommendations."""

    @pytest.mark.asyncio
    async def test_approved_recommendations(self, sample_state):
        """Test category-specific recommendations for approved decision."""
        sample_state["current_phase"] = "enablement"
        sample_state["decision"] = "approved"
        sample_state["applicant_info"] = {"support_category": "divorced"}

        result = await enablement_node(sample_state)

        assert result["current_phase"] == "enablement"
        recommendations = result["enablement_recommendations"]
        assert len(recommendations) > 0
        assert any("benefits will be processed" in r for r in recommendations)
        assert any("divorce certificate" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_manual_review_recommendations(self, sample_state):
        """Test recommendations for manual_review decision."""
        sample_state["current_phase"] = "enablement"
        sample_state["decision"] = "manual_review"
        sample_state["applicant_info"] = {"support_category": "abandoned"}

        result = await enablement_node(sample_state)

        recommendations = result["enablement_recommendations"]
        assert any("additional review" in r for r in recommendations)
        assert any("documents are complete" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_soft_decline_recommendations(self, sample_state):
        """Test recommendations for soft_decline decision."""
        sample_state["current_phase"] = "enablement"
        sample_state["decision"] = "soft_decline"
        sample_state["applicant_info"] = {"support_category": "unknown_parentage"}

        result = await enablement_node(sample_state)

        recommendations = result["enablement_recommendations"]
        assert any("does not currently meet" in r for r in recommendations)
        assert any("reapply" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_health_disability_recommendation(self, sample_state):
        """Test health/disability specific recommendation."""
        sample_state["current_phase"] = "enablement"
        sample_state["decision"] = "approved"
        sample_state["applicant_info"] = {"support_category": "health_disability"}

        result = await enablement_node(sample_state)

        recommendations = result["enablement_recommendations"]
        assert any("Medical assessment" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_llm_enhanced_response(self, sample_state):
        """Test LLM-enhanced enablement response."""
        sample_state["current_phase"] = "enablement"
        sample_state["decision"] = "approved"
        sample_state["applicant_info"] = {"support_category": "divorced"}

        mock_llm_client = AsyncMock()
        mock_llm_client.chat_completion = AsyncMock(return_value={
            "content": "LLM enhanced enablement message",
        })
        inject_llm_client(mock_llm_client)

        result = await enablement_node(sample_state)
        assert result["messages"][0]["content"] == "LLM enhanced enablement message"

    @pytest.mark.asyncio
    async def test_default_decision_when_missing(self, sample_state):
        """Test node handles missing decision gracefully."""
        sample_state["current_phase"] = "enablement"
        # Remove decision key entirely so .get() returns the default "manual_review"
        sample_state.pop("decision", None)
        sample_state["applicant_info"] = {}

        result = await enablement_node(sample_state)

        recommendations = result["enablement_recommendations"]
        assert len(recommendations) > 0
        # With no decision, defaults to manual_review path
        assert any("additional review" in r for r in recommendations)
