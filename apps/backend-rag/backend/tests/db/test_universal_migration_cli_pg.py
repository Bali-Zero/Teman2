"""Real-engine behaviour of the migration CLI contract, on a DISPOSABLE cluster.

Drives the actual `backend/db/migrate.py` commands over the actual
`MigrationManager` / `BaseMigration` path -- advisory lock, rollback-marker
split, full-file checksum, both ledgers -- against synthetic SQL files in a
temporary directory, on a database that must prove it is the mandate's
disposable target before any DDL runs.

TARGET PROOF (fail-closed, never a shared database)
---------------------------------------------------
* `NUZ_UNIVERSAL_PG_DSN`        -- the ONLY way to reach a database here. No
                                   default exists: unset means SKIP with the
                                   reason, not "fall back to TEST_DATABASE_URL".
* `NUZ_UNIVERSAL_PG_SYSTEM_ID`  -- must equal `pg_control_system().
                                   system_identifier` of the cluster behind the
                                   DSN. Unset means SKIP; a mismatch means FAIL
                                   before any write.
* `current_user` must be `universal_db_test_owner` and `current_database()`
  must be `universal_db_test`; anything else FAILS before any write.

Isolation inside the disposable database: every test owns its own migration
numbers (one block per test) and uuid-suffixed table names, patches the
runner's discovery directory to a `tmp_path`, and deletes its ledger rows and
tables in `finally`, so a failure cannot poison the next test or the next run.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from backend.db import migrate, migration_base, migration_manager
from backend.db.migration_base import BaseMigration
from backend.db.migration_manager import MigrationManager

pytestmark = [pytest.mark.integration, pytest.mark.database]

_DSN_ENV = "NUZ_UNIVERSAL_PG_DSN"
_SYSID_ENV = "NUZ_UNIVERSAL_PG_SYSTEM_ID"
EXPECTED_USER = "universal_db_test_owner"
EXPECTED_DATABASE = "universal_db_test"

COUNTED = migrate.APPLIED_LINE_PREFIX
LEDGERS = ("schema_migrations", "_schema_versions")


def _count_applied_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if COUNTED in line)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def disposable_dsn(monkeypatch: pytest.MonkeyPatch) -> str:
    """The DSN of the proven-disposable database, or skip/fail -- never a default."""
    dsn = os.environ.get(_DSN_ENV, "").strip()
    expected_sysid = os.environ.get(_SYSID_ENV, "").strip()
    if not dsn:
        pytest.skip(
            f"{_DSN_ENV} not set: no disposable {EXPECTED_DATABASE} target "
            "(this suite never defaults to a shared database)"
        )
    if not expected_sysid:
        pytest.skip(f"{_SYSID_ENV} not set: cannot prove the target cluster is disposable")

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:  # the DSN itself is never echoed
        pytest.fail(f"{_DSN_ENV} is set but the target is unreachable ({type(exc).__name__})")
    try:
        row = await conn.fetchrow(
            "SELECT current_user AS usr, current_database() AS db, "
            "(SELECT system_identifier FROM pg_control_system())::text AS sysid"
        )
    except Exception as exc:
        pytest.fail(f"could not read the target identity before writing ({type(exc).__name__})")
    finally:
        await conn.close()

    problems: list[str] = []
    if row["usr"] != EXPECTED_USER:
        problems.append(f"current_user={row['usr']!r}, expected {EXPECTED_USER!r}")
    if row["db"] != EXPECTED_DATABASE:
        problems.append(f"current_database={row['db']!r}, expected {EXPECTED_DATABASE!r}")
    if row["sysid"] != expected_sysid:
        problems.append("pg_control_system().system_identifier differs from " + _SYSID_ENV)
    if problems:
        pytest.fail(
            "refusing to write: disposable-target identity mismatch: " + "; ".join(problems)
        )

    # Single-DSN (legacy) runner mode regardless of the ambient environment: the
    # disposable owner is not `backend_rag_v2`, so dedicated-role checks would
    # refuse it, and that is not what this suite tests.
    monkeypatch.setattr(migration_base.settings, "migration_database_url", None)
    return dsn


@pytest.fixture
def schema_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A disposable `migrations_v2/` the REAL runner discovers from.

    `MigrationManager.discover_migrations` derives the directory from its
    module `__file__`; `BaseMigration` resolves SQL files against the class
    attribute `MIGRATIONS_DIR`. Both are redirected, nothing in production
    code changes for this.
    """
    root = tmp_path / "runner"
    root.mkdir()
    directory = root / "migrations_v2"
    directory.mkdir()
    monkeypatch.setattr(migration_manager, "__file__", str(root / "migration_manager.py"))
    monkeypatch.setattr(BaseMigration, "MIGRATIONS_DIR", directory)
    return directory


