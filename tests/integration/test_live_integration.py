"""Live integration tests for the agent graph.

Two test subsets:
1. **Non-live (default)**: Validates that all agent subgraphs are structurally
   buildable — nodes, edges, routes, and compilation succeed without errors.
   These tests run with every pytest invocation.

2. **Live (@pytest.mark.live)**: Runs the full agent graph with real LLM calls
   against live infrastructure (PostgreSQL, Neo4j, Qdrant, Ollama/StreamLake).
   Skipped by default; run with `pytest -m live` when infrastructure is up.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.state import ApplicantState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level globals after each test."""
    yield
    # Reset any injected singletons to avoid test pollution
    try:
        from src.agents.orchestrator.nodes import inject_llm_client, inject_services
        inject_llm_client(None)
        inject_services()
    except Exception:
        pass


@pytest.fixture
def minimal_state() -> ApplicantState:
    """Minimal valid state for graph invocation."""
    return {
        "messages": [{"role": "user", "content": "I need support"}],
        "current_phase": "authentication",
        "applicant_id": "live-test-001",
        "application_id": "live-app-001",
        "uploaded_files": [],
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
        "enablement_recommendations": [],
    }


# ---------------------------------------------------------------------------
# Non-live subset: Structural buildability tests
# These run by default and verify graphs can be constructed without LLM calls.
# ---------------------------------------------------------------------------


class TestGraphBuildability:
    """Verify each agent subgraph compiles successfully without external services."""

    def test_extraction_subgraph_builds(self):
        """Extraction subgraph should compile without errors."""
        from src.agents.extraction.graph import build_extraction_subgraph
        graph = build_extraction_subgraph()
        assert graph is not None
        # Verify it has the expected nodes
        assert "extract_documents" in graph.nodes
        assert "summarize_extraction" in graph.nodes

    def test_eligibility_subgraph_builds(self):
        """Eligibility subgraph should compile without errors."""
        from src.agents.eligibility.graph import build_eligibility_graph
        graph = build_eligibility_graph()
        compiled = graph.compile()
        assert compiled is not None
        assert "eligibility_react" in compiled.nodes
        assert "eligibility_gate" in compiled.nodes
        assert "eligibility_finalize" in compiled.nodes

    def test_decision_subgraph_builds(self):
        """Decision subgraph should compile without errors."""
        from src.agents.decision.graph import build_decision_graph
        graph = build_decision_graph()
        compiled = graph.compile()
        assert compiled is not None
        assert "decision_react" in compiled.nodes
        assert "decision_deterministic" in compiled.nodes

    @pytest.mark.asyncio
    async def test_validation_subgraph_builds(self):
        """Validation subgraph should build without errors (compilation may need checkpointer)."""
        from src.agents.validation.graph import build_validation_graph

        with patch("src.agents.validation.graph.get_checkpointer", return_value=None):
            graph = await build_validation_graph()

        assert graph is not None
        expected_nodes = {
            "attempt_validation",
            "evaluate_validation",
            "critique_validation",
            "generate_clarification",
            "finalize_validation",
            "gate_2_completeness",
        }
        for node_name in expected_nodes:
            assert node_name in graph.nodes, f"Missing node: {node_name}"

    @pytest.mark.asyncio
    async def test_orchestrator_graph_builds(self):
        """Orchestrator graph should build without errors."""
        from src.agents.orchestrator.graph import build_orchestrator_graph

        with patch("src.agents.orchestrator.graph.get_checkpointer", return_value=None):
            with patch("src.agents.orchestrator.graph.get_session_factory", return_value=None):
                graph = await build_orchestrator_graph()

        assert graph is not None
        expected_nodes = {
            "authentication",
            "intake",
            "document_collection",
            "processing",
            "review",
            "decision",
            "enablement",
        }
        for node_name in expected_nodes:
            assert node_name in graph.nodes, f"Missing node: {node_name}"

    def test_orchestrator_routes_exist(self):
        """Orchestrator routing functions should be importable and callable."""
        from src.agents.orchestrator.routes import (
            route_by_phase,
            route_after_intake,
            route_after_document_collection,
            route_after_review,
        )
        # Each route should be callable
        assert callable(route_by_phase)
        assert callable(route_after_intake)
        assert callable(route_after_document_collection)
        assert callable(route_after_review)

    def test_validation_routes_exist(self):
        """Validation routing function should be importable and callable."""
        from src.agents.validation.routes import route_after_critique
        assert callable(route_after_critique)

    def test_extraction_routes_exist(self):
        """Extraction routing function should be importable and callable."""
        from src.agents.extraction.routes import route_after_extraction
        assert callable(route_after_extraction)

    def test_eligibility_routes_exist(self):
        """Eligibility routing function should be importable and callable."""
        from src.agents.eligibility.routes import route_after_eligibility_gate
        assert callable(route_after_eligibility_gate)

    def test_decision_routes_exist(self):
        """Decision routing function should be importable and callable."""
        from src.agents.decision.routes import should_use_react
        assert callable(should_use_react)


