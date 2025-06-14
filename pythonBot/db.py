import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
PG_URL = os.getenv("PG_URL")


async def init_db():
    conn = await asyncpg.connect(PG_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            full_name TEXT,
            name TEXT,
            phone TEXT,
            region TEXT,
            language TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT,
            full_name TEXT,
            stars INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    await conn.close()


async def save_user(data, telegram_id, full_name):
    conn = await asyncpg.connect(PG_URL)
    await conn.execute("""
        INSERT INTO users (telegram_id, full_name, name, phone, region, language)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (telegram_id) DO NOTHING;
    """, telegram_id, full_name, data["name"], data["phone"], data["region"], data["language"])
    await conn.close()


async def save_rating(telegram_id, full_name, stars):
    conn = await asyncpg.connect(PG_URL)
    await conn.execute("""
        INSERT INTO ratings (telegram_id, full_name, stars)
        VALUES ($1, $2, $3);
    """, telegram_id, full_name, stars)
    await conn.close()


async def get_average_rating():
    conn = await asyncpg.connect(PG_URL)
    result = await conn.fetchval("SELECT AVG(stars) FROM ratings;")
    await conn.close()
    return round(result, 2) if result else None
