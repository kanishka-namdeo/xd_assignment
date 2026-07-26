import asyncio
import asyncpg

async def test_asyncpg():
    conn = await asyncpg.connect('postgresql://postgres:postgres123@localhost:5432/social_support')
    print('asyncpg: Connected')
    await conn.close()
    print('asyncpg: Closed')

def test_psycopg():
    import psycopg
    conn = psycopg.connect('postgresql://postgres:postgres123@localhost:5432/social_support')
    print('psycopg: Connected')
    conn.close()
    print('psycopg: Closed')

if __name__ == '__main__':
    asyncio.run(test_asyncpg())
    test_psycopg()
