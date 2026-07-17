from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "docs" / "database_schema.sql"

EXPECTED_TABLES = {
    "users",
    "auth_refresh_tokens",
    "user_preferences",
    "practice_items",
    "practice_item_segments",
    "practice_sessions",
    "practice_session_realtime_tokens",
    "audio_uploads",
    "audio_chunks",
    "evaluation_results",
    "ayah_highlights",
    "letter_insights",
    "letter_mastery",
    "weekly_reports",
    "practice_session_events",
    "request_logs",
}

DESTRUCTIVE_PATTERN = re.compile(r"\b(drop\s+table|truncate|delete\s+from)\b", re.IGNORECASE)


def validate_driver(database_url: str) -> None:
    if make_url(database_url).drivername != "postgresql+asyncpg":
        raise ValueError("SOBAT_DATABASE_URL must use the postgresql+asyncpg driver")


def reject_destructive_sql(sql: str) -> None:
    if DESTRUCTIVE_PATTERN.search(sql):
        raise ValueError("schema contains a destructive table or data operation")


def unknown_tables(existing: set[str]) -> set[str]:
    return existing - EXPECTED_TABLES


def sanitize_error(message: str, password: str | None) -> str:
    if password:
        return message.replace(password, "[redacted]")
    return message


def load_schema() -> str:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    reject_destructive_sql(sql)
    return sql


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"timeout": 10, "statement_cache_size": 0},
    )


async def public_tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("select tablename from pg_catalog.pg_tables where schemaname = 'public'")
        )
        return {str(row[0]) for row in rows}


async def check_database(engine: AsyncEngine, sql: str) -> set[str]:
    async with asyncio.timeout(20):
        async with engine.connect() as conn:
            assert (await conn.execute(text("select 1"))).scalar_one() == 1
        existing = await public_tables(engine)
    collisions = unknown_tables(existing)
    if collisions:
        names = ", ".join(sorted(collisions))
        raise RuntimeError(f"unexpected public tables found: {names}")
    reject_destructive_sql(sql)
    return existing


async def apply_schema(engine: AsyncEngine, sql: str) -> None:
    async with asyncio.timeout(60):
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            driver = raw.driver_connection
            async with driver.transaction():
                await driver.execute(sql)


async def verify_database(engine: AsyncEngine) -> dict[str, int]:
    async with asyncio.timeout(30):
        tables = await public_tables(engine)
        missing = EXPECTED_TABLES - tables
        if missing:
            raise RuntimeError(f"missing application tables: {', '.join(sorted(missing))}")

        async with engine.connect() as conn:
            rls_rows = await conn.execute(
                text(
                    "select c.relname from pg_catalog.pg_class c "
                    "join pg_catalog.pg_namespace n on n.oid = c.relnamespace "
                    "where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity"
                )
            )
            secured = {str(row[0]) for row in rls_rows}
            missing_rls = EXPECTED_TABLES - secured
            if missing_rls:
                raise RuntimeError(f"tables missing RLS: {', '.join(sorted(missing_rls))}")

            grant_count = int(
                (
                    await conn.execute(
                        text(
                            "select count(*) from information_schema.table_privileges "
                            "where table_schema = 'public' "
                            "and grantee in ('anon', 'authenticated') "
                            "and table_name = any(:tables)"
                        ),
                        {"tables": sorted(EXPECTED_TABLES)},
                    )
                ).scalar_one()
            )
            if grant_count:
                raise RuntimeError("anon/authenticated still have application table privileges")

    return {
        "tables": len(EXPECTED_TABLES),
        "rls_enabled": len(EXPECTED_TABLES),
        "client_grants": grant_count,
    }


async def run(mode: str) -> None:
    from api.settings import settings

    validate_driver(settings.database_url)
    sql = load_schema()
    engine = create_engine(settings.database_url)
    try:
        existing = await check_database(engine, sql)
        print(f"check=ok existing_application_tables={len(existing)}")
        if mode == "apply":
            await apply_schema(engine, sql)
            print("apply=ok transaction=committed")
        if mode in {"apply", "verify"}:
            result = await verify_database(engine)
            print(
                "verify=ok "
                f"tables={result['tables']} rls={result['rls_enabled']} "
                f"client_grants={result['client_grants']}"
            )
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up the Sobat Ngaji Supabase database")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_const", const="check", dest="mode")
    mode.add_argument("--apply", action="store_const", const="apply", dest="mode")
    mode.add_argument("--verify", action="store_const", const="verify", dest="mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(run(args.mode))
    except Exception as exc:
        from api.settings import settings

        password = make_url(settings.database_url).password
        print(f"database_setup=failed error={sanitize_error(str(exc), password)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
