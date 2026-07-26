"""Extraction subgraph definition.

Defines the extraction subgraph that integrates the ReAct extraction
agent with Gate 1 (document integrity validation). The subgraph:
1. Runs the extraction agent on uploaded documents
2. Validates extracted data against deterministic gates
3. Retries on gate failure (max 2 retries)
4. Returns extracted data and confidence scores
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from src.agents.extraction.nodes import (
    extract_documents_node,
    summarize_extraction_node,
)
from src.agents.extraction.routes import route_after_extraction
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


def build_extraction_subgraph() -> StateGraph:
    """Build the extraction subgraph.

    Graph structure:
    - extract_documents: Run ReAct agent to extract data from documents
    - summarize_extraction: Summarize results and prepare for validation
    - Conditional routing based on gate_status (passed → END, failed → END with errors)

    Returns:
        Compiled StateGraph for the extraction phase.
    """
    graph = StateGraph(ApplicantState)

    # Add nodes
    graph.add_node("extract_documents", extract_documents_node)
    graph.add_node("summarize_extraction", summarize_extraction_node)

    # Add edges
    graph.add_edge(START, "extract_documents")
    graph.add_edge("extract_documents", "summarize_extraction")

    # Conditional routing after summarization
    graph.add_conditional_edges(
        "summarize_extraction",
        route_after_extraction,
        {
            "extraction_passed": END,
            "extraction_failed": END,
        },
    )

    compiled = graph.compile()

    logger.info(
        "extraction_subgraph_compiled",
        nodes=["extract_documents", "summarize_extraction"],
        routing_function="route_after_extraction",
    )

    return compiled


def get_extraction_subgraph() -> StateGraph:
    """Get the compiled extraction subgraph.

    This is the public API for the orchestrator to import and use
    as a subgraph in the processing phase.

    Returns:
        Compiled StateGraph for extraction.
    """
    return build_extraction_subgraph()
