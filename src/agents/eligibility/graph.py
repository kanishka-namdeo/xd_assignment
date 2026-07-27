"""Eligibility subgraph definition."""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from src.agents.state import ApplicantState
from src.agents.eligibility.nodes import (
    eligibility_finalize_node,
    eligibility_gate_node,
    eligibility_react_node,
)
from src.agents.eligibility.routes import route_after_eligibility_gate

logger = structlog.get_logger(__name__)

_compiled_graph = None


def build_eligibility_graph() -> StateGraph:
    """Build the eligibility subgraph with direct tool calls and Gate 3."""
    graph = StateGraph(ApplicantState)

    # Add nodes
    graph.add_node("eligibility_react", eligibility_react_node)
    graph.add_node("eligibility_gate", eligibility_gate_node)
    graph.add_node("eligibility_finalize", eligibility_finalize_node)

    # Add edges
    graph.add_edge(START, "eligibility_react")
    graph.add_edge("eligibility_react", "eligibility_gate")

    # Conditional edge after gate: pass → finalize, fail → END
    graph.add_conditional_edges(
        "eligibility_gate",
        route_after_eligibility_gate,
        {
            "finalize": "eligibility_finalize",
            "end": END,
        },
    )

    graph.add_edge("eligibility_finalize", END)

    return graph


def get_eligibility_graph():
    """Get the compiled eligibility subgraph."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_eligibility_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph
