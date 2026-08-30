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
    _SHA256_HEX,
    LEGACY_CHECKSUM_ALLOWLIST,
    LEGACY_CHECKSUM_SENTINEL,
    SYMBOLIC_CHECKSUM_ALLOWLIST,
    _check_migration_checksums,
    _migration_sql_by_number,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

_live_only = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# STRUCTURAL -- no database.
# --------------------------------------------------------------------------


async def test_no_two_migrations_share_a_number() -> None:
    """The real W40 property: a DUPLICATE number fails the whole deploy,
    including migrations unrelated to the collision.

    This test used to assert `300 not in on_disk` as a tripwire for "299 was
    next-free on 2026-08-31". That pin answered a neighbouring question: it
    could only ever be true until the next migration was written, so it went
    red on the first PR that added one -- not because anything had collided,
    but because the tree had moved on exactly as intended. A guard that fires
    on correct work teaches people to edit the guard, which is how it stops
    being read at all.

    What actually protects the deploy is uniqueness, so that is what is
    asserted here. It holds no matter how high the numbers go, and it goes red
    for the one thing that genuinely breaks -- two files claiming the same
    number, which is precisely what happened on 2026-08-31 when
    299_schema_versions_provenance and 299_garuda_magic_link_binding_owner
    both existed and the second yielded to 301 under the W40 convention.
    """
    # _migration_sql_by_number() is a dict, so it CANNOT express a collision --
    # a second file with the same number silently replaces the first. Reading
    # the directory directly is the point: the duplicate has to survive long
    # enough to be seen.
    on_disk = _migration_sql_by_number()
    directory = next(iter(on_disk.values())).parent
    by_number: dict[int, list[str]] = {}
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        by_number.setdefault(int(path.name[:3]), []).append(path.name)

    collisions = {n: sorted(v) for n, v in by_number.items() if len(v) > 1}
    assert not collisions, (
        "duplicate migration number(s) -- the runner's uniqueness assertion "
        "fails the WHOLE deploy, not just these files. Per W40 the file that "
        "arrived SECOND in git-log time yields and is renamed to the next free "
        "number: " + repr(collisions)
    )

    # And the specific claim this test was originally written to pin, kept
    # because it is still true and still worth knowing.
    assert 299 in by_number, "migration 299 is missing"
    assert by_number[299] == ["299_schema_versions_provenance.sql"]


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


async def test_the_allowlist_is_keyed_on_the_NUMBER_NAME_PAIR_and_carries_reasons() -> None:
    """Keyed on the PAIR, and every entry says why.

    Number-only keying is a hole: a future row renumbered to an allowlisted
    number would skip verification, and the divergence checker compares numbers
    only, so nothing else would notice. Raised as PLAUSIBLE by a blind refuter
    (2026-08-31) and closed rather than argued away.
    """
    assert SYMBOLIC_CHECKSUM_ALLOWLIST, "an empty allowlist allows nothing at all"
    for key, (expected_value, reason) in SYMBOLIC_CHECKSUM_ALLOWLIST.items():
        assert isinstance(expected_value, str) and expected_value
        assert not _SHA256_HEX.match(expected_value), (
            f"{key} pins a real sha256 as its 'symbolic' value; that row should be "
            "verified normally, not allowlisted"
        )
        assert isinstance(key, tuple) and len(key) == 2, f"{key!r} is not a (number, name) pair"
        number, name = key
        assert isinstance(number, int)
        # NOT asserted to end in `.sql`: three of the four names are written by
        # a migration's own hand-rolled INSERT, which omits the suffix, and the
        # allowlist must match what is IN the column rather than what the
        # filename looks like. Asserting `.sql` here would force the allowlist
        # to be wrong in order to be green -- a test bending the subject.
        assert isinstance(name, str) and name
        assert name.startswith(f"{number:03d}_"), f"{name} does not belong to migration {number}"
        assert len(reason) > 40, f"allowlist entry {key} has no written reason"


