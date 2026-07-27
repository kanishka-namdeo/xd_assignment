"""Master StateGraph definition and compilation."""

import structlog
from langgraph.graph import END, START, StateGraph

from src.agents.checkpointer import get_checkpointer
from src.agents.orchestrator.nodes import (
    authentication_node,
    decision_node,
    document_collection_node,
    enablement_node,
    intake_node,
    processing_node,
    review_node,
)
from src.agents.orchestrator.routes import (
    route_after_document_collection,
    route_after_intake,
    route_after_review,
    route_by_phase,
)
from src.agents.state import ApplicantState
from src.agents.orchestrator.phases.document_collection import (
    enable_document_persistence,
    set_document_persistence,
)
from src.config import settings
from src.infrastructure.db.session import get_session_factory

logger = structlog.get_logger(__name__)


async def build_orchestrator_graph():
    # Inject DB session factory for document persistence.
    try:
        factory = get_session_factory(settings)
        set_document_persistence(factory)
        enable_document_persistence()
    except Exception as e:
        logger.warning("document_persistence_setup_failed", error=str(e))

    graph = StateGraph(ApplicantState)

    graph.add_node("authentication", authentication_node)
    graph.add_node("intake", intake_node)
    graph.add_node("document_collection", document_collection_node)
    graph.add_node("processing", processing_node)
    graph.add_node("review", review_node)
    graph.add_node("decision", decision_node)
    graph.add_node("enablement", enablement_node)

    graph.add_conditional_edges(START, route_by_phase, {
        "authentication": "authentication",
        "intake": "intake",
        "document_collection": "document_collection",
        "processing": "processing",
        "review": "review",
        "decision": "decision",
        "enablement": "enablement",
    })

    graph.add_edge("authentication", "intake")
    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "intake": "intake",
            "document_collection": "document_collection",
        }
    )
    graph.add_conditional_edges(
        "document_collection",
        route_after_document_collection,
        {
            "document_collection": "document_collection",
            "processing": "processing",
        }
    )
    graph.add_edge("processing", "review")
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "document_collection": "document_collection",
            "review": "review",
            "decision": "decision",
        }
    )
    graph.add_edge("decision", "enablement")
    graph.add_edge("enablement", END)

    checkpointer = await get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "graph_compiled",
        nodes=["authentication", "intake", "document_collection", "processing", "review", "decision", "enablement"],
        checkpointer_type=type(checkpointer).__name__,
    )

    return compiled
