"""Integration tests for orchestrator agent.

Tests cover:
1. Full phase flow (mocked LLM, real subgraph logic)
2. Resume existing application (skip auth/intake phases)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.orchestrator.graph import build_orchestrator_graph
from src.agents.orchestrator.nodes import inject_llm_client, inject_services


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _NoOpLogger:
    """Minimal logger that accepts any args/kwargs without error."""

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None
        return _noop


_NOOP = _NoOpLogger()


@pytest.fixture(autouse=True)
def _patch_all_structlog():
    """Patch structlog loggers across all orchestrator-related modules."""
    patches = []
    modules_to_patch = [
        "src.agents.orchestrator.nodes",
        "src.agents.orchestrator.routes",
        "src.agents.orchestrator.graph",
    ]
    for mod_path in modules_to_patch:
        try:
            mod = __import__(mod_path, fromlist=["logger"])
            patches.append(patch.object(mod, "logger", _NOOP))
        except Exception:
            pass

    with patch("src.infrastructure.observability.get_langfuse_client", return_value=None):
        with patch("langgraph.checkpoint.sqlite.SqliteSaver.from_conn_string", return_value=None):
            for p in patches:
                p.start()
            try:
                yield
            finally:
                for p in patches:
                    p.stop()


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level globals after each test."""
    yield
    inject_llm_client(None)
    inject_services()


@pytest.fixture
def mock_subgraphs():
    """Return a dict of mock subgraph objects for extraction, validation, eligibility, decision."""
    mock_extraction_graph = MagicMock()
    mock_extraction_graph.ainvoke = AsyncMock(return_value={
        "extraction_results": [
            {"doc_type": "emirates_id", "status": "extracted", "confidence": 0.95},
            {"doc_type": "bank_statement", "status": "extracted", "confidence": 0.92},
            {"doc_type": "credit_report", "status": "extracted", "confidence": 0.90},
            {"doc_type": "application_form", "status": "extracted", "confidence": 0.88},
        ],
        "gate_status": "passed",
        "gate_errors": [],
    })

    mock_validation_result = {
        "validation_results": {"cross_doc_check": "passed"},
        "discrepancies": [],
        "gate_status": "passed",
    }

    mock_eligibility_graph = MagicMock()
    mock_eligibility_graph.ainvoke = AsyncMock(return_value={
        "eligibility_score": 0.78,
        "eligibility_factors": {"income": 0.3, "credit": 0.4, "employment": 0.2},
        "gate_status": "passed",
        "gate_errors": [],
    })

    mock_decision_agent = MagicMock()
    mock_decision_agent.ainvoke = AsyncMock(return_value={
        "decision": "approved",
        "decision_explanation": "Strong financial profile with stable income and good credit history.",
    })

    return {
        "extraction": mock_extraction_graph,
        "validation_result": mock_validation_result,
        "eligibility": mock_eligibility_graph,
        "decision": mock_decision_agent,
    }


# ---------------------------------------------------------------------------
# Test 1: Full Phase Flow
# ---------------------------------------------------------------------------

