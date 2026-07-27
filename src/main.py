"""FastAPI application factory."""

import sys
import asyncio

# Windows asyncio event loop compatibility for psycopg async
# Must be set before any async code runs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.checkpointer import get_checkpointer_manager
from src.api.middleware import RequestLoggingMiddleware
from src.api.router import router
from src.config import settings
from src.infrastructure.db.session import get_engine
from src.infrastructure.observability import configure_logging, set_langfuse_client
from src.infrastructure.observability.langfuse_client import LangfuseClient

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)

    langfuse_client = LangfuseClient()
    app.state.langfuse = langfuse_client
    set_langfuse_client(langfuse_client)

    logger.info(
        "app_startup",
        app_name=app.title,
        version=app.version,
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        llm_provider=settings.LLM_PROVIDER,
        database_url=settings.DATABASE_URL,
        langfuse_enabled=langfuse_client.enabled,
    )

    engine = get_engine(settings)
    async with engine.begin() as conn:
        from src.infrastructure.db.session import Base

        await conn.run_sync(Base.metadata.create_all)

    # Start checkpoint TTL cleanup task
    checkpointer_manager = get_checkpointer_manager()
    await checkpointer_manager.start_cleanup_task()
    app.state.checkpointer_manager = checkpointer_manager

    yield

    # Stop checkpoint cleanup task gracefully
    if hasattr(app.state, "checkpointer_manager"):
        await app.state.checkpointer_manager.stop_cleanup_task()

    if hasattr(app.state, "langfuse"):
        app.state.langfuse.shutdown()

    logger.info("app_shutdown", app_name=app.title, version=app.version)


def create_app() -> FastAPI:
    app = FastAPI(
        title="UAE Social Support Application",
        description="Workflow automation for social support applications",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Allow cross-origin requests from Streamlit frontend (development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)

    return app


app = create_app()
