"""Document upload and status endpoints."""

import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/status")
async def document_status():
    logger.info("request_received", event="document_status_check")
    logger.info("response_sent", event="document_status_ok")
    return {"status": "ok"}
