"""Shared checkpointer factory for all LangGraph agents."""

import psycopg
import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row

from src.config import settings

logger = structlog.get_logger(__name__)

_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return a long-lived AsyncPostgresSaver, creating it on first call.

    This is a singleton factory that all graphs share to avoid connection leaks.
    """
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