@pytest.fixture(autouse=True)
def _boundary_cleanup():
    """Tests that install the CLI reporting boundary leave no filter behind."""
    yield
    migrate.remove_cli_reporting_boundary()


def _write_migration(
    directory: Path, number: int, stem: str, forward: str, rollback: str | None
) -> Path:
    text = forward.rstrip() + "\n"
    if rollback is not None:
        text += "\n-- === ROLLBACK ===\n" + rollback.rstrip() + "\n"
    path = directory / f"{number:03d}_{stem}.sql"
    path.write_text(text, encoding="utf-8")
    return path


def _table_name() -> str:
    return f"udb_{uuid.uuid4().hex[:10]}"


async def _table_exists(conn: asyncpg.Connection, table: str) -> bool:
    return bool(await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{table}"))


async def _ledger_rows(conn: asyncpg.Connection, number: int) -> dict[str, list[asyncpg.Record]]:
    rows: dict[str, list[asyncpg.Record]] = {}
    for ledger in LEDGERS:
        if await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{ledger}"):
            rows[ledger] = await conn.fetch(
                f"SELECT migration_name, migration_number, checksum, rollback_sql "
                f"FROM {ledger} WHERE migration_number = $1",
                number,
            )
        else:
            rows[ledger] = []
    return rows


async def _cleanup(conn: asyncpg.Connection, numbers: list[int], tables: list[str]) -> None:
    for ledger in LEDGERS:
        if await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{ledger}"):
            await conn.execute(
                f"DELETE FROM {ledger} WHERE migration_number = ANY($1::int[])", numbers
            )
    for table in tables:
        await conn.execute(f"DROP TABLE IF EXISTS public.{table}")


# ---------------------------------------------------------------------------
# apply-all through the CLI
# ---------------------------------------------------------------------------


async def test_forward_only_execution_and_ledger_parity(disposable_dsn, schema_dir, capsys) -> None:
    """The rollback section is NOT executed; both ledgers get the same row;
    the stored checksum is the full-file digest; the counted line appears once."""
    number, table = 901, _table_name()
    path = _write_migration(
        schema_dir,
        number,
        "udb_forward",
        f"CREATE TABLE public.{table} (id int PRIMARY KEY);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert len(await manager.discover_migrations()) == 1, "discovery is not isolated"
            assert await migrate.cmd_apply(manager) is True
        out = capsys.readouterr().out
        assert _count_applied_lines(out) == 1
        assert "✅ Applied: 1 migrations" in out
        assert "Summary: applied=1 skipped=0 failed=0" in out

        assert await _table_exists(conn, table), "rollback section ran inside the apply"

        rows = await _ledger_rows(conn, number)
        full_digest = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        for ledger in LEDGERS:
            assert len(rows[ledger]) == 1, f"{ledger} has {len(rows[ledger])} rows"
            assert rows[ledger][0]["migration_name"] == "901_udb_forward"
            assert rows[ledger][0]["checksum"] == full_digest, (
                "checksum is not the full-file digest"
            )
            assert "DROP TABLE" in (rows[ledger][0]["rollback_sql"] or "")
    finally:
        await _cleanup(conn, [number], [table])
        await conn.close()


async def test_repeat_application_is_idempotent(disposable_dsn, schema_dir, capsys) -> None:
    number, table = 902, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_repeat",
        f"CREATE TABLE public.{table} (id int);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager) is True
            capsys.readouterr()
            assert await migrate.cmd_apply(manager) is True
        out = capsys.readouterr().out
        assert _count_applied_lines(out) == 0
        assert "✅ Applied: 0 migrations" in out
        rows = await _ledger_rows(conn, number)
        assert all(len(rows[ledger]) == 1 for ledger in LEDGERS)
        assert await _table_exists(conn, table)
    finally:
        await _cleanup(conn, [number], [table])
        await conn.close()


async def test_dry_run_applies_nothing(disposable_dsn, schema_dir, capsys) -> None:
    number, table = 903, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_dry",
        f"CREATE TABLE public.{table} (id int);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager, dry_run=True) is True
        out = capsys.readouterr().out
        assert "DRY RUN: 1 pending migration(s) would be applied" in out
        assert "   ~ Would apply migration 903 (903_udb_dry.sql)" in out
        assert _count_applied_lines(out) == 0
        assert not await _table_exists(conn, table)
        rows = await _ledger_rows(conn, number)
        assert all(len(rows[ledger]) == 0 for ledger in LEDGERS)
    finally:
        await _cleanup(conn, [number], [table])
        await conn.close()


async def test_failed_ddl_is_atomic_and_unreported_on_any_surface(
    disposable_dsn, schema_dir, capsys, caplog
) -> None:
    """A failing second statement rolls back the first; no ledger row; the
    server's error text (which names the unknown type) reaches neither
    stdout, nor stderr, nor the log stream once the CLI boundary is up --
    the real runner logs `str(e)` at ERROR and that is what the boundary
    exists for."""
    number, table = 904, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_atomic",
        f"CREATE TABLE public.{table} (id int);\n"
        f"ALTER TABLE public.{table} ADD COLUMN c udb_no_such_type_xyz;",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    caplog.set_level(logging.INFO)
    migrate.install_cli_reporting_boundary()
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager) is False
        captured = capsys.readouterr()
        out = captured.out
        assert "   ! Migration 904 FAILED" in out
        assert "❌ Failed: 1 migrations" in out
        assert _count_applied_lines(out) == 0
        assert "Failed to apply migration 904: MigrationError" in caplog.text
        for surface in (out, captured.err, caplog.text):
            assert "udb_no_such_type_xyz" not in surface
            assert "Traceback" not in surface
        assert not await _table_exists(conn, table), "first statement survived a failed migration"
        rows = await _ledger_rows(conn, number)
        assert all(len(rows[ledger]) == 0 for ledger in LEDGERS)
    finally:
        await _cleanup(conn, [number], [table])
        await conn.close()


async def test_two_concurrent_runners_serialize_on_the_advisory_lock(
    disposable_dsn, schema_dir
) -> None:
    """Two managers race `apply_all_pending`; every migration applies exactly
    once, nothing fails, each ledger holds one row per number."""
    n1, n2 = 905, 906
    t1, t2 = _table_name(), _table_name()
    _write_migration(
        schema_dir,
        n1,
        "udb_race_a",
        f"SELECT pg_sleep(1.5);\nCREATE TABLE public.{t1} (id int);",
        f"DROP TABLE IF EXISTS public.{t1};",
    )
    _write_migration(
        schema_dir,
        n2,
        "udb_race_b",
        f"CREATE TABLE public.{t2} (id int);",
        f"DROP TABLE IF EXISTS public.{t2};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    m1 = MigrationManager(database_url=disposable_dsn)
    m2 = MigrationManager(database_url=disposable_dsn)
    try:
        await m1.connect()
        await m2.connect()
        r1, r2 = await asyncio.gather(m1.apply_all_pending(), m2.apply_all_pending())
        assert not r1["failed"] and not r2["failed"], (r1, r2)
        assert set(r1["applied"]).isdisjoint(r2["applied"]), "a migration applied twice"
        assert set(r1["applied"]) | set(r2["applied"]) == {n1, n2}
        for number in (n1, n2):
            rows = await _ledger_rows(conn, number)
            assert all(len(rows[ledger]) == 1 for ledger in LEDGERS), rows
        assert await _table_exists(conn, t1) and await _table_exists(conn, t2)
    finally:
        await m1.close()
        await m2.close()
        await _cleanup(conn, [n1, n2], [t1, t2])
        await conn.close()


async def test_rollback_is_reversible_with_synthetic_data(
    disposable_dsn, schema_dir, capsys
) -> None:
    """Apply, insert synthetic rows, roll back (table gone, both ledgers
    cleared), re-apply (table back, empty, one row per ledger again)."""
    number, table = 907, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_rollback",
        f"CREATE TABLE public.{table} (id int PRIMARY KEY);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager) is True
            await conn.execute(f"INSERT INTO public.{table} (id) VALUES (1), (2), (3)")
            assert await conn.fetchval(f"SELECT count(*) FROM public.{table}") == 3

            assert await manager.rollback_migration("907_udb_rollback") is True
            assert not await _table_exists(conn, table), "rollback SQL did not run"
            rows = await _ledger_rows(conn, number)
            assert all(len(rows[ledger]) == 0 for ledger in LEDGERS), "a ledger still records it"

            capsys.readouterr()
            assert await migrate.cmd_apply(manager) is True
        out = capsys.readouterr().out
        assert _count_applied_lines(out) == 1
        assert await _table_exists(conn, table)
        assert await conn.fetchval(f"SELECT count(*) FROM public.{table}") == 0
        rows = await _ledger_rows(conn, number)
        assert all(len(rows[ledger]) == 1 for ledger in LEDGERS)
    finally:
        await _cleanup(conn, [number], [table])
        await conn.close()


# ---------------------------------------------------------------------------
# apply N through the CLI
# ---------------------------------------------------------------------------


async def test_apply_single_refuses_earlier_pending_then_applies_in_order(
    disposable_dsn, schema_dir, capsys
) -> None:
    n1, n2 = 908, 909
    t1, t2 = _table_name(), _table_name()
    _write_migration(
        schema_dir,
        n1,
        "udb_one",
        f"CREATE TABLE public.{t1} (id int);",
        f"DROP TABLE IF EXISTS public.{t1};",
    )
    _write_migration(
        schema_dir,
        n2,
        "udb_two",
        f"CREATE TABLE public.{t2} (id int);",
        f"DROP TABLE IF EXISTS public.{t2};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager, migration_number=n2) is False
            out = capsys.readouterr().out
            assert (
                "   ✗ Migration 909 refused: 1 earlier pending migration(s) must be applied first: 908"
                in out
            )
            assert "Summary: applied=0 skipped=0 failed=0 refused=1" in out
            assert _count_applied_lines(out) == 0
            assert not await _table_exists(conn, t2) and not await _table_exists(conn, t1)
            assert all(len(r) == 0 for r in (await _ledger_rows(conn, n2)).values())

            assert await migrate.cmd_apply(manager, migration_number=n1) is True
            assert await migrate.cmd_apply(manager, migration_number=n2) is True
        out = capsys.readouterr().out
        assert _count_applied_lines(out) == 2
        assert await _table_exists(conn, t1) and await _table_exists(conn, t2)
        for number in (n1, n2):
            rows = await _ledger_rows(conn, number)
            assert all(len(rows[ledger]) == 1 for ledger in LEDGERS)
    finally:
        await _cleanup(conn, [n1, n2], [t1, t2])
        await conn.close()


async def test_apply_single_unknown_number_is_refused_without_writes(
    disposable_dsn, schema_dir, capsys
) -> None:
    number, table = 910, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_known",
        f"CREATE TABLE public.{table} (id int);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager, migration_number=999) is False
        out = capsys.readouterr().out
        assert (
            "   ✗ Migration 999 refused: no file with this number (on disk: 1 file(s), 910..910)"
            in out
        )
        assert _count_applied_lines(out) == 0
        assert not await _table_exists(conn, table)
        assert all(len(r) == 0 for r in (await _ledger_rows(conn, 999)).values())
        assert all(len(r) == 0 for r in (await _ledger_rows(conn, number)).values())
    finally:
        await _cleanup(conn, [number, 999], [table])
        await conn.close()


async def test_apply_single_already_applied_is_skipped_and_dry_run_writes_nothing(
    disposable_dsn, schema_dir, capsys
) -> None:
    n1, n2 = 911, 912
    t1, t2 = _table_name(), _table_name()
    _write_migration(
        schema_dir,
        n1,
        "udb_done",
        f"CREATE TABLE public.{t1} (id int);",
        f"DROP TABLE IF EXISTS public.{t1};",
    )
    _write_migration(
        schema_dir,
        n2,
        "udb_next",
        f"CREATE TABLE public.{t2} (id int);",
        f"DROP TABLE IF EXISTS public.{t2};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager, migration_number=n1) is True
            capsys.readouterr()

            assert await migrate.cmd_apply(manager, migration_number=n1) is True
            out = capsys.readouterr().out
            assert "   ~ Migration 911 skipped (already applied)" in out
            assert _count_applied_lines(out) == 0
            assert all(len(r) == 1 for r in (await _ledger_rows(conn, n1)).values())

            assert await migrate.cmd_apply(manager, migration_number=n2, dry_run=True) is True
            out = capsys.readouterr().out
            assert "   ~ Would apply migration 912 (912_udb_next.sql)" in out
            assert _count_applied_lines(out) == 0
            assert not await _table_exists(conn, t2)
            assert all(len(r) == 0 for r in (await _ledger_rows(conn, n2)).values())

            # status / list read the same ledgers the runner wrote.
            assert await migrate.cmd_status(manager) is True
            assert await migrate.cmd_list(manager) is True
        out = capsys.readouterr().out
        assert "Migration status: files=2 applied=1 pending=1" in out
        assert "Pending: 1 migration(s): 912" in out
        assert "[applied] 911 911_udb_done.sql" in out
        assert "[pending] 912 912_udb_next.sql" in out
    finally:
        await _cleanup(conn, [n1, n2], [t1, t2])
        await conn.close()


async def test_duplicate_numbers_on_disk_refuse_every_apply(
    disposable_dsn, schema_dir, capsys, monkeypatch
) -> None:
    """Two files sharing a prefix: the runner raises before any SQL, the CLI
    prints one clean diagnostic, exit code 1, nothing written."""
    number, t1, t2 = 913, _table_name(), _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_dup_a",
        f"CREATE TABLE public.{t1} (id int);",
        f"DROP TABLE IF EXISTS public.{t1};",
    )
    _write_migration(
        schema_dir,
        number,
        "udb_dup_b",
        f"CREATE TABLE public.{t2} (id int);",
        f"DROP TABLE IF EXISTS public.{t2};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    monkeypatch.setattr(migrate, "resolve_migration_dsn", lambda: disposable_dsn)
    monkeypatch.setattr(migrate, "MigrationManager", lambda *a, **k: manager)
    try:
        # `main` owns its own event loop, so run it off this one.
        code = await asyncio.to_thread(migrate.main, ["apply", str(number)])
        assert code == 1
        captured = capsys.readouterr()
        assert "❌ apply failed: MigrationError reason=duplicate_migration_numbers" in captured.out
        assert "udb_dup_a" not in captured.out
        assert "Traceback" not in captured.out
        assert _count_applied_lines(captured.out) == 0
        assert not await _table_exists(conn, t1) and not await _table_exists(conn, t2)
        assert all(len(r) == 0 for r in (await _ledger_rows(conn, number)).values())
    finally:
        await _cleanup(conn, [number], [t1, t2])
        await conn.close()


# ---------------------------------------------------------------------------
# Advisory lock held by another session (Kimi round 3, F1)
# ---------------------------------------------------------------------------


async def test_apply_all_is_refused_while_another_session_holds_the_lock(
    disposable_dsn, schema_dir, capsys
) -> None:
    """A second session holds advisory lock 73491: `apply-all` applies nothing,
    prints the refusal, ends with `refused=1`, returns False (exit 1). After
    the holder releases, the same command applies the file."""
    number, table = 914, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_lock_all",
        f"CREATE TABLE public.{table} (id int);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    holder = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        await holder.execute("SELECT pg_advisory_lock($1)", MigrationManager._APPLY_ALL_LOCK_ID)
        async with manager:
            assert await migrate.cmd_apply(manager) is False
            out = capsys.readouterr().out
            assert (
                "   ✗ apply-all refused: another migration runner holds advisory lock 73491" in out
            )
            assert "Summary: applied=0 skipped=0 failed=0 refused=1" in out
            assert _count_applied_lines(out) == 0
            assert not await _table_exists(conn, table)
            assert all(len(r) == 0 for r in (await _ledger_rows(conn, number)).values())

            # A dry run under the held lock is refused too, never an empty success.
            assert await migrate.cmd_apply(manager, dry_run=True) is False
            out = capsys.readouterr().out
            assert "refused=1" in out
            assert _count_applied_lines(out) == 0

            await holder.execute(
                "SELECT pg_advisory_unlock($1)", MigrationManager._APPLY_ALL_LOCK_ID
            )
            assert await migrate.cmd_apply(manager) is True
        out = capsys.readouterr().out
        assert _count_applied_lines(out) == 1
        assert "Summary: applied=1 skipped=0 failed=0 refused=0" in out
        assert await _table_exists(conn, table)
    finally:
        await holder.close()
        await _cleanup(conn, [number], [table])
        await conn.close()


async def test_apply_single_is_refused_while_another_session_holds_the_lock(
    disposable_dsn, schema_dir, capsys
) -> None:
    number, table = 915, _table_name()
    _write_migration(
        schema_dir,
        number,
        "udb_lock_one",
        f"CREATE TABLE public.{table} (id int);",
        f"DROP TABLE IF EXISTS public.{table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    holder = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        await holder.execute("SELECT pg_advisory_lock($1)", MigrationManager._APPLY_ALL_LOCK_ID)
        async with manager:
            assert await migrate.cmd_apply(manager, migration_number=number) is False
        out = capsys.readouterr().out
        assert (
            "   ✗ Migration 915 refused: another migration runner holds advisory lock 73491" in out
        )
        assert "Summary: applied=0 skipped=0 failed=0 refused=1" in out
        assert _count_applied_lines(out) == 0
        assert not await _table_exists(conn, table)
    finally:
        await holder.close()
        await _cleanup(conn, [number], [table])
        await conn.close()


async def test_apply_single_on_a_ledger_only_number_is_skipped(
    disposable_dsn, schema_dir, capsys
) -> None:
    """A number recorded in `_schema_versions` with no file on disk (the
    production shape for every pre-092 row) is already applied: skipped,
    exit 0, nothing written."""
    number = 916
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            await manager.get_applied_migrations()  # ensures the ledger table exists
            await conn.execute(
                "INSERT INTO _schema_versions (migration_name, migration_number, checksum, description) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT (migration_name) DO NOTHING",
                "916_ledger_only_probe",
                number,
                "0" * 64,
                "synthetic ledger-only row",
            )
            assert await migrate.cmd_apply(manager, migration_number=number) is True
        out = capsys.readouterr().out
        assert "   ~ Migration 916 skipped (already applied)" in out
        assert "Summary: applied=0 skipped=1 failed=0 refused=0" in out
        assert _count_applied_lines(out) == 0
        rows = await _ledger_rows(conn, number)
        assert len(rows["_schema_versions"]) == 1
        assert len(rows["schema_migrations"]) == 0, "a skip must not reconcile ledgers"
    finally:
        await _cleanup(conn, [number], [])
        await conn.close()


@pytest.mark.asyncio
async def test_apply_single_enforces_declared_dependency_missing_from_disk(
    disposable_dsn, schema_dir, capsys
) -> None:
    """A declaration remains binding when the prerequisite SQL file is absent."""
    prerequisite, number = 950, 951
    first_table, dependent_table = _table_name(), _table_name()
    _write_migration(
        schema_dir, number, "udb_dependent",
        f"-- depends: {prerequisite}\nCREATE TABLE public.{dependent_table} (id int);",
        f"DROP TABLE IF EXISTS public.{dependent_table};",
    )
    conn = await asyncpg.connect(disposable_dsn)
    manager = MigrationManager(database_url=disposable_dsn)
    try:
        async with manager:
            assert await migrate.cmd_apply(manager, migration_number=number) is False
            assert _count_applied_lines(capsys.readouterr().out) == 0
            assert not await _table_exists(conn, dependent_table)
            assert not await _table_exists(conn, first_table)
            for candidate in (prerequisite, number):
                assert all(not rows for rows in (await _ledger_rows(conn, candidate)).values())

            prerequisite_path = _write_migration(
                schema_dir, prerequisite, "udb_prerequisite",
                f"CREATE TABLE public.{first_table} (id int);",
                f"DROP TABLE IF EXISTS public.{first_table};",
            )
            assert await migrate.cmd_apply(manager, migration_number=prerequisite) is True
            prerequisite_path.unlink()
            assert await migrate.cmd_apply(manager, migration_number=number) is True
            assert _count_applied_lines(capsys.readouterr().out) == 2
        assert await _table_exists(conn, first_table)
        assert await _table_exists(conn, dependent_table)
        for candidate in (prerequisite, number):
            rows = await _ledger_rows(conn, candidate)
            assert all(len(rows[ledger]) == 1 for ledger in LEDGERS)
    finally:
        await _cleanup(conn, [prerequisite, number], [first_table, dependent_table])
        await conn.close()