async def test_every_symbolic_checksum_IN_THE_REAL_TREE_is_accounted_for() -> None:
    """THE REGRESSION FOR THE DEFECT THAT WOULD HAVE FAILED EVERY DEPLOY.

    Some migrations INSERT THEIR OWN ledger row with a symbolic checksum, and
    `_log_migration` then uses `ON CONFLICT DO NOTHING`, so the symbolic value
    is never replaced by a real digest. The first version of this audit
    allowlisted ONE literal by number. Against production it would have
    reported mismatches on the others and FAILED THE `release_command` ON A
    HEALTHY DATABASE -- a verifier turned into an outage.

    A blind cross-family refuter named two (165, 166). Grepping for the CLASS
    rather than those two found `legacy-107-bridge-outbox` as well -- and this
    test, on its first run, found that it is written by migration **194**
    backfilling the row for **107**, which is why the allowlist is keyed on the
    row's (number, name) and not on whoever writes it.

    Pinned as a SET of literals rather than by attributing each to a writer:
    a migration can backfill someone else's row, so "which file contains the
    string" is not the same question as "which row carries it". A new literal
    appearing here fails this test and forces a decision instead of a surprise
    at deploy time.
    """
    import re as _re

    expected = {
        "legacy_fake_checksum",
        "legacy-107-bridge-outbox",
        "tracked-by-migration-165",
        "tracked-by-migration-166",
    }
    literal = _re.compile(r"'((?:legacy|tracked)[a-z0-9_-]{4,})'", _re.IGNORECASE)
    found: set[str] = set()
    for _number, path in sorted(_migration_sql_by_number().items()):
        body = path.read_text(encoding="utf-8")
        for m in literal.finditer(body):
            token = m.group(1)
            if _SHA256_HEX.match(token):
                continue
            if "checksum" in body[max(0, m.start() - 400) : m.start()].lower():
                found.add(token)

    assert found, (
        "premise gone: no symbolic checksum literal found in migrations_v2 at all. "
        "If they were removed, this test guards nothing and the allowlist should "
        "shrink with them."
    )
    assert found <= expected, (
        f"NEW symbolic checksum literal(s) in migrations_v2: {sorted(found - expected)}. "
        "A row carrying one of these is compared against a real sha256 by "
        "_check_migration_checksums and will FAIL THE DEPLOY unless its (number, name) "
        "is added to SYMBOLIC_CHECKSUM_ALLOWLIST."
    )
    covered = {name for _n, name in SYMBOLIC_CHECKSUM_ALLOWLIST}
    assert len(covered) == len(SYMBOLIC_CHECKSUM_ALLOWLIST), "duplicate name in the allowlist"


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


# NEVER the real ledger name. These tests used to CREATE and DROP a table
# literally called `_schema_versions` on whatever `TEST_DATABASE_URL` points
# at -- so a misconfigured DSN would have DESTROYED A REAL MIGRATION LEDGER.
# A blind refuter flagged it (2026-08-31) and it is a fair hit: the checker
# reads `_schema_versions` by name, so the tests pass a table NAME through and
# the name is now a unique per-run scratch table. The cost of being wrong here
# is unbounded; the cost of the indirection is one parameter.
SCRATCH_TABLE = f"_schema_versions_probe_{uuid.uuid4().hex[:10]}"


