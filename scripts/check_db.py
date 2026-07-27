"""Check validation_confidence in database."""
import sys
import time
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from src.config import settings
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.db.models.application import Application
from src.infrastructure.observability.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


async def check():
    t0 = time.time()
    logger.info("check_db_started")
    factory = get_session_factory(settings)
    async with factory() as session:
        result = await session.execute(select(Application).order_by(Application.created_at.desc()).limit(1))
        app = result.scalar_one_or_none()
        if app:
            logger.info(
                "application_found",
                application_id=str(app.id),
                decision=app.decision,
                eligibility_score=app.eligibility_score,
                validation_confidence=app.validation_confidence,
            )
        else:
            logger.warning("no_applications_found")
    duration_ms = (time.time() - t0) * 1000
    logger.info("check_db_completed", duration_ms=round(duration_ms, 1))


if __name__ == "__main__":
    asyncio.run(check())
