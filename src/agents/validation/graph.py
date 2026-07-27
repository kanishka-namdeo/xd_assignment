"""Validation subgraph definition with Reflexion reasoning loop.

Implements the validation agent as a LangGraph StateGraph with Reflexion pattern:
Attempt → Evaluate → Critique → (Clarify | Finalize) → Gate 2

The graph integrates with Gate 2 (completeness validation) and returns
validation results, discrepancies, and confidence scores.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from src.agents.checkpointer import get_checkpointer
from src.agents.state import ApplicantState
from src.agents.validation.nodes import (
    attempt_validation_node,
    critique_validation_node,
    evaluate_validation_node,
    finalize_validation_node,
    gate_2_completeness_node,
    generate_clarification_node,
)
from src.agents.validation.routes import route_after_critique

logger = structlog.get_logger(__name__)

_compiled_graph = None


async def get_validation_graph():
    """Return the cached compiled validation graph, building it once on first call."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = await build_validation_graph()
    return _compiled_graph


async def build_validation_graph():
    """Build the validation agent subgraph with Reflexion reasoning loop.

    The graph follows this flow:
    1. attempt_validation: Run per-doc and cross-doc validation
    2. evaluate_validation: Classify discrepancies as OCR errors or real
    3. critique_validation: Self-critique and decide next action
    4. Conditional routing:
       - If clarification needed → generate_clarification
       - If validation complete → finalize_validation
       - If escalating → end
    5. finalize_validation: Compute final confidence and gate status
    6. gate_2_completeness: Deterministic completeness check

    Returns:
        Compiled StateGraph ready for invocation.
    """
    graph = StateGraph(ApplicantState)

    graph.add_node("attempt_validation", attempt_validation_node)
    graph.add_node("evaluate_validation", evaluate_validation_node)
    graph.add_node("critique_validation", critique_validation_node)
    graph.add_node("generate_clarification", generate_clarification_node)
    graph.add_node("finalize_validation", finalize_validation_node)
    graph.add_node("gate_2_completeness", gate_2_completeness_node)

    graph.add_edge(START, "attempt_validation")
    graph.add_edge("attempt_validation", "evaluate_validation")
    graph.add_edge("evaluate_validation", "critique_validation")

    graph.add_conditional_edges(
        "critique_validation",
        route_after_critique,
        {
            "generate_clarification": "generate_clarification",
            "finalize_validation": "finalize_validation",
            "end": END,
        },
    )

    graph.add_edge("generate_clarification", "finalize_validation")
    graph.add_edge("finalize_validation", "gate_2_completeness")
    graph.add_edge("gate_2_completeness", END)

    checkpointer = await get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "validation_graph_compiled",
        nodes=[
            "attempt_validation",
            "evaluate_validation",
            "critique_validation",
            "generate_clarification",
            "finalize_validation",
            "gate_2_completeness",
        ],
        checkpointer_type=type(checkpointer).__name__,
    )

    return compiled


async def run_validation_agent(state: ApplicantState) -> ApplicantState:
    """Run the validation agent on the given state.

    This is the main entry point for the validation agent. It executes
    the Reflexion reasoning loop and returns the updated state with
    validation results, discrepancies, and confidence scores.

    Args:
        state: Current applicant state with extracted_data populated.

    Returns:
        Updated state with validation_results, discrepancies, gate_status, etc.
    """
    logger.info(
        "validation_agent_start",
        application_id=state.get("application_id"),
        applicant_id=state.get("applicant_id"),
        document_count=len(state.get("extracted_data", {})),
    )

    graph = await get_validation_graph()
    config = {
        "configurable": {
            "thread_id": state.get("application_id", "default"),
            "recursion_limit": 15,
        },
    }

    result = await graph.ainvoke(state, config=config)

    logger.info(
        "validation_agent_complete",
        application_id=state.get("application_id"),
        gate_status=result.get("gate_status"),
        overall_confidence=result.get("validation_results", {}).get("overall_confidence"),
        discrepancy_count=len(result.get("discrepancies", [])),
    )

    return result
