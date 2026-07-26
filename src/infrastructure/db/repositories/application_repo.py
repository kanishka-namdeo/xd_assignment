"""Application data access."""

import time
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.application import Application

logger = structlog.get_logger(__name__)


class ApplicationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_by_applicant(self, applicant_id: UUID) -> Application | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Application)
            .where(Application.applicant_id == applicant_id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        application = result.scalar_one_or_none()
        logger.debug(
            "application_get_latest_by_applicant",
            applicant_id=str(applicant_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=application is not None,
        )
        return application

    async def create(self, applicant_id: UUID) -> Application:
        start = time.perf_counter()
        application = Application(applicant_id=applicant_id)
        self.session.add(application)
        await self.session.flush()
        await self.session.refresh(application)
        await self.session.commit()
        logger.info(
            "application_created",
            application_id=str(application.id),
            applicant_id=str(applicant_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return application

    async def update(self, application: Application) -> Application:
        start = time.perf_counter()
        await self.session.merge(application)
        await self.session.flush()
        await self.session.refresh(application)
        logger.debug(
            "application_updated",
            application_id=str(application.id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return application

    async def get_by_id(self, application_id: UUID) -> Application | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Application).where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        logger.debug(
            "application_get_by_id",
            application_id=str(application_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=application is not None,
        )
        return application

    async def get_state(self, application_id: UUID) -> dict | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Application.state_snapshot).where(Application.id == application_id)
        )
        state = result.scalar_one_or_none()
        logger.debug(
            "application_get_state",
            application_id=str(application_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=state is not None,
        )
        return state

    async def save_state(self, application_id: UUID, state: dict) -> None:
        import json
        start = time.perf_counter()
        
        def make_serializable(obj):
            """Recursively convert non-serializable objects to serializable form."""
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif hasattr(obj, "content") and hasattr(obj, "type"):
                # LangChain message object
                return {
                    "type": obj.type,
                    "content": obj.content,
                    "additional_kwargs": make_serializable(getattr(obj, "additional_kwargs", {})),
                }
            elif hasattr(obj, "__dict__"):
                return make_serializable(obj.__dict__)
            else:
                return str(obj)
        
        # Deep serialize the entire state
        state_serializable = make_serializable(state)
        
        # Remove __interrupt__ key (LangGraph internal)
        state_serializable.pop("__interrupt__", None)
        
        await self.session.execute(
            update(Application)
            .where(Application.id == application_id)
            .values(state_snapshot=state_serializable)
        )
        await self.session.flush()
        logger.debug(
            "application_save_state",
            application_id=str(application_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            state_keys=list(state_serializable.keys()),
        )
