"""Application data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.application import Application


class ApplicationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_by_applicant(self, applicant_id: UUID) -> Application | None:
        result = await self.session.execute(
            select(Application)
            .where(Application.applicant_id == applicant_id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, applicant_id: UUID) -> Application:
        application = Application(applicant_id=applicant_id)
        self.session.add(application)
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def update(self, application: Application) -> Application:
        await self.session.merge(application)
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def get_by_id(self, application_id: UUID) -> Application | None:
        result = await self.session.execute(
            select(Application).where(Application.id == application_id)
        )
        return result.scalar_one_or_none()
