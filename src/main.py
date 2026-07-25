"""FastAPI application factory."""

from fastapi import FastAPI

from src.api.router import router
from src.config import settings
from src.infrastructure.db.session import get_engine


def create_app() -> FastAPI:
    app = FastAPI(
        title="UAE Social Support Application",
        description="Workflow automation for social support applications",
        version="1.0.0",
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup():
        engine = get_engine(settings)
        async with engine.begin() as conn:
            from src.infrastructure.db.session import Base
            await conn.run_sync(Base.metadata.create_all)

    return app


app = create_app()
