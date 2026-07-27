"""Auth endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.domain.schemas.auth import AuthLoginRequest, AuthLoginResponse
from src.services.auth_service import AuthService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=AuthLoginResponse, status_code=status.HTTP_200_OK)
async def login(
    request: AuthLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthLoginResponse:
    try:
        return await auth_service.login(request.emirates_id)
    except ValueError as e:
        logger.warning("auth_failed", reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
