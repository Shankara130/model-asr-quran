from __future__ import annotations

import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "database_schema.sql"
TABLES = {
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


def schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8").lower()


def test_every_application_table_enables_rls_and_revokes_client_roles():
    sql = schema_sql()

    for table in TABLES:
        assert f"alter table public.{table} enable row level security;" in sql
        assert f"revoke all on table public.{table} from anon, authenticated;" in sql


def test_trigger_function_has_restricted_execution_context():
    sql = schema_sql()

    assert "security invoker" in sql
    assert "set search_path = public, pg_temp" in sql
    revoke = "revoke execute on function public.set_updated_at() from public, anon, authenticated;"
    assert revoke in sql


def test_schema_does_not_delete_tables_or_rows():
    sql = schema_sql()

    assert re.search(r"\bdrop\s+table\b", sql) is None
    assert re.search(r"\btruncate\b", sql) is None
    assert re.search(r"\bdelete\s+from\b", sql) is None