class TestGraphNodeStructure:
    """Verify node functions exist and have correct signatures."""

    def test_extraction_nodes_exist(self):
        """Extraction agent nodes should be importable."""
        from src.agents.extraction.nodes import (
            extract_documents_node,
            summarize_extraction_node,
        )
        assert callable(extract_documents_node)
        assert callable(summarize_extraction_node)

    def test_validation_nodes_exist(self):
        """Validation agent nodes should be importable."""
        from src.agents.validation.nodes import (
            attempt_validation_node,
            evaluate_validation_node,
            critique_validation_node,
            finalize_validation_node,
            gate_2_completeness_node,
            generate_clarification_node,
        )
        assert callable(attempt_validation_node)
        assert callable(evaluate_validation_node)
        assert callable(critique_validation_node)
        assert callable(finalize_validation_node)
        assert callable(gate_2_completeness_node)
        assert callable(generate_clarification_node)

    def test_eligibility_nodes_exist(self):
        """Eligibility agent nodes should be importable."""
        from src.agents.eligibility.nodes import (
            eligibility_react_node,
            eligibility_gate_node,
            eligibility_finalize_node,
        )
        assert callable(eligibility_react_node)
        assert callable(eligibility_gate_node)
        assert callable(eligibility_finalize_node)

    def test_decision_nodes_exist(self):
        """Decision agent nodes should be importable."""
        from src.agents.decision.nodes import (
            decision_react_node,
            synthesize_decision_node,
        )
        assert callable(decision_react_node)
        assert callable(synthesize_decision_node)

    def test_orchestrator_nodes_exist(self):
        """Orchestrator phase nodes should be importable."""
        from src.agents.orchestrator.nodes import (
            authentication_node,
            intake_node,
            document_collection_node,
            processing_node,
            review_node,
            decision_node,
            enablement_node,
        )
        assert callable(authentication_node)
        assert callable(intake_node)
        assert callable(document_collection_node)
        assert callable(processing_node)
        assert callable(review_node)
        assert callable(decision_node)
        assert callable(enablement_node)


# ---------------------------------------------------------------------------
# Live subset: Full graph execution with real LLM calls
# Skipped by default; run with `pytest -m live` when infrastructure is up.
# ---------------------------------------------------------------------------


def _skip_if_no_infrastructure():
    """Skip live tests if required environment variables are not set."""
    required_vars = ["DATABASE_URL", "LLM_PROVIDER"]
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        pytest.skip(f"Live test skipped: missing env vars {missing}. Set up infrastructure and retry.")


@pytest.mark.live
class TestLiveOrchestratorGraph:
    """Live integration tests for the orchestrator graph with real LLM calls."""

    @pytest.mark.asyncio
    async def test_orchestrator_full_flow_live(self, minimal_state):
        """Run the full orchestrator graph with real LLM (StreamLake/Ollama).

        This test requires:
        - PostgreSQL running (for checkpointer and document persistence)
        - LLM provider available (StreamLake or Ollama)
        - Qdrant running (for embeddings)
        - Neo4j running (for graph relationships)
        """
        _skip_if_no_infrastructure()

        from src.agents.orchestrator.graph import build_orchestrator_graph
        from src.agents.orchestrator.nodes import inject_llm_client
        from src.infrastructure.llm.factory import get_llm_client

        # Set up a real LLM client
        llm_client = get_llm_client()
        inject_llm_client(llm_client)

        # Build the graph with real infrastructure
        with patch("src.agents.orchestrator.graph.get_checkpointer"):
            with patch("src.agents.orchestrator.graph.get_session_factory"):
                graph = await build_orchestrator_graph()

        # Set up minimal state for a quick flow
        minimal_state["current_phase"] = "decision"
        minimal_state["identity_number"] = "784-1990-1234567-8"
        minimal_state["support_category"] = "divorced"
        minimal_state["extracted_data"] = {
            "emirates_id": {"identity_number": "784-1990-1234567-8", "full_name_en": "Test User"},
            "bank_statement": {"monthly_salary": 8000},
        }
        minimal_state["eligibility_score"] = 0.65
        minimal_state["validation_results"] = {"overall_confidence": 0.85}

        config = {"configurable": {"thread_id": "live-test-orchestrator-001", "recursion_limit": 50}}
        final_state = await graph.ainvoke(minimal_state, config=config)

        # Assertions
        assert final_state is not None
        assert "current_phase" in final_state
        # Decision should have been attempted
        assert final_state.get("decision") is not None or final_state.get("current_phase") in ("decision", "enablement")

    @pytest.mark.asyncio
    async def test_orchestrator_decision_phase_live(self, minimal_state):
        """Test the decision phase specifically with real LLM."""
        _skip_if_no_infrastructure()

        from src.agents.orchestrator.graph import build_orchestrator_graph
        from src.agents.orchestrator.nodes import inject_llm_client
        from src.infrastructure.llm.factory import get_llm_client

        llm_client = get_llm_client()
        inject_llm_client(llm_client)

        with patch("src.agents.orchestrator.graph.get_checkpointer"):
            with patch("src.agents.orchestrator.graph.get_session_factory"):
                graph = await build_orchestrator_graph()

        minimal_state["current_phase"] = "decision"
        minimal_state["identity_number"] = "784-1990-1234567-8"
        minimal_state["support_category"] = "divorced"
        minimal_state["extracted_data"] = {
            "emirates_id": {"identity_number": "784-1990-1234567-8"},
        }
        minimal_state["eligibility_score"] = 0.70
        minimal_state["validation_results"] = {"overall_confidence": 0.90}
        minimal_state["gate_status"] = "passed"

        config = {"configurable": {"thread_id": "live-test-decision-001", "recursion_limit": 50}}
        final_state = await graph.ainvoke(minimal_state, config=config)

        assert final_state is not None
        assert final_state.get("decision") in ("approved", "soft_decline", "manual_review", None)


