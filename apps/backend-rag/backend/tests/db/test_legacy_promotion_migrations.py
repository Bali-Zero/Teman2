"""Structural checks for the 129–137 legacy-promotion migrations.

Strategy 01 Step 4 prep — these migrations promote tables and ALTERs
that today live in `apps/backend-rag/scripts/ci_bootstrap_schema.py`
into `db/migrations_v2/`. They are intentionally idempotent so they can
land before the bootstrap step is removed.

What this test enforces (no Postgres needed):

* every file we expect to ship is present;
* every file carries the `-- === ROLLBACK ===` marker (without it the
  v2 runner has no rollback to extract — see `migration_base.py`);
* the forward block is non-empty and the rollback block is non-empty;
* every CREATE TABLE / CREATE INDEX / ADD COLUMN uses the IF NOT EXISTS
  form (idempotency invariant for this batch);
* every ALTER COLUMN that touches NOT NULL / DEFAULT does so via a verb
  that's a no-op when re-applied (DROP NOT NULL, SET DEFAULT, DROP
  DEFAULT) — never `SET NOT NULL` (which would fail on rows that
  legitimately store NULL today).

Functional schema correctness — "does running this against a real
Postgres reproduce the prod shape?" — belongs in an integration test
that the Step 4 cutover PR will add when the bootstrap step is removed
and the audit can stand on its own.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIG_DIR = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
)


# Files this batch ships. Originally numbered 129–137 with one
# intentional gap (131) for Strategy 01 Step 3
# (`131_unify_migration_tracking.sql`). 129 and 130 collided with the
# crm_guardian batch (PR #258) and were renumbered to 142 and 143 by
# the P0-7 audit fix on 2026-04-29 — see cicatrix STRUCTURAL P0-7.
LEGACY_PROMOTION_FILES = (
    "142_legacy_user_profiles.sql",
    "143_legacy_conversations.sql",
    "132_legacy_lkpm_reports.sql",
    "133_legacy_system_settings.sql",
    "134_legacy_notification_log.sql",
    "135_legacy_notification_prefs.sql",
    "136_clients_drive_columns_and_defaults.sql",
    "137_team_members_legacy_columns_and_defaults.sql",
)

# Files that landed in the 129/130 number range and are NOT part of the
# legacy-promotion batch. They have their own forward/rollback contracts
# tested elsewhere (or none, if pre-dating the convention). Listed here
# so test_files_match_directory_listing accepts them as expected.
NON_LEGACY_FILES_IN_RANGE = (
    "129_crm_guardian.sql",  # crm_guardian DDL (separate feature, has its own tests)
    "130_crm_guardian_summary_queue.sql",  # follow-up to 129
)


_ROLLBACK_MARKER = re.compile(r"^--\s*===\s*ROLLBACK\s*===\s*$", re.MULTILINE | re.IGNORECASE)


def _strip_sql_comments(sql: str) -> str:
    """Drop everything after `--` on each line.

    The shape tests apply regexes that look for SQL verbs; English prose
    inside `-- comments` (e.g. "DROP TABLE is intentionally NOT offered")
    must not be matched as if it were code.
    """
    out: list[str] = []
    for line in sql.splitlines():
        idx = line.find("--")
        out.append(line[:idx] if idx >= 0 else line)
    return "\n".join(out)


def _split(sql_text: str) -> tuple[str, str]:
    """Return (forward_sql, rollback_sql) — both with comments stripped.

    Mirrors `migration_base.split_migration_sql` for the marker logic
    and additionally drops `-- ...` comment tails so test regexes don't
    trip on English text inside comment lines.
    """
    parts = _ROLLBACK_MARKER.split(sql_text, maxsplit=1)
    forward = _strip_sql_comments(parts[0]).strip()
    rollback = _strip_sql_comments(parts[1]).strip() if len(parts) == 2 else ""
    return forward, rollback


@pytest.fixture(scope="module")
def files() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in LEGACY_PROMOTION_FILES:
        path = MIG_DIR / name
        assert path.exists(), f"missing migration file: {path}"
        out[name] = path.read_text(encoding="utf-8")
    return out


def test_every_file_has_rollback_marker(files: dict[str, str]) -> None:
    for name, sql in files.items():
        assert _ROLLBACK_MARKER.search(sql), (
            f"{name}: missing '-- === ROLLBACK ===' marker"
        )


def test_forward_and_rollback_blocks_non_empty(files: dict[str, str]) -> None:
    for name, sql in files.items():
        forward, rollback = _split(sql)
        assert forward, f"{name}: forward block is empty"
        assert rollback, f"{name}: rollback block is empty"


def test_create_uses_if_not_exists(files: dict[str, str]) -> None:
    """Every CREATE TABLE / CREATE INDEX in the forward block is idempotent.

    Bootstrap-replacement migrations land on a DB that already has the
    table; without IF NOT EXISTS the second `apply-all` run would crash.
    The runner already records the migration as applied on first run,
    so this is a defence-in-depth invariant for the case where
    `_schema_versions` and `schema_migrations` disagree mid-transition.
    """
    create_table_pat = re.compile(r"\bCREATE\s+TABLE\b(?!\s+IF\s+NOT\s+EXISTS)", re.IGNORECASE)
    create_index_pat = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b(?!\s+(?:CONCURRENTLY\s+)?IF\s+NOT\s+EXISTS)", re.IGNORECASE)
    add_column_pat = re.compile(
        r"\bADD\s+COLUMN\b(?!\s+IF\s+NOT\s+EXISTS)", re.IGNORECASE,
    )

    for name, sql in files.items():
        forward, _ = _split(sql)
        bad = create_table_pat.findall(forward)
        assert not bad, f"{name}: forward block has CREATE TABLE without IF NOT EXISTS"
        bad = create_index_pat.findall(forward)
        assert not bad, f"{name}: forward block has CREATE INDEX without IF NOT EXISTS"
        bad = add_column_pat.findall(forward)
        assert not bad, f"{name}: forward block has ADD COLUMN without IF NOT EXISTS"


def test_alter_column_does_not_promote_to_not_null(files: dict[str, str]) -> None:
    """SET NOT NULL would fail on prod rows that legitimately store NULL.

    Several of these migrations reflect prod's relaxation of historical
    NOT NULL constraints (lkpm_reports realized_*/cumulative_*,
    team_members.full_name). The forward block must never re-introduce
    NOT NULL — if it did, applying this migration to prod would crash
    on the first row that has NULL in that column today.
    """
    set_not_null_pat = re.compile(
        r"\bALTER\s+COLUMN\s+\w+\s+SET\s+NOT\s+NULL\b",
        re.IGNORECASE,
    )
    for name, sql in files.items():
        forward, _ = _split(sql)
        bad = set_not_null_pat.findall(forward)
        assert not bad, (
            f"{name}: forward block contains 'SET NOT NULL' "
            "(would fail on prod rows holding NULL today)"
        )


def test_drop_uses_if_exists_in_rollback(files: dict[str, str]) -> None:
    """Every DROP in a rollback block must guard with IF EXISTS.

    Rollbacks run against DBs in arbitrary states (incomplete forward
    application, manual interventions). DROP without IF EXISTS turns a
    routine rollback into a hard failure.
    """
    drop_pat = re.compile(
        r"\bDROP\s+(TABLE|INDEX|COLUMN)\b(?!\s+IF\s+EXISTS)",
        re.IGNORECASE,
    )
    for name, sql in files.items():
        _, rollback = _split(sql)
        bad = drop_pat.findall(rollback)
        assert not bad, f"{name}: rollback block has DROP without IF EXISTS"


def test_files_match_directory_listing() -> None:
    """No surprise files in the 129–137 range — every numbered file in
    that range is in our list, and our list has no missing entries.

    Catches the case where a follow-up PR drops a 13X migration into
    `migrations_v2/` without updating this test (and therefore without
    establishing the forward/rollback / idempotency contract).
    """
    actual = sorted(
        f.name
        for f in MIG_DIR.iterdir()
        if f.is_file()
        and f.suffix == ".sql"
        and f.name[:3].isdigit()
        and 129 <= int(f.name[:3]) <= 137
    )
    # 131 is intentionally reserved for unify_migration_tracking
    # 142, 143 used to live in this range as 129_legacy_user_profiles and
    # 130_legacy_conversations; renumbered out by P0-7 (2026-04-29).
    in_range_legacy = tuple(
        f for f in LEGACY_PROMOTION_FILES if 129 <= int(f[:3]) <= 137
    )
    expected = sorted(in_range_legacy + NON_LEGACY_FILES_IN_RANGE)
    assert actual == expected, (
        f"unexpected files in 129–137 range\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )
