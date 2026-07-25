"""Applicant data access."""

import time
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.applicant import Applicant

logger = structlog.get_logger(__name__)


class ApplicantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_identity_number(self, identity_number: str) -> Applicant | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Applicant).where(Applicant.identity_number == identity_number)
        )
        applicant = result.scalar_one_or_none()
        logger.debug(
            "applicant_get_by_identity_number",
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=applicant is not None,
        )
        return applicant

    async def create(self, identity_number: str) -> Applicant:
        start = time.perf_counter()
        applicant = Applicant(identity_number=identity_number)
        self.session.add(applicant)
        await self.session.flush()
        await self.session.refresh(applicant)
        await self.session.commit()
        logger.info(
            "applicant_created",
            applicant_id=str(applicant.id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return applicant

    async def update(self, applicant: Applicant) -> Applicant:
        start = time.perf_counter()
        await self.session.merge(applicant)
        await self.session.flush()
        await self.session.refresh(applicant)
        logger.debug(
            "applicant_updated",
            applicant_id=str(applicant.id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return applicant

    async def get_by_id(self, applicant_id: UUID) -> Applicant | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Applicant).where(Applicant.id == applicant_id)
        )
        applicant = result.scalar_one_or_none()
        logger.debug(
            "applicant_get_by_id",
            applicant_id=str(applicant_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=applicant is not None,
        )
        return applicant
