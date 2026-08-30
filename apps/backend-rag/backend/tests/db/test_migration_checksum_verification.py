"""Guilt + innocence for the migration-checksum audit (L12-PR2, 2026-08-31).

`_schema_versions.checksum` has been written since the table existed and read
back by NOTHING. This file is the corpus for the check that finally reads it,
and it is written to fail if that check is ever weakened -- a verifier with no
adversarial corpus is the same class of artefact as the write-only column it
replaces.

Every test here drives the REAL `_check_migration_checksums` against a REAL
Postgres. There is no mock of the comparison: mocking the thing under test
would prove only that the mock agrees with itself.
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest

from backend.db.schema_audit import (
    LEGACY_CHECKSUM_ALLOWLIST,
    LEGACY_CHECKSUM_SENTINEL,
    _check_migration_checksums,
    _migration_sql_by_number,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

_live_only = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# STRUCTURAL -- no database.
# --------------------------------------------------------------------------


async def test_migration_299_exists_and_is_the_next_free_number() -> None:
    """The spec said 298. 298 was taken by the time this lane ran.

    Pinned as a test rather than a comment because a stale migration number is
    how two migrations collide (W40), and the runner's uniqueness assertion
    fails the WHOLE deploy -- including migrations unrelated to the collision.
    """
    on_disk = _migration_sql_by_number()
    assert 299 in on_disk, "migration 299 is missing"
    assert on_disk[299].name == "299_schema_versions_provenance.sql"
    assert 300 not in on_disk, (
        "a migration numbered 300 appeared; 299 was chosen as next-free on "
        "2026-08-31 and this test is the tripwire for that assumption"
    )


async def test_299_carries_an_explicit_rollback_section() -> None:
    """Every migration in this tree must be reversible, and the reversal must
    undo EXACTLY what the upgrade did -- no more."""
    sql = _migration_sql_by_number()[299].read_text(encoding="utf-8")
    assert "-- === ROLLBACK ===" in sql
    up, _, down = sql.partition("-- === ROLLBACK ===")
    for col in ("applied_as", "applied_via", "runner_version"):
        assert f"ADD COLUMN IF NOT EXISTS {col}" in up, f"{col} not added"
        assert f"DROP COLUMN IF EXISTS {col}" in down, f"{col} not dropped on rollback"
    assert "DROP CONSTRAINT IF EXISTS schema_versions_applied_via_check" in down


async def test_the_sentinel_allowlist_is_by_number_and_carries_reasons() -> None:
    """A blanket "ignore anything that says legacy" would let ANY future row opt
    out of verification by storing that string. The allowlist must therefore be
    keyed by migration NUMBER, and every entry must say why."""
    assert LEGACY_CHECKSUM_ALLOWLIST, "an empty allowlist would silently allow nothing at all"
    for number, reason in LEGACY_CHECKSUM_ALLOWLIST.items():
        assert isinstance(number, int)
        assert len(reason) > 40, f"allowlist entry {number} has no written reason"


# --------------------------------------------------------------------------
# LIVE -- the check against a real database.
# --------------------------------------------------------------------------


class _FakePool:
    """Minimal async-context pool over one real asyncpg connection."""

    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


class _FakeManager:
    def __init__(self, pool):
        self.pool = pool


async def _fresh_versions_table(conn, table: str) -> None:
    await conn.execute(f"DROP TABLE IF EXISTS {table}")
    await conn.execute(
        f"CREATE TABLE {table} (id SERIAL PRIMARY KEY, "
        "migration_name VARCHAR(255) UNIQUE NOT NULL, migration_number INTEGER NOT NULL, "
        "executed_at TIMESTAMPTZ DEFAULT NOW(), checksum VARCHAR(64) NOT NULL, "
        "description TEXT, execution_time_ms INTEGER, rollback_sql TEXT, "
        "applied_by VARCHAR(255) DEFAULT 'system')"
    )


@_live_only
async def test_an_untampered_row_passes(monkeypatch) -> None:
    """INNOCENCE. A row whose stored checksum matches the file raises nothing."""
    import asyncpg


    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, "_schema_versions")
        path = _migration_sql_by_number()[299]
        honest = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        await conn.execute(
            "INSERT INTO _schema_versions (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            path.name, 299, honest,
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)))
        assert findings == [], f"an honest row produced findings: {findings}"
    finally:
        await conn.execute("DROP TABLE IF EXISTS _schema_versions")
        await conn.close()


@_live_only
async def test_a_tampered_row_is_caught_and_names_the_migration_number() -> None:
    """GUILT, and it is the whole point: the file on disk is no longer the text
    that was applied. The finding must NAME the migration number -- an audit
    that says "something is wrong" without saying which migration cannot be
    acted on at 03:00."""
    import asyncpg

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, "_schema_versions")
        path = _migration_sql_by_number()[299]
        await conn.execute(
            "INSERT INTO _schema_versions (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            path.name, 299, hashlib.sha256(b"what was actually applied").hexdigest(),
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)))
        assert len(findings) == 1, findings
        f = findings[0]
        assert f.code == "migration_checksum_mismatch"
        assert f.severity == "error"
        assert "299" in f.message
        assert f.details["migration_number"] == 299
        assert f.details["stored_checksum"] != f.details["recomputed_checksum"]
    finally:
        await conn.execute("DROP TABLE IF EXISTS _schema_versions")
        await conn.close()


@_live_only
async def test_the_allowlisted_sentinel_passes_but_an_unlisted_one_does_not() -> None:
    """The sentinel is real (`migration_manager.py:461` writes it for migration
    1, whose SQL is deliberately never executed) and must stay allowed. Allowing
    it by NUMBER is what stops it from being a hole: the same string on any
    other migration is an error."""
    import asyncpg

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, "_schema_versions")
        allowed = next(iter(LEGACY_CHECKSUM_ALLOWLIST))
        on_disk = _migration_sql_by_number()
        # DELIBERATELY does not assume the allowlisted migration HAS a file.
        # It does not: migrations_v2/ starts at 092, and 001_baseline_v2.sql is
        # written by the adoption path in migration_manager.py without ever
        # existing as a file. The first draft of this test indexed
        # `on_disk[allowed]` and died with KeyError -- which is what exposed
        # that the allowlist was unreachable code in the checker itself.
        await conn.execute(
            "INSERT INTO _schema_versions (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            f"{allowed:03d}_baseline_v2.sql", allowed, LEGACY_CHECKSUM_SENTINEL,
        )
        assert await _check_migration_checksums(_FakeManager(_FakePool(conn))) == []

        await conn.execute(
            "INSERT INTO _schema_versions (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            on_disk[299].name, 299, LEGACY_CHECKSUM_SENTINEL,
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)))
        assert len(findings) == 1, findings
        assert findings[0].code == "migration_checksum_unallowed_sentinel"
        assert findings[0].details["migration_number"] == 299
    finally:
        await conn.execute("DROP TABLE IF EXISTS _schema_versions")
        await conn.close()


@_live_only
async def test_a_row_whose_file_is_gone_is_left_to_the_divergence_check() -> None:
    """Not this check's job. `_check_tracking_divergence` already owns orphan
    rows; reporting them here too would make ONE schema problem produce TWO
    findings with different names, which is how an operator learns to ignore
    both."""
    import asyncpg

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, "_schema_versions")
        await conn.execute(
            "INSERT INTO _schema_versions (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            f"9999_never_existed_{uuid.uuid4().hex[:8]}.sql", 9999, "deadbeef" * 8,
        )
        assert await _check_migration_checksums(_FakeManager(_FakePool(conn))) == []
    finally:
        await conn.execute("DROP TABLE IF EXISTS _schema_versions")
        await conn.close()


@_live_only
async def test_an_UNLISTED_sentinel_with_NO_FILE_is_still_an_error() -> None:
    """The regression guard for the defect this file found in its own subject --
    and it is written to be the ONE case the two orderings disagree about.

    The checker originally skipped rows whose migration file is absent BEFORE
    it looked at the sentinel, which made the whole allowlist unreachable
    (W116: a branch that reads like a guard and can never fire).

    The obvious test for that -- assert an ALLOWLISTED file-less row passes --
    is a TAUTOLOGY, and the first draft of this test was exactly that: under
    the correct ordering the allowlist passes the row, under the broken
    ordering the row is skipped, and BOTH produce `[]`. Mutation-proved: the
    broken ordering left all 8 tests green.

    An UNLISTED sentinel on a file-less migration is the discriminating case.
    Correct ordering -> the sentinel is judged on the ROW and this is an error.
    Broken ordering -> the row is skipped for having no file and NOTHING is
    reported. The sentinel means "this SQL was never executed"; a row claiming
    that without being on the allowlist is precisely what must not pass, and
    whether a file happens to exist has no bearing on it.
    """
    import asyncpg

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, "_schema_versions")
        unlisted = 2
        assert unlisted not in LEGACY_CHECKSUM_ALLOWLIST, "premise gone: 2 got allowlisted"
        assert unlisted not in _migration_sql_by_number(), "premise gone: 2 now has a file"
        await conn.execute(
            "INSERT INTO _schema_versions (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            "002_no_such_file.sql", unlisted, LEGACY_CHECKSUM_SENTINEL,
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)))
        assert len(findings) == 1, (
            f"an UNLISTED sentinel row was not reported: {findings}. If this is empty, "
            "the file-absent skip has been moved back above the sentinel branch and the "
            "allowlist is dead code again."
        )
        assert findings[0].code == "migration_checksum_unallowed_sentinel"
        assert findings[0].details["migration_number"] == unlisted
    finally:
        await conn.execute("DROP TABLE IF EXISTS _schema_versions")
        await conn.close()