async def _fresh_versions_table(conn, table: str) -> None:
    assert table != "_schema_versions", (
        "refusing to create/drop the REAL migration ledger from a test"
    )
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
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        path = _migration_sql_by_number()[299]
        honest = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            path.name, 299, honest,
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)), table=SCRATCH_TABLE)
        assert findings == [], f"an honest row produced findings: {findings}"
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
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
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        path = _migration_sql_by_number()[299]
        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            path.name, 299, hashlib.sha256(b"what was actually applied").hexdigest(),
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)), table=SCRATCH_TABLE)
        assert len(findings) == 1, findings
        f = findings[0]
        assert f.code == "migration_checksum_mismatch"
        assert f.severity == "error"
        assert "299" in f.message
        assert f.details["migration_number"] == 299
        assert f.details["stored_checksum"] != f.details["recomputed_checksum"]
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
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
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        allowed = next(iter(LEGACY_CHECKSUM_ALLOWLIST))
        on_disk = _migration_sql_by_number()
        # DELIBERATELY does not assume the allowlisted migration HAS a file.
        # It does not: migrations_v2/ starts at 092, and 001_baseline_v2.sql is
        # written by the adoption path in migration_manager.py without ever
        # existing as a file. The first draft of this test indexed
        # `on_disk[allowed]` and died with KeyError -- which is what exposed
        # that the allowlist was unreachable code in the checker itself.
        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            f"{allowed:03d}_baseline_v2.sql", allowed, LEGACY_CHECKSUM_SENTINEL,
        )
        assert await _check_migration_checksums(_FakeManager(_FakePool(conn)), table=SCRATCH_TABLE) == []

        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            on_disk[299].name, 299, LEGACY_CHECKSUM_SENTINEL,
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)), table=SCRATCH_TABLE)
        assert len(findings) == 1, findings
        assert findings[0].code == "migration_checksum_unallowed_sentinel"
        assert findings[0].details["migration_number"] == 299
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
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
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            f"9999_never_existed_{uuid.uuid4().hex[:8]}.sql", 9999, "deadbeef" * 8,
        )
        assert await _check_migration_checksums(_FakeManager(_FakePool(conn)), table=SCRATCH_TABLE) == []
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
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
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        unlisted = 2
        assert unlisted not in LEGACY_CHECKSUM_ALLOWLIST, "premise gone: 2 got allowlisted"
        assert unlisted not in _migration_sql_by_number(), "premise gone: 2 now has a file"
        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            "002_no_such_file.sql", unlisted, LEGACY_CHECKSUM_SENTINEL,
        )
        findings = await _check_migration_checksums(_FakeManager(_FakePool(conn)), table=SCRATCH_TABLE)
        assert len(findings) == 1, (
            f"an UNLISTED sentinel row was not reported: {findings}. If this is empty, "
            "the file-absent skip has been moved back above the sentinel branch and the "
            "allowlist is dead code again."
        )
        assert findings[0].code == "migration_checksum_unallowed_sentinel"
        assert findings[0].details["migration_number"] == unlisted
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
        await conn.close()


async def test_the_writer_and_the_auditor_hash_THE_SAME_TEXT() -> None:
    """The false-positive trap, pinned — the one that would fail every deploy.

    `migration_base._log_migration` hashes what it is handed, and `apply()`
    hands it `sql`: the FULL file text, ROLLBACK section included. This audit
    recomputes `sha256(path.read_text())` — also the full file. They agree.

    They agree by a coupling that is NOT obvious, and the plausible
    "improvement" breaks it: `apply()` splits the file at
    `-- === ROLLBACK ===` and EXECUTES only the forward half, so hashing
    `split_migration_sql(sql)[0]` looks more correct. If anyone makes that
    change, every stored checksum stops matching every file and this audit
    fails EVERY deploy — a verifier turned into an outage.

    THIS TEST READS THE WRITER'S SOURCE rather than re-deriving the hash.
    A previous version compared `sha256(raw)` to `sha256(raw)` — two spellings
    of one expression — and was a TAUTOLOGY: mutating the writer to hash the
    forward half left all 9 tests GREEN. To test that two things agree, the
    test has to invoke or inspect BOTH, never restate one of them twice.
    """
    import ast
    from pathlib import Path as _P

    from backend.db import migration_base

    src = _P(migration_base.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_calculate_checksum"
    ]
    assert calls, "no _calculate_checksum call found; the writer moved"
    for call in calls:
        assert call.args, "_calculate_checksum called with no argument"
        arg = call.args[0]
        assert isinstance(arg, ast.Name) and arg.id == "sql", (
            "the checksum is no longer computed over the WHOLE file text "
            f"(argument is {ast.dump(arg)}). If this is now the forward-only half, "
            "every stored checksum will stop matching its file and the audit in "
            "schema_audit.py will fail every deploy. Change BOTH sides or neither."
        )

    # And prove the trap is real rather than hypothetical: for a migration that
    # HAS a rollback section, the two candidate texts hash differently.
    on_disk = _migration_sql_by_number()
    assert len(on_disk) > 100, f"suspiciously few migrations discovered: {len(on_disk)}"
    raw_299 = on_disk[299].read_text(encoding="utf-8")
    forward, _ = migration_base.split_migration_sql(raw_299)
    assert forward != raw_299, "299 lost its ROLLBACK section; this test's premise is gone"
    assert (
        hashlib.sha256(forward.encode("utf-8")).hexdigest()
        != hashlib.sha256(raw_299.encode("utf-8")).hexdigest()
    ), "forward-only and full-file hashes coincide; this test could not detect the swap"