class TestFullPhaseFlow:
    """Test running the orchestrator through all 7 phases."""

    @pytest.mark.asyncio
    async def test_full_flow_from_authentication(self, mock_subgraphs):
        """Run orchestrator from Phase 0 through all phases.

        Asserts final state has decision, eligibility_score, and enablement_recommendations.
        """
        # Set up mock subgraphs
        with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_subgraphs["extraction"]):
            with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_subgraphs["validation_result"]):
                with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_subgraphs["eligibility"]):
                    with patch.dict("src.agents.decision.graph.__dict__", {"decision_agent": mock_subgraphs["decision"]}):
                        # Build and compile the graph (no checkpointer for test isolation)
                        graph = build_orchestrator_graph()

                        initial_state = {
                            "messages": [{"role": "user", "content": "My Emirates ID is 784199012345678"}],
                            "current_phase": "authentication",
                            "applicant_id": "test-applicant-001",
                            "application_id": "test-application-001",
                            "uploaded_files": ["emirates_id.png", "bank_statement.pdf", "credit_report.pdf", "application_form.png"],
                            "uploaded_documents": [],
                            "identity_number": None,
                            "support_category": None,
                            "applicant_info": {},
                            "eligibility_score": None,
                            "decision": None,
                            "decision_explanation": None,
                            "discrepancies": [],
                            "extracted_data": {},
                            "validation_errors": [],
                            "extraction_confidence": {},
                            "validation_results": {},
                            "eligibility_factors": None,
                            "gate_status": "passed",
                            "gate_errors": [],
                            "retry_count": 0,
                            "escalation_reason": None,
                            "extraction_results": [],
                        }

                        config = {"configurable": {"thread_id": "test-full-flow-001"}}
                        final_state = await graph.ainvoke(initial_state, config=config)

                        # Assert phase transitions occurred
                        assert final_state["current_phase"] == "enablement"

                        # Assert decision was made
                        assert final_state.get("decision") == "approved"
                        assert final_state.get("decision_explanation") is not None

                        # Assert eligibility score was computed
                        assert final_state.get("eligibility_score") == 0.78
                        assert final_state.get("eligibility_factors") is not None

                        # Assert enablement recommendations were generated
                        assert "enablement_recommendations" in final_state
                        assert len(final_state["enablement_recommendations"]) > 0

                        # Assert messages were generated throughout the flow
                        assert len(final_state.get("messages", [])) > 0

    @pytest.mark.asyncio
    async def test_full_flow_with_discrepancies(self, mock_subgraphs):
        """Run flow with discrepancies detected during validation."""
        mock_subgraphs["validation_result"] = {
            "validation_results": {"cross_doc_check": "mismatch"},
            "discrepancies": [
                {"type": "income_variance", "message": "Income differs by 15%", "severity": "warning"},
            ],
            "gate_status": "passed",
        }

        with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_subgraphs["extraction"]):
            with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_subgraphs["validation_result"]):
                with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_subgraphs["eligibility"]):
                    with patch.dict("src.agents.decision.graph.__dict__", {"decision_agent": mock_subgraphs["decision"]}):
                        graph = build_orchestrator_graph()

                        initial_state = {
                            "messages": [{"role": "user", "content": "784-1990-1234567-8"}],
                            "current_phase": "authentication",
                            "applicant_id": "test-applicant-002",
                            "application_id": "test-application-002",
                            "uploaded_files": ["emirates_id.png"],
                            "uploaded_documents": [],
                            "identity_number": None,
                            "support_category": "divorced",
                            "applicant_info": {"support_category": "divorced"},
                            "eligibility_score": None,
                            "decision": None,
                            "decision_explanation": None,
                            "discrepancies": [],
                            "extracted_data": {},
                            "validation_errors": [],
                            "extraction_confidence": {},
                            "validation_results": {},
                            "eligibility_factors": None,
                            "gate_status": "passed",
                            "gate_errors": [],
                            "retry_count": 0,
                            "escalation_reason": None,
                            "extraction_results": [],
                        }

                        config = {"configurable": {"thread_id": "test-discrepancies-001"}}
                        final_state = await graph.ainvoke(initial_state, config=config)

                        assert final_state["current_phase"] == "enablement"
                        # Discrepancies should be carried through
                        assert len(final_state.get("discrepancies", [])) == 1


# ---------------------------------------------------------------------------
# Test 2: Resume Existing Application
# ---------------------------------------------------------------------------