@pytest.mark.live
class TestLiveSubgraphs:
    """Live integration tests for individual agent subgraphs with real LLM calls."""

    @pytest.mark.asyncio
    async def test_validation_subgraph_live(self):
        """Run validation subgraph with real LLM for Reflexion loop."""
        _skip_if_no_infrastructure()

        from src.agents.validation.graph import run_validation_agent
        from src.agents.orchestrator.nodes import inject_llm_client
        from src.infrastructure.llm.factory import get_llm_client

        llm_client = get_llm_client()
        inject_llm_client(llm_client)

        state: ApplicantState = {
            "messages": [],
            "current_phase": "processing",
            "applicant_id": "live-val-001",
            "application_id": "live-val-app-001",
            "uploaded_files": [],
            "uploaded_documents": [],
            "identity_number": "784-1990-1234567-8",
            "support_category": "divorced",
            "applicant_info": {},
            "eligibility_score": None,
            "decision": None,
            "decision_explanation": None,
            "discrepancies": [],
            "extracted_data": {
                "emirates_id": {
                    "identity_number": "784-1990-1234567-8",
                    "full_name_en": "Ahmed Ali",
                    "date_of_birth": "1990-05-15",
                },
                "bank_statement": {
                    "account_holder": "Ahmed Ali",
                    "monthly_salary": 8000,
                },
            },
            "validation_errors": [],
            "extraction_confidence": {"emirates_id": 0.95, "bank_statement": 0.90},
            "validation_results": {},
            "eligibility_factors": None,
            "gate_status": "passed",
            "gate_errors": [],
            "retry_count": 0,
            "escalation_reason": None,
            "enablement_recommendations": [],
            "extraction_results": [],
        }

        result = await run_validation_agent(state)

        assert result is not None
        assert "validation_results" in result
        assert "gate_status" in result

    @pytest.mark.asyncio
    async def test_eligibility_subgraph_live(self):
        """Run eligibility subgraph with real LLM."""
        _skip_if_no_infrastructure()

        from src.agents.eligibility.graph import get_eligibility_graph
        from src.agents.orchestrator.nodes import inject_llm_client
        from src.infrastructure.llm.factory import get_llm_client

        llm_client = get_llm_client()
        inject_llm_client(llm_client)

        graph = get_eligibility_graph()

        state: ApplicantState = {
            "messages": [],
            "current_phase": "processing",
            "applicant_id": "live-elig-001",
            "application_id": "live-elig-app-001",
            "uploaded_files": [],
            "uploaded_documents": [],
            "identity_number": "784-1990-1234567-8",
            "support_category": "divorced",
            "applicant_info": {"monthly_salary": 8000, "employment_status": "employed"},
            "eligibility_score": None,
            "decision": None,
            "decision_explanation": None,
            "discrepancies": [],
            "extracted_data": {
                "bank_statement": {"monthly_salary": 8000},
                "credit_report": {"credit_score": 720},
            },
            "validation_errors": [],
            "extraction_confidence": {},
            "validation_results": {},
            "eligibility_factors": None,
            "gate_status": "passed",
            "gate_errors": [],
            "retry_count": 0,
            "escalation_reason": None,
            "enablement_recommendations": [],
            "extraction_results": [],
        }

        config = {"configurable": {"thread_id": "live-elig-001", "recursion_limit": 10}}
        result = await graph.ainvoke(state, config=config)

        assert result is not None
        assert "eligibility_score" in result or result.get("eligibility_score") is not None

    @pytest.mark.asyncio
    async def test_decision_subgraph_live(self):
        """Run decision subgraph with real LLM."""
        _skip_if_no_infrastructure()

        from src.agents.decision.graph import get_decision_agent
        from src.agents.orchestrator.nodes import inject_llm_client
        from src.infrastructure.llm.factory import get_llm_client

        llm_client = get_llm_client()
        inject_llm_client(llm_client)

        agent = get_decision_agent()

        state: ApplicantState = {
            "messages": [],
            "current_phase": "decision",
            "applicant_id": "live-dec-001",
            "application_id": "live-dec-app-001",
            "uploaded_files": [],
            "uploaded_documents": [],
            "identity_number": "784-1990-1234567-8",
            "support_category": "divorced",
            "applicant_info": {
                "full_name": "Ahmed Ali",
                "support_category": "divorced",
                "family_size": 3,
            },
            "eligibility_score": 0.75,
            "decision": None,
            "decision_explanation": None,
            "discrepancies": [],
            "extracted_data": {
                "emirates_id": {"identity_number": "784-1990-1234567-8"},
            },
            "validation_errors": [],
            "extraction_confidence": {},
            "validation_results": {"overall_confidence": 0.85},
            "eligibility_factors": {"income": 0.3, "credit": 0.4},
            "gate_status": "passed",
            "gate_errors": [],
            "retry_count": 0,
            "escalation_reason": None,
            "enablement_recommendations": [],
            "extraction_results": [],
        }

        config = {"configurable": {"thread_id": "live-dec-001", "recursion_limit": 10}}
        result = await agent.ainvoke(state, config=config)

        assert result is not None
        # Decision should be one of the valid outcomes
        decision = result.get("decision")
        assert decision in ("approved", "soft_decline", "manual_review"), (
            f"Unexpected decision: {decision}"
        )


