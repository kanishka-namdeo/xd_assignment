"""Apply checkpoint migration directly via SQL."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from sqlalchemy import text
from src.infrastructure.db.session import get_engine
from src.config import Settings

async def run_migration():
    settings = Settings()
    engine = get_engine(settings)
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'checkpoints' AND column_name = 'created_at'
        """))
        if result.fetchone():
            print('Column already exists')
            return
        
        # Add the column
        await conn.execute(text('ALTER TABLE checkpoints ADD COLUMN created_at TIMESTAMPTZ DEFAULT now()'))
        await conn.execute(text('UPDATE checkpoints SET created_at = now() WHERE created_at IS NULL'))
        await conn.execute(text('ALTER TABLE checkpoints ALTER COLUMN created_at SET NOT NULL'))
        await conn.execute(text('CREATE INDEX ix_checkpoints_created_at ON checkpoints (created_at)'))
        print('Migration applied successfully')
    await engine.dispose()

asyncio.run(run_migration())
