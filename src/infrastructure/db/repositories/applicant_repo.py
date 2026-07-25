"""Applicant data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.applicant import Applicant


class ApplicantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_identity_number(self, identity_number: str) -> Applicant | None:
        result = await self.session.execute(
            select(Applicant).where(Applicant.identity_number == identity_number)
        )
        return result.scalar_one_or_none()

    async def create(self, identity_number: str) -> Applicant:
        applicant = Applicant(identity_number=identity_number)
        self.session.add(applicant)
        await self.session.flush()
        await self.session.refresh(applicant)
        return applicant

    async def update(self, applicant: Applicant) -> Applicant:
        await self.session.merge(applicant)
        await self.session.flush()
        await self.session.refresh(applicant)
        return applicant

    async def get_by_id(self, applicant_id: UUID) -> Applicant | None:
        result = await self.session.execute(
            select(Applicant).where(Applicant.id == applicant_id)
        )
        return result.scalar_one_or_none()
