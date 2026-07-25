"""Eligibility scoring endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.deps import AsyncDB
from src.domain.schemas.eligibility import (
    EligibilityComputeResponse,
    EligibilityExplanationResponse,
    EligibilityResponse,
)
from src.services.application_service import ApplicationService
from src.services.eligibility_service import EligibilityService

router = APIRouter(prefix="/eligibility", tags=["eligibility"])


@router.get(
    "/{application_id}",
    response_model=EligibilityResponse,
    status_code=status.HTTP_200_OK,
)
async def get_eligibility(
    application_id: UUID,
    db: AsyncDB,
) -> EligibilityResponse:
    """Get eligibility score for an application."""
    service = EligibilityService(db)
    result = await service.get_eligibility(application_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility not computed for this application",
        )
    return EligibilityResponse(
        application_id=result["application_id"],
        eligibility_score=result["eligibility_score"],
        factors=result.get("factors"),
    )


@router.post(
    "/{application_id}/compute",
    response_model=EligibilityComputeResponse,
    status_code=status.HTTP_200_OK,
)
async def compute_eligibility(
    application_id: UUID,
    db: AsyncDB,
) -> EligibilityComputeResponse:
    """Compute eligibility score for an application."""
    app_service = ApplicationService(db)
    application = await app_service.get_application(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    service = EligibilityService(db)
    result = await service.compute_eligibility(application_id)
    return EligibilityComputeResponse(
        application_id=result["application_id"],
        eligibility_score=result["eligibility_score"],
        factors=result["factors"],
        features_used=result["features_used"],
    )


@router.get(
    "/{application_id}/explanation",
    response_model=EligibilityExplanationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_eligibility_explanation(
    application_id: UUID,
    db: AsyncDB,
) -> EligibilityExplanationResponse:
    """Get human-readable explanation of eligibility decision."""
    service = EligibilityService(db)
    explanation = await service.get_eligibility_explanation(application_id)
    if explanation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility not computed for this application",
        )

    result = await service.get_eligibility(application_id)
    return EligibilityExplanationResponse(
        application_id=application_id,
        explanation=explanation,
        eligibility_score=result["eligibility_score"] if result else 0.0,
    )
