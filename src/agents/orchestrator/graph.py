"""Master StateGraph definition and compilation."""

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents.orchestrator.nodes import (
    decision_node,
    document_collection_node,
    enablement_node,
    intake_node,
    processing_node,
    review_node,
)
from src.agents.orchestrator.routes import route_by_phase
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


def build_orchestrator_graph() -> StateGraph:
    graph = StateGraph(ApplicantState)

    graph.add_node("intake", intake_node)
    graph.add_node("document_collection", document_collection_node)
    graph.add_node("processing", processing_node)
    graph.add_node("review", review_node)
    graph.add_node("decision", decision_node)
    graph.add_node("enablement", enablement_node)

    graph.add_conditional_edges(START, route_by_phase, {
        "intake": "intake",
        "document_collection": "document_collection",
        "processing": "processing",
        "review": "review",
        "decision": "decision",
        "enablement": "enablement",
    })

    graph.add_edge("intake", "document_collection")
    graph.add_edge("document_collection", "processing")
    graph.add_edge("processing", "review")
    graph.add_edge("review", "decision")
    graph.add_edge("decision", "enablement")
    graph.add_edge("enablement", END)

    checkpointer = MemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "graph_compiled",
        event="graph_compiled",
        nodes=["intake", "document_collection", "processing", "review", "decision", "enablement"],
        checkpointer_type=type(checkpointer).__name__,
    )

    if isinstance(checkpointer, MemorySaver):
        logger.warning(
            "checkpointer_warning",
            event="checkpointer_warning",
            message="MemorySaver is in-memory only and not suitable for production deployments",
            checkpointer_type="MemorySaver",
        )

    return compiled
