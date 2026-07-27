import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres123@localhost:5432/social_support')
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        print(f"Current migration: {row[0] if row else 'None'}")
    await engine.dispose()

asyncio.run(check())
