"""SQLAlchemy async engine and sessionmaker."""

import time

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import Settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


_engine = None
_SessionLocal = None


def get_engine(settings: Settings):
    global _engine
    if _engine is None:
        database_url = settings.DATABASE_URL
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=20,
        )
        logger.info(
            "db_engine_created",
            pool_size=20,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
        )

        @_engine.pool.listen("connect")
        def on_connect(dbapi_conn, connection_record):
            logger.debug("db_pool_connect")

        @_engine.pool.listen("disconnect")
        def on_disconnect(dbapi_conn, connection_record):
            logger.debug("db_pool_disconnect")

        @_engine.pool.listen("checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            logger.debug("db_pool_checkout")

        @_engine.pool.listen("checkin")
        def on_checkin(dbapi_conn, connection_record, connection_proxy):
            logger.debug("db_pool_checkin")

    return _engine


async def get_session(settings: Settings) -> AsyncSession:
    """Create a new session with query duration logging."""
    factory = get_session_factory(settings)
    session = factory()

    @event.listens_for(session.sync_session, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(session.sync_session, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.perf_counter() - conn.info["query_start_time"].pop(-1)
        logger.debug(
            "db_query_executed",
            duration_ms=round(total * 1000, 2),
            executemany=executemany,
        )

    @event.listens_for(session.sync_session, "handle_error")
    def receive_handle_error(context):
        logger.error(
            "db_query_error",
            error=str(context.original_exception),
        )

    return session


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(settings)
        _SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _SessionLocal
