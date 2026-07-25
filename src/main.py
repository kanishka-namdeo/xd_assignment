"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.api.middleware import RequestLoggingMiddleware
from src.api.router import router
from src.config import settings
from src.infrastructure.db.session import get_engine
from src.infrastructure.observability import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)

    logger.info(
        "app_startup",
        app_name=app.title,
        version=app.version,
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        llm_provider=settings.LLM_PROVIDER,
        database_url=settings.DATABASE_URL,
    )

    engine = get_engine(settings)
    async with engine.begin() as conn:
        from src.infrastructure.db.session import Base

        await conn.run_sync(Base.metadata.create_all)

    yield

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
