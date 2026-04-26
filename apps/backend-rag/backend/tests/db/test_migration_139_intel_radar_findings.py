"""
Tests for migration 139_intel_radar_findings.sql.

Validates the SQL file's structural invariants without needing a real DB:
  - presence of `-- === ROLLBACK ===` marker (required by runner since SCAR 2026-04-19)
  - forward and rollback blocks both non-empty
  - CREATE TABLE / INDEX are idempotent (IF NOT EXISTS)
  - UNIQUE(canonical_url) constraint is declared in forward
  - rollback DROPs the table (recovery path)

Real-DB roundtrip is left for the apply-all integration test that runs
in CI (test_migration_apply_strips_rollback.py walks the directory).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).parent.parent.parent
    / "db"
    / "migrations_v2"
    / "139_intel_radar_findings.sql"
)

_ROLLBACK_MARKER = re.compile(r"^\s*--\s*===\s*ROLLBACK\s*===\s*$", re.MULTILINE | re.IGNORECASE)


@pytest.fixture(scope="module")
def sql() -> str:
    assert MIGRATION_PATH.exists(), f"missing migration file: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def split_sql(sql: str) -> tuple[str, str]:
    match = _ROLLBACK_MARKER.search(sql)
    assert match, "migration 139 missing ROLLBACK marker"
    return sql[: match.start()].rstrip(), sql[match.end() :].strip()


def test_has_rollback_marker(sql: str) -> None:
    assert _ROLLBACK_MARKER.search(sql), "missing '-- === ROLLBACK ===' marker"


def test_forward_and_rollback_non_empty(split_sql: tuple[str, str]) -> None:
    forward, rollback = split_sql
    assert forward, "forward block is empty"
    assert rollback, "rollback block is empty"


def test_create_uses_if_not_exists(split_sql: tuple[str, str]) -> None:
    forward, _ = split_sql
    create_table_pat = re.compile(r"\bCREATE\s+TABLE\b(?!\s+IF\s+NOT\s+EXISTS)", re.IGNORECASE)
    create_index_pat = re.compile(
        r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b(?!\s+(?:CONCURRENTLY\s+)?IF\s+NOT\s+EXISTS)",
        re.IGNORECASE,
    )
    assert not create_table_pat.findall(forward), "CREATE TABLE without IF NOT EXISTS"
    assert not create_index_pat.findall(forward), "CREATE INDEX without IF NOT EXISTS"


def test_canonical_url_unique_constraint(split_sql: tuple[str, str]) -> None:
    forward, _ = split_sql
    # Either inline UNIQUE on the column or named CONSTRAINT — accept both.
    pat = re.compile(
        r"(canonical_url\s+TEXT\s+NOT\s+NULL\s+UNIQUE|CONSTRAINT\s+\w+_canonical_url_uniq\s+UNIQUE\s*\(\s*canonical_url\s*\))",
        re.IGNORECASE,
    )
    assert pat.search(forward), "UNIQUE(canonical_url) not declared in forward block"


def test_query_tier_check_constraint(split_sql: tuple[str, str]) -> None:
    forward, _ = split_sql
    # Tier rotation L1/L2/L3 is structural — must be enforced at DB level.
    pat = re.compile(
        r"query_tier\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*query_tier\s+IN\s*\(\s*'L1'\s*,\s*'L2'\s*,\s*'L3'\s*\)",
        re.IGNORECASE,
    )
    assert pat.search(forward), "query_tier CHECK constraint missing or wrong values"


def test_processed_and_scraper_picked_columns(split_sql: tuple[str, str]) -> None:
    """Watermark booleans are how digest and scraper signal progress."""
    forward, _ = split_sql
    for col in ("processed", "scraper_picked"):
        pat = re.compile(
            rf"\b{col}\s+BOOLEAN\s+NOT\s+NULL\s+DEFAULT\s+FALSE\b",
            re.IGNORECASE,
        )
        assert pat.search(forward), f"{col} column missing or wrong default"


def test_partial_indexes_for_query_paths(split_sql: tuple[str, str]) -> None:
    """The two read paths (digest unprocessed, scraper pickable) get partial indexes."""
    forward, _ = split_sql
    assert re.search(
        r"idx_intel_radar_findings_unprocessed.*WHERE\s+processed\s*=\s*FALSE",
        forward, re.IGNORECASE | re.DOTALL,
    ), "missing partial index on unprocessed"
    assert re.search(
        r"idx_intel_radar_findings_pickable.*WHERE\s+processed\s*=\s*TRUE\s+AND\s+scraper_picked\s*=\s*FALSE",
        forward, re.IGNORECASE | re.DOTALL,
    ), "missing partial index on pickable"


def test_rollback_drops_table(split_sql: tuple[str, str]) -> None:
    _, rollback = split_sql
    pat = re.compile(r"DROP\s+TABLE\s+IF\s+EXISTS\s+intel_radar_findings", re.IGNORECASE)
    assert pat.search(rollback), "rollback must DROP intel_radar_findings"
