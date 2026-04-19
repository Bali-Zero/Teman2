"""Smoke tests for the two llm_cost SQL migrations in db/migrations_v2/.

Replaces the removed Python-based test_migration_119_cost_recommendations.py.
Verifies SQL structure (presence, indexes, constraints, rollback) by reading
the files directly — no live PG needed, matches the convention used by the
other SQL migrations in this repo (e.g. 116_intel_validator_log has no
dedicated runner test either; the apply-path is exercised via
test_migration_apply_strips_rollback.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"


def _read(name: str) -> str:
    return (_MIGRATIONS_DIR / name).read_text(encoding="utf-8")


def test_117_creates_llm_cost_events_table():
    sql = _read("117_llm_cost_events.sql")
    assert "CREATE TABLE IF NOT EXISTS llm_cost_events" in sql
    # Required columns
    for col in (
        "ts_utc",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "success",
        "latency_ms",
    ):
        assert col in sql, f"column {col!r} missing"
    # Check constraints on token/cost non-negativity
    assert "CHECK (input_tokens >= 0)" in sql
    assert "CHECK (cost_usd >= 0)" in sql


def test_117_creates_four_indexes():
    sql = _read("117_llm_cost_events.sql")
    for idx in (
        "idx_llm_cost_ts",
        "idx_llm_cost_endpoint_ts",
        "idx_llm_cost_model_ts",
        "idx_llm_cost_provider_ts",
    ):
        assert f"CREATE INDEX IF NOT EXISTS {idx}" in sql


def test_117_rollback_is_drop_chain():
    sql = _read("117_llm_cost_events.sql")
    after_marker = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS llm_cost_events" in after_marker
    assert after_marker.count("DROP INDEX IF EXISTS") == 4


def test_119_creates_llm_cost_recommendations_table():
    sql = _read("119_llm_cost_recommendations.sql")
    assert "CREATE TABLE IF NOT EXISTS llm_cost_recommendations" in sql
    for col in (
        "endpoint",
        "current_model",
        "proposed_model",
        "estimated_monthly_saving_usd",
        "quality_tradeoff",
        "confidence",
        "spike_flag",
        "status",
    ):
        assert col in sql, f"column {col!r} missing"


def test_119_enforces_status_and_confidence_check_constraints():
    sql = _read("119_llm_cost_recommendations.sql")
    assert "CHECK (confidence IN ('low','medium','high'))" in sql
    assert (
        "CHECK (status IN ('pending','reviewed','applied','rejected'))" in sql
    )


def test_119_creates_two_indexes():
    sql = _read("119_llm_cost_recommendations.sql")
    for idx in ("idx_llm_cost_reco_status_ts", "idx_llm_cost_reco_endpoint"):
        assert f"CREATE INDEX IF NOT EXISTS {idx}" in sql


def test_119_rollback_includes_cascade_drop():
    sql = _read("119_llm_cost_recommendations.sql")
    after_marker = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS llm_cost_recommendations CASCADE" in after_marker


@pytest.mark.parametrize("name", ["117_llm_cost_events.sql", "119_llm_cost_recommendations.sql"])
def test_has_rollback_marker(name: str):
    """Both migrations must include the -- === ROLLBACK === marker so the
    migration runner can strip the rollback section during apply()."""
    sql = _read(name)
    assert "-- === ROLLBACK ===" in sql
