"""Route aggregation."""

from fastapi import APIRouter

from src.api.v1 import applications, auth, chat, eligibility

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(applications.router)
router.include_router(eligibility.router)
