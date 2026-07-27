"""Test persist_decision method directly."""
import asyncio
import sys
import time
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.observability.logging import configure_logging
from src.services.decision_service import DecisionService

configure_logging()
logger = structlog.get_logger(__name__)


async def main():
    t0 = time.time()
    factory = get_session_factory(settings)
    async with factory() as session:
        # Get the latest application
        from src.infrastructure.db.models.application import Application
        from sqlalchemy import select
        result = await session.execute(
            select(Application).order_by(Application.created_at.desc()).limit(1)
        )
        app = result.scalar_one_or_none()

        if app:
            logger.info("persist_decision_test_started", application_id=str(app.id), current_validation_confidence=app.validation_confidence)

            # Now test persist_decision
            t1 = time.time()
            decision_svc = DecisionService(session)
            await decision_svc.persist_decision(
                application_id=app.id,
                decision="manual_review",
                decision_explanation="Test explanation",
                eligibility_score=0.78,
                validation_confidence=0.45,
            )
            duration_ms = (time.time() - t1) * 1000
            logger.info("persist_decision_completed", duration_ms=round(duration_ms, 1))

            # Re-fetch to verify
            result = await session.execute(
                select(Application).where(Application.id == app.id)
            )
            updated_app = result.scalar_one_or_none()
            logger.info(
                "persist_decision_verified",
                validation_confidence=updated_app.validation_confidence,
                eligibility_score=updated_app.eligibility_score,
                decision=updated_app.decision,
            )
        else:
            logger.warning("no_application_found")

    total_duration_ms = (time.time() - t0) * 1000
    logger.info("persist_decision_test_completed", total_duration_ms=round(total_duration_ms, 1))


if __name__ == "__main__":
    asyncio.run(main())
