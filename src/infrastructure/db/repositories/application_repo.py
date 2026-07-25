"""Application data access."""

import time
from uuid import UUID

import structlog
from sqlalchemy import select
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
