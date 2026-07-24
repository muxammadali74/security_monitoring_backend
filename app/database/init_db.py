import asyncpg

from config import settings
from app.database.connection import engine
from app.database.base import Base
from app.models import *

async def check_and_create_database() -> None:
    try:
        conn = await asyncpg.connect(
            user=settings.DB_USER,
            password=settings.DB_PASS,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database="postgres",
        )

        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", settings.DB_NAME
        )

        if not db_exists:
            # CREATE DATABASE нельзя выполнить внутри транзакции — asyncpg.execute
            # по умолчанию выполняет запрос вне транзакции, так что это безопасно.
            await conn.execute(f'CREATE DATABASE "{settings.DB_NAME}"')
            print(f"[DB] Database '{settings.DB_NAME}' successfully created.", flush=True)
        else:
            print(f"[DB] Database '{settings.DB_NAME}' already exists.", flush=True)

        await conn.close()

    except Exception as e:
        print(f"[DB ERROR] Error while checking or creating the database: {e}", flush=True)
        raise


async def init_tables() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] All database tables have been successfully synchronized.", flush=True)
    except Exception as e:
        print(f"[DB ERROR] Error creating tables: {e}", flush=True)
        raise
