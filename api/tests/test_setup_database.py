from __future__ import annotations

import pytest

from scripts.setup_database import (
    EXPECTED_TABLES,
    reject_destructive_sql,
    sanitize_error,
    unknown_tables,
    validate_driver,
)


def test_validate_driver_accepts_only_asyncpg_postgresql():
    validate_driver("postgresql+asyncpg://user:secret@host:6543/postgres")

    with pytest.raises(ValueError, match=r"postgresql\+asyncpg"):
        validate_driver("postgresql://user:secret@host:6543/postgres")

    with pytest.raises(ValueError, match=r"postgresql\+asyncpg"):
        validate_driver("sqlite+aiosqlite:///test.db")


def test_reject_destructive_sql_blocks_table_and_data_deletion():
    reject_destructive_sql("create table if not exists users (id uuid primary key);")

    for statement in ("drop table users", "truncate users", "delete from users"):
        with pytest.raises(ValueError, match="destructive"):
            reject_destructive_sql(statement)


def test_unknown_tables_allows_only_application_tables():
    assert unknown_tables(set()) == set()
    assert unknown_tables({"users", "practice_items"}) == set()
    assert unknown_tables(EXPECTED_TABLES | {"unexpected"}) == {"unexpected"}


def test_sanitize_error_removes_database_password():
    message = sanitize_error("connection failed for password secret-value", "secret-value")

    assert "secret-value" not in message
    assert "[redacted]" in message
