# Supabase PostgreSQL Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Sobat Ngaji FastAPI database schema secure and compatible with Supabase PostgreSQL, deploy it transactionally, seed practice data idempotently, and verify Supabase Auth profile synchronization.

**Architecture:** SQLAlchemy models use native temporal types shared by PostgreSQL and SQLite. A repository-owned deployment command validates the target, executes the reviewed SQL in one transaction, and verifies tables, RLS, and grants. Supabase Auth owns credentials; the application database stores a backend-only profile keyed by the Auth UUID.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, asyncpg, aiosqlite, Supabase Auth REST, PostgreSQL, pytest.

---

### Task 1: Native Temporal Model Types

**Files:**
- Modify: `api/db/models.py`
- Modify: `api/db/seed.py`
- Test: `api/tests/test_database_models.py`

- [ ] **Step 1: Write failing metadata and round-trip tests**

Add tests that assert `created_at` and `updated_at` columns are `DateTime(timezone=True)`, `WeeklyReport.week_start/week_end` are `Date`, and `UserPreference.reminder_time` is `Time`. Insert a user and preferences into the isolated SQLite database and assert loaded values are native Python values:

```python
assert isinstance(user.created_at, datetime)
assert user.created_at.tzinfo is not None
assert isinstance(preferences.reminder_time, time)
```

- [ ] **Step 2: Run tests and confirm the old string mappings fail**

Run: `rtk pytest api/tests/test_database_models.py -q`

Expected: failures report `String` columns or string values.

- [ ] **Step 3: Replace temporal string mappings**

Use `Date`, `DateTime(timezone=True)`, and `Time` in `api/db/models.py`. Replace `now_iso()` model defaults with:

```python
def utc_now() -> datetime:
    return datetime.now(timezone.utc)
```

Use native `date`, `datetime`, and `time` annotations. Keep API serialization at router/schema boundaries.

- [ ] **Step 4: Update seed values and run focused tests**

Ensure seed code relies on native model defaults and does not pass ISO strings into temporal columns.

Run: `rtk pytest api/tests/test_database_models.py api/tests/test_api_smoke.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit temporal compatibility**

```bash
rtk git add api/db/models.py api/db/seed.py api/tests/test_database_models.py
rtk git commit -m "fix: align database temporal types"
```

### Task 2: Secure Supabase Schema

**Files:**
- Modify: `docs/database_schema.sql`
- Test: `api/tests/test_database_schema.py`

- [ ] **Step 1: Write failing static schema security tests**

Parse the schema text and assert every application table appears in both an `alter table ... enable row level security` statement and a `revoke all ... from anon, authenticated` statement. Assert the trigger function contains:

```sql
security invoker
set search_path = public, pg_temp
```

Also reject destructive table/data operations with a case-insensitive pattern for `drop table`, `truncate`, and `delete from`.

- [ ] **Step 2: Run tests and confirm security clauses are missing**

Run: `rtk pytest api/tests/test_database_schema.py -q`

Expected: failures identify missing RLS and grants.

- [ ] **Step 3: Harden function and table privileges**

Update `set_updated_at()` to be `security invoker` with explicit `search_path`. Append explicit RLS and revoke statements for all 16 application tables. Revoke direct function execution from `PUBLIC`, `anon`, and `authenticated`.

- [ ] **Step 4: Run schema tests**

Run: `rtk pytest api/tests/test_database_schema.py -q`

Expected: all schema security tests pass.

- [ ] **Step 5: Commit schema hardening**

```bash
rtk git add -f docs/database_schema.sql api/tests/test_database_schema.py
rtk git commit -m "fix: harden supabase database schema"
```

### Task 3: Transactional Schema Deployment Command

**Files:**
- Create: `scripts/setup_database.py`
- Test: `api/tests/test_setup_database.py`

- [ ] **Step 1: Write failing deployment validation tests**

Test pure helpers for URL validation, destructive SQL rejection, expected-table comparison, and redacted errors. Include these cases:

```python
assert validate_driver("postgresql+asyncpg://user:secret@host/db") is None
with pytest.raises(ValueError):
    validate_driver("postgresql://user:secret@host/db")
