"""FastAPI application factory."""

import sys

# Windows asyncio event loop compatibility for psycopg async
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

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

    yield

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

    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)

    return app


app = create_app()
