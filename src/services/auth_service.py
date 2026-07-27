"""Authentication service - handle applicant login and application creation."""

import time
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas.auth import AuthLoginResponse
from src.infrastructure.db.repositories.applicant_repo import ApplicantRepository
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.utils.emirates_id import validate as validate_emirates_id

logger = structlog.get_logger(__name__)


class AuthService:
    """Handle applicant authentication and application lifecycle."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.applicant_repo = ApplicantRepository(session)
        self.application_repo = ApplicationRepository(session)

    async def login(self, emirates_id: str) -> AuthLoginResponse:
        """Authenticate an applicant by Emirates ID and return application state.

        Validates the Emirates ID checksum, finds or creates the applicant,
        finds or creates their latest application, and returns a state snapshot.

        Args:
            emirates_id: The applicant's Emirates ID number.

        Returns:
            AuthLoginResponse with applicant/application IDs and state snapshot.

        Raises:
            ValueError: If the Emirates ID checksum is invalid.
        """
        start_ms = time.perf_counter()

        logger.info("auth_attempt", id_type="emirates_id", id_checksum_valid=validate_emirates_id(emirates_id))

        if not validate_emirates_id(emirates_id):
            logger.warning("auth_failed", reason="invalid_emirates_id_checksum")
            raise ValueError("Invalid Emirates ID format or checksum")

        applicant = await self.applicant_repo.get_by_identity_number(emirates_id)
        is_new = applicant is None

        if is_new:
            applicant = await self.applicant_repo.create(identity_number=emirates_id)
            application = await self.application_repo.create(applicant_id=applicant.id)
            logger.info(
                "auth_success",
                applicant_type="new",
                applicant_id=str(applicant.id),
                application_id=str(application.id),
            )
            state_snapshot = None
        else:
            application = await self.application_repo.get_latest_by_applicant(applicant.id)
            if application is None:
                application = await self.application_repo.create(applicant_id=applicant.id)
                state_snapshot = None
            else:
                state_snapshot = application.state_snapshot
            logger.info(
                "auth_success",
                applicant_type="returning",
                applicant_id=str(applicant.id),
                application_id=str(application.id),
            )

        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "auth_complete",
            applicant_id=str(applicant.id),
            application_id=str(application.id),
            is_new=is_new,
            duration_ms=round(duration_ms, 2),
        )

        return AuthLoginResponse(
            applicant_id=applicant.id,
            application_id=application.id,
            is_new_applicant=is_new,
            current_phase=application.current_phase,
            state_snapshot=state_snapshot,
            identity_number=emirates_id,
            applicant_info={
                "support_category": getattr(application, "support_category", None),
            } if hasattr(application, "support_category") else None,
        )
