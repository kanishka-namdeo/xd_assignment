"""Add validation_confidence column to applications table."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
import asyncpg


async def main():
    # Convert asyncpg URL to standard postgres URL
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgres://")
    conn = await asyncpg.connect(url)

    try:
        await conn.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS validation_confidence FLOAT")
        print("Column 'validation_confidence' added to applications table")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