assert "secret" not in sanitize_error("connection failed: secret", "secret")
```

- [ ] **Step 2: Run tests and confirm the module is absent**

Run: `rtk pytest api/tests/test_setup_database.py -q`

Expected: import failure for `scripts.setup_database`.

- [ ] **Step 3: Implement check/apply/verify modes**

The command reads `settings.database_url`, validates `postgresql+asyncpg`, and supports:

```bash
rtk proxy .venv/bin/python scripts/setup_database.py --check
rtk proxy .venv/bin/python scripts/setup_database.py --apply
rtk proxy .venv/bin/python scripts/setup_database.py --verify
```

`--check` runs `SELECT 1`, reads existing public tables, scans SQL, and refuses unknown collisions. `--apply` executes the complete schema through one `engine.begin()` transaction. `--verify` checks the exact expected table set, `relrowsecurity`, required triggers, and absence of `anon`/`authenticated` table privileges. Output contains counts and object names but no URL or credentials.

- [ ] **Step 4: Run deployment unit tests**

Run: `rtk pytest api/tests/test_setup_database.py -q`

Expected: all deployment helper tests pass.

- [ ] **Step 5: Commit deployment tooling**

```bash
rtk git add scripts/setup_database.py api/tests/test_setup_database.py
rtk git commit -m "feat: add transactional database setup"
```

### Task 4: Idempotent Seed And Supabase User Sync

**Files:**
- Modify: `api/app.py`
- Modify: `api/services/seed_data.py`
- Modify: `api/services/supabase_auth.py`
- Modify: `api/core/errors.py`
- Test: `api/tests/test_database_seed.py`
- Test: `api/tests/test_supabase_user_sync.py`

- [ ] **Step 1: Write failing seed mode tests**

Assert application startup skips `seed_dev_user` when `supabase_auth_enabled()` is true. Call `seed_practice_items` twice and assert the second call returns `0` and the row count is unchanged.

- [ ] **Step 2: Write failing Auth synchronization tests**

Cover new UUID creation, repeat synchronization, invalid payload, and an email collision with a different UUID. The collision must raise a stable API conflict and leave the existing primary key unchanged:

```python
with pytest.raises(ApiError) as exc:
    await sync_supabase_user(db, conflicting_user)
assert exc.value.code == "auth_identity_conflict"
```

- [ ] **Step 3: Run focused tests and confirm failures**

Run: `rtk pytest api/tests/test_database_seed.py api/tests/test_supabase_user_sync.py -q`

Expected: dev seed runs in Supabase mode and email collision behavior is unsafe or undefined.

- [ ] **Step 4: Implement safe startup and profile sync**

In lifespan startup, always seed practice items but only seed a dev user when Supabase Auth is disabled. Validate the Auth payload contains a UUID and email. Never update an existing profile primary key. Raise `ApiError("auth_identity_conflict")` when email belongs to another UUID. Continue to use user metadata only for display name and avatar.

- [ ] **Step 5: Run focused tests**

Run: `rtk pytest api/tests/test_database_seed.py api/tests/test_supabase_user_sync.py api/tests/test_api_smoke.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit seed and identity synchronization**

```bash
rtk git add api/app.py api/services/seed_data.py api/services/supabase_auth.py api/core/errors.py api/tests/test_database_seed.py api/tests/test_supabase_user_sync.py
rtk git commit -m "fix: secure supabase profile seeding"
```

### Task 5: Apply And Verify Supabase Database

**Files:**
- Create: `docs/SUPABASE_DATABASE_EVIDENCE.md`

- [ ] **Step 1: Run the non-mutating preflight**

Run: `rtk proxy .venv/bin/python scripts/setup_database.py --check`

Expected: connection succeeds, driver is asyncpg, SQL audit passes, and the empty database is accepted.

- [ ] **Step 2: Apply schema transactionally**

Run: `rtk proxy .venv/bin/python scripts/setup_database.py --apply`

Expected: 16 application tables are created in one committed transaction.

- [ ] **Step 3: Verify security metadata**

Run: `rtk proxy .venv/bin/python scripts/setup_database.py --verify`

Expected: all expected tables exist, all have RLS enabled, and `anon`/`authenticated` have no direct table privileges.

- [ ] **Step 4: Run seed twice against Supabase**

Invoke `init_db()` and `seed_practice_items()` using the configured remote database. Record first-run total and assert second-run additions equal `0`. Do not seed the local dev user in Supabase mode.

- [ ] **Step 5: Verify Auth profile synchronization**

Use a valid Supabase access token only in process memory, call `/auth/v1/user`, run profile synchronization through the backend, and verify the profile UUID equals the Auth UUID. Redact email and all token values from evidence.

- [ ] **Step 6: Write evidence document**

Record timestamp, PostgreSQL version, table count, RLS count, privilege result, practice-item count, second-seed result, and Auth UUID equality as booleans in `docs/SUPABASE_DATABASE_EVIDENCE.md`. Do not include host, username, email, token, URL, or key values.

- [ ] **Step 7: Run full backend regression tests**

Run: `rtk pytest api/tests -q`

Expected: zero failures.

- [ ] **Step 8: Commit verified evidence**

```bash
rtk git add -f docs/SUPABASE_DATABASE_EVIDENCE.md
rtk git commit -m "docs: record supabase database verification"
```

### Task 6: Final Stage-1 Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Re-run schema verification**

Run: `rtk proxy .venv/bin/python scripts/setup_database.py --verify`

Expected: 16/16 tables secured and no forbidden grants.

- [ ] **Step 2: Re-run backend tests**

Run: `rtk pytest api/tests -q`

Expected: zero failures.

- [ ] **Step 3: Check repository state and secret hygiene**

Run: `rtk git status --short` and `rtk git diff --check`

Expected: only the pre-existing `uv.lock` modification remains; `.env` is ignored and no credentials appear in tracked diffs.
