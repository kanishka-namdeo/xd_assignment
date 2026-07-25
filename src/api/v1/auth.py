"""Auth endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AsyncDB
from src.domain.schemas.auth import AuthLoginRequest, AuthLoginResponse
from src.infrastructure.db.repositories.applicant_repo import ApplicantRepository
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.utils.emirates_id import validate as validate_emirates_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthLoginResponse, status_code=status.HTTP_200_OK)
async def login(
    request: AuthLoginRequest,
    db: AsyncDB,
) -> AuthLoginResponse:
    logger.info("auth_attempt", event="auth_attempt", id_type="emirates_id", id_checksum_valid=validate_emirates_id(request.emirates_id))

    if not validate_emirates_id(request.emirates_id):
        logger.warning("auth_failed", event="auth_failed", reason="invalid_emirates_id_checksum")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Emirates ID format or checksum",
        )

    applicant_repo = ApplicantRepository(db)
    application_repo = ApplicationRepository(db)

    applicant = await applicant_repo.get_by_identity_number(request.emirates_id)
    is_new = applicant is None

    if is_new:
        applicant = await applicant_repo.create(identity_number=request.emirates_id)
        application = await application_repo.create(applicant_id=applicant.id)
        logger.info("auth_success", event="auth_success", applicant_type="new", applicant_id=str(applicant.id), application_id=str(application.id))
    else:
        application = await application_repo.get_latest_by_applicant(applicant.id)
        if application is None:
            application = await application_repo.create(applicant_id=applicant.id)
        logger.info("auth_success", event="auth_success", applicant_type="returning", applicant_id=str(applicant.id), application_id=str(application.id))

    return AuthLoginResponse(
        applicant_id=applicant.id,
        application_id=application.id,
        is_new_applicant=is_new,
        current_phase=application.current_phase,
    )
