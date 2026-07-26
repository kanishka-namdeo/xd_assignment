"""Master StateGraph definition and compilation."""

import psycopg
import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row

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
from src.config import settings

logger = structlog.get_logger(__name__)

# Module-level checkpointer instance (lives for the process lifetime)
_checkpointer: AsyncPostgresSaver | None = None


async def _get_checkpointer() -> AsyncPostgresSaver:
    """Return a long-lived AsyncPostgresSaver, creating it on first call."""
    global _checkpointer
    if _checkpointer is None:
        # Convert SQLAlchemy async URL to sync PostgreSQL URL
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        # Replace localhost with 127.0.0.1 to avoid IPv6 hang issues
        db_url = db_url.replace("localhost", "127.0.0.1")
        conn = await psycopg.AsyncConnection.connect(
            db_url,
            autocommit=True,
            row_factory=dict_row,
        )
        _checkpointer = AsyncPostgresSaver(conn)
        logger.info("postgres_saver_initialized")
    return _checkpointer


async def build_orchestrator_graph():
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

    checkpointer = await _get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "graph_compiled",
        nodes=["authentication", "intake", "document_collection", "processing", "review", "decision", "enablement"],
        checkpointer_type=type(checkpointer).__name__,
    )

    return compiled