@_live_only
async def test_THE_FOUR_REAL_SYMBOLIC_ROWS_PRODUCE_NO_FINDING() -> None:
    """The deploy-breaker, reproduced against a real database.

    This is the test the earlier ones only gestured at. Pinning the literals
    found in the tree does NOT prove the allowlist covers the ROWS they land
    on: mutation-proved, removing 165 from the allowlist left all 10 tests
    green. Only inserting the actual rows and demanding silence discriminates.

    Each row below is the (number, name, checksum) triple that really exists in
    a migrated database -- names read out of the migrations' own INSERT
    statements, three of which omit the `.sql` suffix the runner would have
    written. Against the FIRST version of this audit these produced mismatch
    findings and would have failed the `release_command` on a healthy
    production database.
    """
    import asyncpg

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        real_rows = [
            (1, "001_baseline_v2.sql", "legacy_fake_checksum"),
            (107, "107_bridge_outbox", "legacy-107-bridge-outbox"),
            (165, "165_reconcile_schema_migrations_duplicates", "tracked-by-migration-165"),
            (166, "166_reconcile_client_email_duplicates", "tracked-by-migration-166"),
        ]
        for number, name, checksum in real_rows:
            await conn.execute(
                f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
                "VALUES ($1, $2, $3)",
                name, number, checksum,
            )
        findings = await _check_migration_checksums(
            _FakeManager(_FakePool(conn)), table=SCRATCH_TABLE
        )
        assert findings == [], (
            "the four REAL symbolic ledger rows produced findings: "
            f"{[f.code for f in findings]}. On production this is the "
            "`release_command` failing on a healthy database -- the audit turned "
            "into an outage. Every one of these must be in "
            "SYMBOLIC_CHECKSUM_ALLOWLIST keyed on its (number, name)."
        )
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
        await conn.close()



@_live_only
async def test_an_allowlisted_row_carrying_a_DIFFERENT_symbolic_value_still_errors() -> None:
    """The bypass Kimi K3 named, closed and pinned.

    Keyed on (number, name) ALONE, an allowlist entry exempts a migration
    UNCONDITIONALLY — a waiver that survives the file being tampered with.
    Bound to the VALUE, the entry excuses exactly one known string: any other
    symbolic value on the same row is still an error, and a real sha256 on it is
    verified normally rather than waived.
    """
    import asyncpg

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _fresh_versions_table(conn, SCRATCH_TABLE)
        (number, name), (expected, _reason) = next(iter(SYMBOLIC_CHECKSUM_ALLOWLIST.items()))
        await conn.execute(
            f"INSERT INTO {SCRATCH_TABLE} (migration_name, migration_number, checksum) "
            "VALUES ($1, $2, $3)",
            name, number, expected + "-tampered",
        )
        findings = await _check_migration_checksums(
            _FakeManager(_FakePool(conn)), table=SCRATCH_TABLE
        )
        assert len(findings) == 1, (
            f"an allowlisted row carrying a DIFFERENT symbolic value was waived: {findings}. "
            "The allowlist must excuse one exact value, not a migration forever."
        )
        assert findings[0].code == "migration_checksum_unallowed_sentinel"
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE}")
        await conn.close()
