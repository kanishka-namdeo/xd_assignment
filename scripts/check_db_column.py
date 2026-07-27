"""Check if validation_confidence column exists."""
import asyncio
import sys
import time
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings
from src.infrastructure.observability.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


async def check():
    t0 = time.time()
    logger.info("check_db_column_started", column_name="validation_confidence", table_name="applications")
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        t1 = time.time()
        result = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'applications' AND column_name = 'validation_confidence'")
        )
        duration_ms = (time.time() - t1) * 1000
        exists = bool(result.first())
        logger.info("column_check_completed", exists=exists, duration_ms=round(duration_ms, 1))
    await engine.dispose()
    total_duration_ms = (time.time() - t0) * 1000
    logger.info("check_db_column_completed", total_duration_ms=round(total_duration_ms, 1))


if __name__ == "__main__":
    asyncio.run(check())
