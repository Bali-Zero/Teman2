"""Tripwire for the failure mode diagnosed on PR #4901/#4902 (2026-08-25):
migration 285 added a THIRD foreign key onto
``visa_decision_retention_policies`` (264) — after 281's two — and was never
taught to ``conftest.py``'s ``unwind_garuda_voa_retention_fk`` /
``restore_garuda_voa_retention_fk`` pair. 264's rollback drops that table
with no ``CASCADE`` (deliberately — see this directory's 252/264 fixture
docstrings), so any test that rolls 264 back went red with
``asyncpg.exceptions.DependentObjectsStillExistError`` the moment 285 merged
— on files that never touch GARUDA-VOA at all
(``test_evaluate_endpoint.py``, ``test_shadow_evidence.py``). The failure
mode is SILENCE: nothing at authoring time told 285's author that a shared
test-fixture registry in a different product's directory needed a one-line
update.

This test makes that silence loud. It statically scans every migration
under ``migrations_v2/`` for a fresh FK onto
``visa_decision_retention_policies`` and asserts every one it finds
(other than 264 itself, which owns the table) is registered in
``conftest.py``'s ``_GARUDA_VOA_RETENTION_FK_DEPENDENTS``. It does not touch
a database — a missing registration is a static, file-content fact, and this
test is meant to fail at PR-authoring time for the NEXT such migration, not
at merge time three lanes away from the one that added it.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.tests.services.visa_engine.conftest import _GARUDA_VOA_RETENTION_FK_DEPENDENTS

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "db" / "migrations_v2"

# Matches e.g. "REFERENCES public.visa_decision_retention_policies (id)" —
# case-sensitive on purpose: this repo's migrations spell the table name
# consistently, and a differently-cased reference would itself be worth a
# human's eyes rather than this regex silently accepting it.
_FK_PATTERN = re.compile(
    r"REFERENCES\s+public\.visa_decision_retention_policies\b"
)

# The migration that OWNS the table. It legitimately contains no
# "REFERENCES ... visa_decision_retention_policies" of its own (it only
# ever appears on the *referencing* side elsewhere) — excluded from the
# "must be registered" scan by construction, not by an allowlist entry.
_OWNER_MIGRATION_NUMBER = 264


def _migration_number(path: Path) -> int | None:
    match = re.match(r"^(\d+)_", path.name)
    return int(match.group(1)) if match else None


def test_every_fk_onto_the_retention_policy_table_is_registered():
    registered_numbers = {entry[0] for entry in _GARUDA_VOA_RETENTION_FK_DEPENDENTS}

    found_but_unregistered: list[str] = []
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        number = _migration_number(path)
        if number is None or number == _OWNER_MIGRATION_NUMBER:
            continue
        text = path.read_text(encoding="utf-8")
        if _FK_PATTERN.search(text) and number not in registered_numbers:
            found_but_unregistered.append(path.name)

    assert not found_but_unregistered, (
        "migration(s) "
        f"{found_but_unregistered} add a foreign key onto "
        "visa_decision_retention_policies (264) but are not registered in "
        "conftest.py's _GARUDA_VOA_RETENTION_FK_DEPENDENTS — add a one-line "
        "entry there (see unwind_garuda_voa_retention_fk's docstring), or "
        "this repo's other visa_engine tests that roll 264 back in their "
        "fixtures will go red with DependentObjectsStillExistError the "
        "moment your migration merges, on files that never touch your "
        "product at all."
    )


def test_the_registry_itself_only_names_files_that_still_exist_and_still_match():
    """A registry entry that survives after its migration is renamed, or
    whose marker column gets renamed in a later migration, is a silent dead
    entry — this asserts each one is still real, not just historically true."""
    for number, filename, marker_table, marker_column in _GARUDA_VOA_RETENTION_FK_DEPENDENTS:
        path = _MIGRATIONS_DIR / filename
        assert path.is_file(), f"registered migration file missing: {filename}"
        assert path.name.startswith(f"{number}_"), (
            f"registry entry number {number} does not match its own filename {filename!r}"
        )
        text = path.read_text(encoding="utf-8")
        # Not every dependent migration CREATEs its marker table — 281
        # widens a table an earlier migration already created (ALTER TABLE
        # ... ADD COLUMN). What every registered entry MUST do is add
        # ``marker_column`` onto ``marker_table`` as an FK onto the
        # retention-policy table — checked structurally, not by assuming
        # any one DDL verb.
        assert re.search(rf"\bpublic\.{re.escape(marker_table)}\b", text), (
            f"{filename} no longer mentions table {marker_table!r} the registry uses as its marker"
        )
        assert marker_column in text, (
            f"{filename} no longer mentions column {marker_column!r} the registry uses as its marker"
        )
        assert _FK_PATTERN.search(text), (
            f"{filename} is registered as an FK dependent but no longer references "
            "visa_decision_retention_policies at all"
        )


# ---------------------------------------------------------------------------
# Regression test for the restore-asymmetry the team-lead found (2026-08-25,
# PR #4902 follow-up, independently converged with a Kimi K3 finding):
# restore_garuda_voa_retention_fk used to unconditionally replay every
# registered migration's forward SQL, while unwind_garuda_voa_retention_fk
# only rolls back entries whose marker is present -- correct with ONE
# registered entry (the aggregate bool was unambiguous), broken once the
# registry generalized to two-or-more. This proves the fix: restore now
# probes for absence per-entry (the same marker check unwind already used)
# and only re-applies what is actually missing.
# ---------------------------------------------------------------------------

import pytest

from backend.db.migration_base import split_migration_sql
from backend.tests.services.visa_engine.conftest import (
    restore_garuda_voa_retention_fk,
)


async def _marker_present(conn, marker_table: str, marker_column: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2",
            marker_table,
            marker_column,
        )
    )


@pytest.mark.asyncio
async def test_restore_only_reapplies_the_entry_that_was_actually_unwound(db_pool):
    """Manually unwind ONLY 285 (285's rollback drops garuda_magic_link_tokens
    and friends; it does not touch anything 281 owns), leaving 281 fully
    applied -- a deliberately SKEWED state unwind_garuda_voa_retention_fk
    itself would never produce (it always unwinds every applied entry it
    finds), used here purely to prove restore's OWN per-entry behaviour in
    isolation. Before the fix, an unconditional restore would try to
    re-apply 281's forward SQL onto a schema where 281 is already live --
    281's forward does plain `ALTER TABLE ... ADD COLUMN policy_scope`
    (no `IF NOT EXISTS`), so that would raise `DuplicateColumnError`, not
    silently no-op. After the fix, restore probes 281's marker, finds it
    present, and leaves it alone -- only 285 gets re-applied.
    """
    _, filename_285, marker_table_285, marker_column_285 = next(
        e for e in _GARUDA_VOA_RETENTION_FK_DEPENDENTS if e[0] == 285
    )
    _, _filename_281, marker_table_281, marker_column_281 = next(
        e for e in _GARUDA_VOA_RETENTION_FK_DEPENDENTS if e[0] == 281
    )

    async with db_pool.acquire() as conn:
        assert await _marker_present(conn, marker_table_281, marker_column_281), (
            "281 must be live in the deployed schema for this test's premise to hold"
        )
        assert await _marker_present(conn, marker_table_285, marker_column_285), (
            "285 must be live in the deployed schema for this test's premise to hold"
        )

        # Manually unwind ONLY 285 -- deliberately bypassing
        # unwind_garuda_voa_retention_fk (which would also unwind 281).
        sql_285 = (
            _MIGRATIONS_DIR / filename_285
        ).read_text(encoding="utf-8")
        _, rollback_285 = split_migration_sql(sql_285)
        await conn.execute(rollback_285)

        assert not await _marker_present(conn, marker_table_285, marker_column_285)
        assert await _marker_present(conn, marker_table_281, marker_column_281), (
            "281 must still be live -- this test only unwound 285"
        )

        # The fix under test: restore must re-apply ONLY 285. Before the fix
        # this line raised DuplicateColumnError trying to re-add 281's
        # policy_scope column onto a schema where it already exists.
        await restore_garuda_voa_retention_fk(conn)

        assert await _marker_present(conn, marker_table_285, marker_column_285), (
            "285 must have been restored"
        )
        assert await _marker_present(conn, marker_table_281, marker_column_281), (
            "281 must still be live and untouched by restore"
        )
