"""
Static guard: migration 041b must emit valid PostgreSQL DDL.

SCAR CONTEXT (found via live prod E2E 2026-07-08):
`migration_041b_team_activity_logging.py` was REGISTERED in the runner
(backend/db/migration_base.py) but had NEVER successfully applied to prod:
its CREATE TABLE statements used MySQL inline-`INDEX` syntax
(`INDEX idx_foo (col)` inside the table body), which PostgreSQL rejects with
a syntax error on every run. Result: the activity_logs / team_interactions /
api_audit_trail / session_tracking tables and the v_today_team_activity view
were never created, so GET /api/admin/logs/{activity,interactions,summary/*}
all 500'd with `relation "activity_logs" does not exist`.

Fix: move every inline index out of the CREATE TABLE body into a separate
`CREATE INDEX IF NOT EXISTS ... ON table(...)` statement (valid Postgres).
FOREIGN KEY constraints stay inline (those ARE valid Postgres table
constraints). This test parses each `CREATE TABLE ( ... )` body in the
migration source and asserts no bare inline `INDEX` declaration remains — a
static tripwire so the MySQL-ism cannot regress. Applying the migration needs
a live DB, so a source-level guard is the right layer here.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "migration_041b_team_activity_logging.py"
)


def _create_table_bodies(source: str) -> list[str]:
    """Return the parenthesised body of every CREATE TABLE ... ( ... ) block.

    Walks the source and, for each `CREATE TABLE ... (`, captures text up to
    the matching close-paren by paren-depth counting (handles nested parens
    such as VARCHAR(255) / DEFAULT NOW()).
    """
    bodies: list[str] = []
    for m in re.finditer(r"CREATE TABLE[^(]*\(", source, re.IGNORECASE):
        depth = 1
        i = m.end()
        start = i
        while i < len(source) and depth > 0:
            ch = source[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        bodies.append(source[start : i - 1])
    return bodies


def test_migration_source_exists() -> None:
    assert MIGRATION.is_file(), f"migration not found at {MIGRATION}"


def test_no_inline_index_in_any_create_table_body() -> None:
    """GUILT: the live 500 was caused by MySQL inline `INDEX idx_x (col)` lines
    inside CREATE TABLE bodies. Assert none survive in any table block."""
    source = MIGRATION.read_text(encoding="utf-8")
    bodies = _create_table_bodies(source)
    assert bodies, "expected at least one CREATE TABLE block in migration 041b"

    inline_index = re.compile(r"(^|,|\n)\s*INDEX\s+\w", re.IGNORECASE)
    offenders: list[str] = []
    for body in bodies:
        if inline_index.search(body):
            offenders.append(body.strip()[:120])
    assert not offenders, (
        "MySQL inline INDEX declaration found inside a CREATE TABLE body "
        "(Postgres rejects this) — move it to a separate CREATE INDEX statement:\n"
        + "\n".join(offenders)
    )


def test_indexes_are_created_via_standalone_statements() -> None:
    """INNOCENCE: the indexes must still exist — as valid standalone
    `CREATE INDEX` statements. If the fix merely deleted the inline indexes,
    that would be a silent coverage loss."""
    source = MIGRATION.read_text(encoding="utf-8")
    create_index_count = len(re.findall(r"CREATE INDEX", source, re.IGNORECASE))
    assert create_index_count >= 15, (
        f"expected many standalone CREATE INDEX statements, found {create_index_count} "
        "— the inline indexes must be re-expressed, not dropped"
    )


def test_no_corrupted_placeholder_log_messages() -> None:
    """The file also carried corrupted `logger.info(\"$1\")` placeholders from a
    botched find/replace; assert they are gone (real messages restored)."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'logger.info("$1")' not in source, (
        "corrupted placeholder log message logger.info(\"$1\") still present"
    )