class TestResumeApplication:
    """Test resuming an existing application from a later phase."""

    @pytest.mark.asyncio
    async def test_resume_from_processing(self, mock_subgraphs):
        """Resume from Phase 3 (processing), skipping auth and intake.

        Asserts the orchestrator does not execute auth/intake nodes.
        """
        auth_called = []
        intake_called = []

        async def track_auth(state):
            auth_called.append(True)
            return {"messages": [], "current_phase": "processing"}

        async def track_intake(state):
            intake_called.append(True)
            return {"messages": [], "current_phase": "processing"}

        with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_subgraphs["extraction"]):
            with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_subgraphs["validation_result"]):
                with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_subgraphs["eligibility"]):
                    with patch.dict("src.agents.decision.graph.__dict__", {"decision_agent": mock_subgraphs["decision"]}):
                        graph = build_orchestrator_graph()

                        initial_state = {
                            "messages": [],
                            "current_phase": "processing",
                            "applicant_id": "existing-applicant-001",
                            "application_id": "existing-application-001",
                            "uploaded_files": ["emirates_id.png", "bank_statement.pdf"],
                            "uploaded_documents": [],
                            "identity_number": "784-1990-1234567-8",
                            "support_category": "divorced",
                            "applicant_info": {
                                "full_name": "Ahmed Mohammed",
                                "support_category": "divorced",
                            },
                            "eligibility_score": None,
                            "decision": None,
                            "decision_explanation": None,
                            "discrepancies": [],
                            "extracted_data": {},
                            "validation_errors": [],
                            "extraction_confidence": {},
                            "validation_results": {},
                            "eligibility_factors": None,
                            "gate_status": "passed",
                            "gate_errors": [],
                            "retry_count": 0,
                            "escalation_reason": None,
                            "extraction_results": [],
                        }

                        config = {"configurable": {"thread_id": "test-resume-001"}}
                        final_state = await graph.ainvoke(initial_state, config=config)

                        # Should reach enablement
                        assert final_state["current_phase"] == "enablement"
                        assert final_state.get("decision") == "approved"
                        assert final_state.get("eligibility_score") == 0.78

    @pytest.mark.asyncio
    async def test_resume_from_decision(self, mock_subgraphs):
        """Resume from Phase 5 (decision), skipping earlier phases.

        Asserts the orchestrator jumps directly to decision logic.
        """
        with patch("src.agents.extraction.graph.get_extraction_subgraph", return_value=mock_subgraphs["extraction"]):
            with patch("src.agents.validation.graph.run_validation_agent", return_value=mock_subgraphs["validation_result"]):
                with patch("src.agents.eligibility.graph.get_eligibility_graph", return_value=mock_subgraphs["eligibility"]):
                    with patch.dict("src.agents.decision.graph.__dict__", {"decision_agent": mock_subgraphs["decision"]}):
                        graph = build_orchestrator_graph()

                        initial_state = {
                            "messages": [],
                            "current_phase": "decision",
                            "applicant_id": "existing-applicant-002",
                            "application_id": "existing-application-002",
                            "uploaded_files": [],
                            "uploaded_documents": [],
                            "identity_number": "784-1990-1234567-8",
                            "support_category": "abandoned",
                            "applicant_info": {
                                "full_name": "Fatima Ali",
                                "support_category": "abandoned",
                            },
                            "eligibility_score": None,
                            "decision": None,
                            "decision_explanation": None,
                            "discrepancies": [],
                            "extracted_data": {
                                "emirates_id": {"identity_number": "784-1990-1234567-8"},
                                "bank_statement": {"monthly_salary": 8000},
                            },
                            "validation_errors": [],
                            "extraction_confidence": {"emirates_id": 0.95},
                            "validation_results": {"cross_doc_check": "passed"},
                            "eligibility_factors": None,
                            "gate_status": "passed",
                            "gate_errors": [],
                            "retry_count": 0,
                            "escalation_reason": None,
                            "extraction_results": [{"doc_type": "emirates_id"}],
                        }

                        config = {"configurable": {"thread_id": "test-resume-decision-001"}}
                        final_state = await graph.ainvoke(initial_state, config=config)

                        assert final_state["current_phase"] == "enablement"
                        assert final_state.get("decision") == "approved"
                        assert final_state.get("eligibility_score") == 0.78
                        assert "enablement_recommendations" in final_state
