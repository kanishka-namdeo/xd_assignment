"""Application service - business logic for application lifecycle."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.application import Application
from src.infrastructure.db.repositories.application_repo import ApplicationRepository

logger = structlog.get_logger()


class ApplicationService:
    """Manage application lifecycle and status transitions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ApplicationRepository(session)

    async def create_application(
        self, applicant_id: UUID, support_category: str | None = None
    ) -> Application:
        """Create a new application for an applicant."""
        application = await self.repo.create(applicant_id=applicant_id)
        if support_category:
            application.status = "in_progress"
            application.current_phase = "intake"
            await self.repo.update(application)

        logger.info(
            "application_created",
            application_id=str(application.id),
            applicant_id=str(applicant_id),
            support_category=support_category,
        )
        return application

    async def get_application(self, application_id: UUID) -> Application | None:
        """Retrieve application by ID."""
        return await self.repo.get_by_id(application_id)

    async def update_application_status(
        self, application_id: UUID, status: str, phase: str | None = None
    ) -> Application | None:
        """Update application status and optionally the current phase."""
        application = await self.repo.get_by_id(application_id)
        if application is None:
            return None

        application.status = status
        if phase is not None:
            application.current_phase = phase

        completed = application.phase_completed or {}
        completed[application.current_phase] = datetime.now(timezone.utc).isoformat()
        application.phase_completed = completed

        await self.repo.update(application)
        logger.info(
            "application_status_updated",
            application_id=str(application_id),
            status=status,
            phase=phase,
        )
        return application

    async def list_applications(self, applicant_id: UUID) -> list[Application]:
        """List all applications for an applicant."""
        application = await self.repo.get_latest_by_applicant(applicant_id)
        return [application] if application else []

    async def set_eligibility_score(
        self, application_id: UUID, score: float, factors: dict | None = None
    ) -> Application | None:
        """Store eligibility score and contributing factors."""
        application = await self.repo.get_by_id(application_id)
        if application is None:
            return None

        application.eligibility_score = score
        if factors is not None:
            application.eligibility_factors = factors
        await self.repo.update(application)
        return application

    async def set_decision(
        self, application_id: UUID, decision: str, explanation: str | None = None
    ) -> Application | None:
        """Store final decision and explanation."""
        application = await self.repo.get_by_id(application_id)
        if application is None:
            return None

        application.decision = decision
        application.decision_explanation = explanation
        await self.repo.update(application)

        logger.info(
            "application_decision_set",
            application_id=str(application_id),
            decision=decision,
        )
        return application