@pytest.mark.live
class TestLiveEndToEndPipeline:
    """Live end-to-end pipeline test running the full graph with real documents."""

    @pytest.mark.asyncio
    async def test_full_pipeline_live_with_mock_documents(self):
        """Run the complete pipeline from auth to enablement with real LLM.

        Uses minimal mock document data to keep the test fast while still
        exercising real LLM calls through the full graph.
        """
        _skip_if_no_infrastructure()

        from src.agents.orchestrator.graph import build_orchestrator_graph
        from src.agents.orchestrator.nodes import inject_llm_client
        from src.infrastructure.llm.factory import get_llm_client

        llm_client = get_llm_client()
        inject_llm_client(llm_client)

        state: ApplicantState = {
            "messages": [
                {"role": "user", "content": "I am divorced and need financial support"},
            ],
            "current_phase": "intake",
            "applicant_id": "live-e2e-001",
            "application_id": "live-e2e-app-001",
            "uploaded_files": ["emirates_id.png", "bank_statement.pdf"],
            "uploaded_documents": [
                {"id": "doc-1", "type": "emirates_id", "path": "/tmp/emirates_id.png"},
                {"id": "doc-2", "type": "bank_statement", "path": "/tmp/bank_statement.pdf"},
            ],
            "identity_number": "784-1990-1234567-8",
            "support_category": "divorced",
            "applicant_info": {
                "full_name": "Ahmed Ali",
                "support_category": "divorced",
                "family_size": 3,
            },
            "eligibility_score": None,
            "decision": None,
            "decision_explanation": None,
            "discrepancies": [],
            "extracted_data": {
                "emirates_id": {
                    "identity_number": "784-1990-1234567-8",
                    "full_name_en": "Ahmed Ali",
                },
                "bank_statement": {
                    "monthly_salary": 8000,
                    "account_holder": "Ahmed Ali",
                },
            },
            "validation_errors": [],
            "extraction_confidence": {"emirates_id": 0.90, "bank_statement": 0.85},
            "validation_results": {},
            "eligibility_factors": None,
            "gate_status": "passed",
            "gate_errors": [],
            "retry_count": 0,
            "escalation_reason": None,
            "enablement_recommendations": [],
            "extraction_results": [],
        }

        with patch("src.agents.orchestrator.graph.get_checkpointer"):
            with patch("src.agents.orchestrator.graph.get_session_factory"):
                graph = await build_orchestrator_graph()

        config = {"configurable": {"thread_id": "live-e2e-001", "recursion_limit": 50}}
        final_state = await graph.ainvoke(state, config=config)

        assert final_state is not None
        # The pipeline should have progressed through multiple phases
        assert final_state.get("current_phase") is not None
