"""Check if validation_confidence column exists."""
import asyncio
import sys
import time
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.infrastructure.observability.logging import configure_logging
import asyncpg

configure_logging()
logger = structlog.get_logger(__name__)


async def main():
    t0 = time.time()
    logger.info("check_column_started", column_name="validation_confidence", table_name="applications")
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgres://")
    conn = await asyncpg.connect(url)

    try:
        t1 = time.time()
        result = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'applications' AND column_name = 'validation_confidence')"
        )
        duration_ms = (time.time() - t1) * 1000
        logger.info("column_check_completed", exists=result, duration_ms=round(duration_ms, 1))

        if result:
            t2 = time.time()
            rows = await conn.fetch("SELECT id, validation_confidence FROM applications ORDER BY created_at DESC LIMIT 3")
            duration_ms = (time.time() - t2) * 1000
            for row in rows:
                logger.info("application_validation_confidence", application_id=str(row["id"]), validation_confidence=row["validation_confidence"], duration_ms=round(duration_ms, 1))
    except Exception as e:
        logger.exception("column_check_failed", error=str(e))
    finally:
        await conn.close()
    total_duration_ms = (time.time() - t0) * 1000
    logger.info("check_column_completed", total_duration_ms=round(total_duration_ms, 1))


if __name__ == "__main__":
    asyncio.run(main())
