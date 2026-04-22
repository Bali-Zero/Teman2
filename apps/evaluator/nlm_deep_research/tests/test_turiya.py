"""Tests for turiya read-only aggregator."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.turiya import (
    NB_CATALOG,
    _build_consistency,
    _read_heartbeat,
    _read_pipeline_state,
    _read_synthesis_state,
    _read_yin_yang_for_nb,
    snapshot_all,
    snapshot_nb,
)


# ── _read_pipeline_state ─────────────────────────────────────────────────────


def test_read_pipeline_state_missing_file(tmp_path: Path) -> None:
    out = _read_pipeline_state("nb4", evaluator_root=tmp_path)
    assert out == {"available": False}


def test_read_pipeline_state_parsed(tmp_path: Path) -> None:
    state_data = {
        "current_state": "COMPLETE",
        "degradation_level": "NOMINAL",
        "last_updated": "2026-04-22T02:22:00+00:00",
        "last_run": {"cluster": "F", "claims_total": 42},
    }
    state_file = tmp_path / "nlm_nb4_pipeline_state.json"
    state_file.write_text(json.dumps(state_data))

    out = _read_pipeline_state("nb4", evaluator_root=tmp_path)
    assert out["available"] is True
    assert out["current_state"] == "COMPLETE"
    assert out["last_run_cluster"] == "F"
    assert out["last_run_claims_total"] == 42


def test_read_pipeline_state_corrupt_json_is_unavailable(tmp_path: Path) -> None:
    bad = tmp_path / "nlm_nb4_pipeline_state.json"
    bad.write_text("not-json{{{{")
    out = _read_pipeline_state("nb4", evaluator_root=tmp_path)
    assert out == {"available": False}


# ── _read_heartbeat ──────────────────────────────────────────────────────────


def test_read_heartbeat_computes_age(tmp_path: Path) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    hb_file = tmp_path / "heartbeat_nb4_pipeline.json"
    hb_file.write_text(json.dumps({"last_success": ts, "duration_seconds": 3.14}))

    out = _read_heartbeat("nb4_pipeline", heartbeat_dir=tmp_path)
    assert out["available"] is True
    assert out["age_hours"] is not None
    assert 1.9 < out["age_hours"] < 2.1
    assert out["duration_seconds"] == 3.14


def test_read_heartbeat_missing_file(tmp_path: Path) -> None:
    out = _read_heartbeat("nb4_pipeline", heartbeat_dir=tmp_path)
    assert out == {"available": False}


def test_read_heartbeat_invalid_timestamp(tmp_path: Path) -> None:
    hb_file = tmp_path / "heartbeat_nb4_pipeline.json"
    hb_file.write_text(json.dumps({"last_success": "not-a-date"}))
    out = _read_heartbeat("nb4_pipeline", heartbeat_dir=tmp_path)
    assert out["available"] is True
    assert out["age_hours"] is None


# ── _read_synthesis_state ────────────────────────────────────────────────────


def test_read_synthesis_counts_sources(tmp_path: Path) -> None:
    data = {
        "last_updated": "2026-04-22T00:00+00:00",
        "daily_sources": ["a", "b", "c"],
        "weekly_sources": ["d"],
        "monthly_sources": [],
    }
    f = tmp_path / "nlm_nb4_synthesis_state.json"
    f.write_text(json.dumps(data))

    out = _read_synthesis_state("nb4", evaluator_root=tmp_path)
    assert out["available"] is True
    assert out["daily_sources_count"] == 3
    assert out["weekly_sources_count"] == 1
    assert out["monthly_sources_count"] == 0


# ── _read_yin_yang_for_nb ────────────────────────────────────────────────────


def test_read_yin_yang_slices_nb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit = {
        "ts": "2026-04-22T09:00+00:00",
        "per_nb": {"nb4": {"ratio": 1.8, "status": "HEALTHY"}, "nb5": {"ratio": 12.5, "status": "YANG_FLOOD"}},
        "streaks": {"nb4": {"consecutive_weeks": 1}, "nb5": {"consecutive_weeks": 3}},
    }
    state_file = tmp_path / "yin_yang_state.jsonl"
    state_file.write_text(json.dumps(audit) + "\n")
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.turiya.YIN_YANG_STATE", state_file
    )

    out = _read_yin_yang_for_nb("nb4")
    assert out["available"] is True
    assert out["status"] == "HEALTHY"
    assert out["ratio"] == 1.8
    assert out["consecutive_weeks"] == 1


# ── _build_consistency ───────────────────────────────────────────────────────


def test_consistency_flags_empty_when_healthy() -> None:
    jagrat = {"available": True, "current_state": "COMPLETE"}
    svapna = {"available": True, "coverage_updated": datetime.now(timezone.utc).isoformat()}
    sushupti = {"available": True}
    heartbeat = {"available": True, "age_hours": 1.0}
    yajna = {"available": True, "offered": 5, "cited": 2}
    yin_yang = {"available": True, "status": "HEALTHY", "consecutive_weeks": 1}

    out = _build_consistency("nb4", jagrat, svapna, sushupti, heartbeat, yajna, yin_yang)
    assert out["flags"] == []
    assert out["ok"] is True


def test_consistency_flags_halted_pipeline_fresh_heartbeat() -> None:
    jagrat = {"available": True, "current_state": "HALTED"}
    heartbeat = {"available": True, "age_hours": 3.0}
    out = _build_consistency(
        "nb4",
        jagrat,
        {"available": False},
        {"available": False},
        heartbeat,
        {"available": False},
        {"available": False},
    )
    assert any("HALTED but heartbeat fresh" in f for f in out["flags"])
    assert out["ok"] is False


def test_consistency_flags_stale_coverage_matrix() -> None:
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    svapna = {"available": True, "coverage_updated": stale_ts}
    out = _build_consistency(
        "nb4",
        {"available": False},
        svapna,
        {"available": False},
        {"available": False},
        {"available": False},
        {"available": False},
    )
    assert any("coverage_matrix stale" in f for f in out["flags"])


def test_consistency_flags_yang_flood_streak() -> None:
    yin_yang = {"available": True, "status": "YANG_FLOOD", "consecutive_weeks": 3}
    out = _build_consistency(
        "nb5",
        {"available": False},
        {"available": False},
        {"available": False},
        {"available": False},
        {"available": False},
        yin_yang,
    )
    assert any("YANG_FLOOD for 3" in f for f in out["flags"])


def test_consistency_flags_orphan_nb() -> None:
    yajna = {"available": True, "offered": 25, "cited": 0}
    out = _build_consistency(
        "nb5",
        {"available": False},
        {"available": False},
        {"available": False},
        {"available": False},
        yajna,
        {"available": False},
    )
    assert any("possible orphan NB" in f for f in out["flags"])


# ── snapshot_nb / snapshot_all ───────────────────────────────────────────────


def test_snapshot_nb_structure_all_unavailable(tmp_path: Path) -> None:
    """When no state files exist, snapshot still produces coherent structure."""
    snap = snapshot_nb("nb4", evaluator_root=tmp_path, heartbeat_dir=tmp_path)
    assert snap["nb"] == "nb4"
    assert "label" in snap
    assert snap["jagrat"] == {"available": False}
    assert snap["heartbeat"] == {"available": False}
    assert "consistency" in snap
    assert "flags" in snap["consistency"]


def test_snapshot_all_covers_full_catalog(tmp_path: Path) -> None:
    out = snapshot_all(evaluator_root=tmp_path, heartbeat_dir=tmp_path)
    assert set(out["per_nb"].keys()) == set(NB_CATALOG.keys())
    assert "ts" in out
    assert "global_flags" in out
    assert out["observer"] == "turiya-v1"


def test_snapshot_all_global_flag_heartbeat_gap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When registry declares pipelines but no heartbeat files exist, flag it."""
    # Build a minimal registry with 3 entries
    registry = {"nb4_pipeline": {"max_age_hours": 6}, "nb5_pipeline": {"max_age_hours": 6}, "nb6_pipeline": {"max_age_hours": 6}}
    reg_file = tmp_path / "pipeline_heartbeat_registry.json"
    reg_file.write_text(json.dumps(registry))

    # Heartbeat dir empty
    heartbeat_dir = tmp_path / "hb"
    heartbeat_dir.mkdir()

    # Patch module-level registry path
    monkeypatch.setattr("apps.evaluator.nlm_deep_research.turiya._DIR", tmp_path)

    out = snapshot_all(heartbeat_dir=heartbeat_dir, evaluator_root=tmp_path)
    # Should flag: 0/3 pipelines have heartbeat
    assert any("heartbeat_registry" in f for f in out["global_flags"])
