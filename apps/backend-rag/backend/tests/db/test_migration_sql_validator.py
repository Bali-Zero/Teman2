"""
Guilt + innocence coverage for BaseMigration._validate_sql's TRUNCATE guard.

Context (cicatrix family #3 -- guard-over-match): the validator used to flag
ANY non-comment line containing the substring "TRUNCATE" as dangerous. That
trapped a legitimate pattern: append-only tables guard against
`TRUNCATE TABLE <t>` wipes with a `CREATE TRIGGER ... BEFORE TRUNCATE ON
public.<t> FOR EACH STATEMENT EXECUTE FUNCTION ...` -- the `BEFORE TRUNCATE
ON` clause is a trigger EVENT declaration (safe, and in fact prevents wipes),
not a destructive `TRUNCATE` statement, but the old substring check couldn't
tell the two apart (migration 252, STEP-6b SHADOW write substrate).

The fix makes the check context-aware: a line is only flagged if TRUNCATE is
NOT followed by ON/OR (the markers of a trigger-event clause). These tests
prove BOTH directions: destructive TRUNCATE statements still raise
(guilt), and trigger-event / comment usages still pass (innocence).
"""

from pathlib import Path

import pytest

from backend.db.migration_base import BaseMigration, MigrationError


def _migration(tmp_path: Path) -> BaseMigration:
    """A throwaway BaseMigration instance -- _validate_sql doesn't touch the
    DB or even read self.sql_file's content, it only operates on the string
    passed to it, so the backing file just needs to exist to satisfy
    __init__'s existence check."""
    sql_file = tmp_path / "999_scratch.sql"
    sql_file.write_text("-- scratch file, content irrelevant to these tests\n")
    return BaseMigration(
        migration_number=999,
        sql_file="999_scratch.sql",
        description="scratch migration for _validate_sql unit tests",
        rollback_sql="-- no-op",
        _sql_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# GUILT -- destructive TRUNCATE statements must still raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dangerous_sql",
    [
        "TRUNCATE TABLE foo;",
        "TRUNCATE foo;",
        "TRUNCATE ONLY foo;",
        "truncate table visa_decisions;",  # lowercase still caught
        "TRUNCATE TABLE foo, bar CASCADE;",
    ],
)
def test_destructive_truncate_statement_raises(tmp_path: Path, dangerous_sql: str) -> None:
    migration = _migration(tmp_path)
    with pytest.raises(MigrationError, match="TRUNCATE"):
        migration._validate_sql(dangerous_sql)


# ---------------------------------------------------------------------------
# INNOCENCE -- trigger-event TRUNCATE and comments must NOT raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "safe_sql",
    [
        # Precedent from migration 252: BEFORE TRUNCATE ON <table> is a
        # trigger-event clause (wipe guard), not a destructive statement.
        "CREATE TRIGGER visa_decisions_no_wipe\n"
        "BEFORE TRUNCATE ON public.visa_decisions\n"
        "FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();",
        # Chained event list via OR.
        "CREATE TRIGGER x_guard\n"
        "AFTER INSERT OR TRUNCATE ON public.x\n"
        "FOR EACH STATEMENT EXECUTE FUNCTION public.some_guard();",
        # Comment-only mention (existing allowance, migration 201 precedent).
        "-- TRUNCATE column first, see migration 201 for context.",
        # Mixed: a comment line plus a genuinely safe trigger-event line.
        "-- BEFORE TRUNCATE guard added per P2 fix\n"
        "CREATE TRIGGER y_guard\n"
        "BEFORE TRUNCATE ON public.y\n"
        "FOR EACH STATEMENT EXECUTE FUNCTION public.reject_wipe();",
    ],
)
def test_trigger_event_and_comment_truncate_passes(tmp_path: Path, safe_sql: str) -> None:
    migration = _migration(tmp_path)
    # _validate_sql returns None on success (raises MigrationError on
    # failure) -- asserting the return value makes "did not raise" an
    # explicit, checked assertion rather than an implicit fall-through.
    assert migration._validate_sql(safe_sql) is None


def test_migration_252_style_full_block_passes(tmp_path: Path) -> None:
    """End-to-end shape mirroring the real migration 252 guard block."""
    sql = """
-- ---------------------------------------------------------------------------
-- BEFORE TRUNCATE guards (P2 fix, verify-round finding): Postgres row-level
-- triggers (FOR EACH ROW, above) do NOT fire on the TRUNCATE statement.
-- ---------------------------------------------------------------------------
CREATE TRIGGER visa_decisions_no_wipe
BEFORE TRUNCATE ON public.visa_decisions
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_decision_payloads_no_wipe
BEFORE TRUNCATE ON public.visa_decision_payloads
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_source_records_no_wipe
BEFORE TRUNCATE ON public.visa_source_records
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();
"""
    migration = _migration(tmp_path)
    assert migration._validate_sql(sql) is None  # must not raise


def test_trigger_event_line_with_trailing_destructive_statement_still_raises(
    tmp_path: Path,
) -> None:
    """A safe trigger-event line elsewhere in the file must not mask an
    actual destructive TRUNCATE statement placed on a different line."""
    sql = (
        "CREATE TRIGGER x_guard\n"
        "BEFORE TRUNCATE ON public.x\n"
        "FOR EACH STATEMENT EXECUTE FUNCTION public.reject_wipe();\n"
        "\n"
        "TRUNCATE TABLE some_other_table;\n"
    )
    migration = _migration(tmp_path)
    with pytest.raises(MigrationError, match="TRUNCATE"):
        migration._validate_sql(sql)
