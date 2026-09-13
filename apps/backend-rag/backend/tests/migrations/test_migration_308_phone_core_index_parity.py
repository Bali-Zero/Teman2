"""Migration 308's expression indexes must be TEXTUALLY the query's own CASE expressions.

PostgreSQL uses an expression index only when the planner can match the indexed
expression against the predicate structurally; a stray COALESCE default, a
reordered WHEN branch or a different regexp flag silently turns the index into
dead weight and the seq scan (2.54M lifetime, 0.6/s sustained, measured
2026-09-10) comes back with no error anywhere. This tripwire pins the three
indexed expressions to UPSERT_MATCH_SQL, whitespace-normalised, and fails if
either side drifts without the other. Guilt case included: a one-character
divergence is caught.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.routers.crm_clients import UPSERT_MATCH_SQL

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "308_clients_phone_core_expression_indexes.sql"
)

_CASE_RE = re.compile(r"CASE WHEN .*? END", re.S)
_INDEX_RE = re.compile(
    r"CREATE INDEX IF NOT EXISTS (\w+)\s+ON public\.clients \(\(\s*(CASE WHEN .*? END)\s*\)\);",
    re.S,
)


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _query_cases() -> list[str]:
    where = UPSERT_MATCH_SQL.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    cases = [_norm(m) for m in _CASE_RE.findall(where)]
    assert len(cases) == 3, cases
    return cases


def _migration_cases(text: str) -> list[tuple[str, str]]:
    return [(name, _norm(expr)) for name, expr in _INDEX_RE.findall(text)]


def test_migration_indexes_exactly_the_three_query_expressions() -> None:
    indexed = _migration_cases(MIGRATION.read_text(encoding="utf-8"))
    assert [name for name, _ in indexed] == [
        "idx_clients_phone_core_normalized",
        "idx_clients_phone_core_phone",
        "idx_clients_phone_core_whatsapp",
    ]
    assert [expr for _, expr in indexed] == _query_cases()


def test_every_query_column_is_covered_once() -> None:
    columns = [
        re.search(r"COALESCE\((\w+),", expr).group(1)  # type: ignore[union-attr]
        for expr in _query_cases()
    ]
    assert columns == ["phone_normalized", "phone", "whatsapp"]


def test_rollback_drops_exactly_the_created_indexes() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    created = set(_INDEX_RE.findall(text) and [n for n, _ in _INDEX_RE.findall(text)])
    rollback = text.split("-- === ROLLBACK ===", 1)[1]
    dropped = set(re.findall(r"DROP INDEX IF EXISTS public\.(\w+);", rollback))
    assert created == dropped


def test_one_character_drift_is_caught() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    drifted = text.replace("LIKE '62%'", "LIKE '63%'", 1)
    assert [e for _, e in _migration_cases(drifted)] != _query_cases()
