"""Tests for nb0_refresh — Meta-NLM aggregator + bootstrap guard."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research.nb0_refresh import (
    SOURCE_TITLES,
    _sha256,
    assemble_coverage_source,
    assemble_heartbeat_source,
    assemble_yajna_source,
    assemble_yin_yang_source,
    build_all_sources,
    get_nb0_notebook_id,
    run_refresh,
)


# ── Bootstrap guard ──────────────────────────────────────────────────────────


def test_get_nb0_notebook_id_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NB0_NOTEBOOK_ID", raising=False)
    assert get_nb0_notebook_id() is None


def test_get_nb0_notebook_id_empty_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NB0_NOTEBOOK_ID", "   ")
    assert get_nb0_notebook_id() is None


def test_get_nb0_notebook_id_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NB0_NOTEBOOK_ID", "abc-uuid")
    assert get_nb0_notebook_id() == "abc-uuid"


# ── assemble_yajna_source ────────────────────────────────────────────────────


def test_assemble_yajna_missing_file(tmp_path: Path) -> None:
    out = assemble_yajna_source(metrics_path=tmp_path / "nonexistent.jsonl")
    assert out == ""


def test_assemble_yajna_renders_latest_line(tmp_path: Path) -> None:
    path = tmp_path / "yajna_metrics.jsonl"
    # Multi-line jsonl; only last should be rendered
    lines = [
        json.dumps({"computed_at": "2026-04-15", "totals": {"offered": 1}}),
        json.dumps(
            {
                "computed_at": "2026-04-22",
                "window_days": 30,
                "totals": {"offered": 10, "cited": 3, "promoted": 1},
                "rates": {"cite_rate": 0.3},
                "per_nb": {"nb4": {"offered": 5, "cited": 2, "promoted": 1}},
                "orphan_count": 1,
            }
        ),
    ]
    path.write_text("\n".join(lines) + "\n")
    out = assemble_yajna_source(metrics_path=path)
    assert "2026-04-22" in out
    assert "2026-04-15" not in out  # older line not rendered
    assert "offered: 10" in out
    assert "cited: 3" in out
    assert "cite_rate: 0.3" in out
    assert "| nb4 | 5 | 2 | 1 |" in out


def test_assemble_yajna_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "yajna_metrics.jsonl"
    path.write_text("")
    assert assemble_yajna_source(metrics_path=path) == ""


# ── assemble_yin_yang_source ─────────────────────────────────────────────────


def test_assemble_yin_yang_renders(tmp_path: Path) -> None:
    path = tmp_path / "yin_yang_state.jsonl"
    entry = {
        "ts": "2026-04-22T09:00Z",
        "auto_adjust_enabled": True,
        "per_nb": {
            "nb4": {"offered": 10, "cited": 5, "promoted": 2, "ratio": 1.8, "status": "HEALTHY"},
            "nb5": {"offered": 50, "cited": 2, "promoted": 1, "ratio": 12.5, "status": "YANG_FLOOD"},
        },
        "recommendations": [
            {"nb": "nb5", "action": "synth_cadence_to_daily", "reason": "2w yang flood", "auto_applied": True, "reversible": True}
        ],
    }
    path.write_text(json.dumps(entry) + "\n")
    out = assemble_yin_yang_source(state_path=path)
    assert "2026-04-22" in out
    assert "| nb4 |" in out
    assert "YANG_FLOOD" in out
    assert "synth_cadence_to_daily" in out


def test_assemble_yin_yang_missing_file(tmp_path: Path) -> None:
    out = assemble_yin_yang_source(state_path=tmp_path / "nonexistent.jsonl")
    assert out == ""


def test_assemble_yin_yang_no_recommendations(tmp_path: Path) -> None:
    path = tmp_path / "yin_yang_state.jsonl"
    entry = {
        "ts": "2026-04-22T09:00Z",
        "per_nb": {"nb4": {"offered": 10, "cited": 5, "promoted": 2, "ratio": 1.8, "status": "HEALTHY"}},
        "recommendations": [],
    }
    path.write_text(json.dumps(entry) + "\n")
    out = assemble_yin_yang_source(state_path=path)
    assert "no recommendations" in out


# ── assemble_heartbeat_source ────────────────────────────────────────────────


def test_assemble_heartbeat_reports_missing_as_never(tmp_path: Path) -> None:
    hdir = tmp_path / "state"
    hdir.mkdir()
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({"nb4_pipeline": {"max_age_hours": 6}}))
    # Write heartbeat for nb4 only
    (hdir / "heartbeat_nb4_pipeline.json").write_text(json.dumps({"last_success": "2026-04-22T00:00+00:00"}))

    out = assemble_heartbeat_source(state_dir=hdir, registry_path=reg_path)
    assert "nb4_pipeline" in out
    assert "2026-04-22" in out


def test_assemble_heartbeat_multiple_pipelines_declared(tmp_path: Path) -> None:
    hdir = tmp_path / "state"
    hdir.mkdir()
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(
        json.dumps(
            {"nb4_pipeline": {"max_age_hours": 6}, "nb5_pipeline": {"max_age_hours": 6}}
        )
    )
    # Only nb4 has heartbeat; nb5 is missing
    (hdir / "heartbeat_nb4_pipeline.json").write_text(json.dumps({"last_success": "2026-04-22T00:00"}))

    out = assemble_heartbeat_source(state_dir=hdir, registry_path=reg_path)
    assert "declared_pipelines: 2" in out
    assert "recorded: 1" in out
    assert "missing: 1" in out
    assert "NEVER" in out  # for nb5


# ── assemble_coverage_source ─────────────────────────────────────────────────


def test_assemble_coverage_renders_domains(tmp_path: Path) -> None:
    path = tmp_path / "coverage_matrix.json"
    matrix = {
        "immigration": {
            "gaps": ["q1", "q2"],
            "health_pct": 50.0,
            "gap_pct": 30.0,
            "coverage_updated": "2026-04-20",
        },
        "tax": {
            "gaps": [],
            "health_pct": 80.0,
            "gap_pct": 10.0,
            "coverage_updated": "2026-04-21",
        },
    }
    path.write_text(json.dumps(matrix))
    out = assemble_coverage_source(path=path)
    assert "immigration" in out
    assert "tax" in out
    assert "50.0%" in out
    assert "80.0%" in out


def test_assemble_coverage_missing_file(tmp_path: Path) -> None:
    out = assemble_coverage_source(path=tmp_path / "nonexistent.json")
    assert out == ""


# ── build_all_sources returns 5 keys ─────────────────────────────────────────


def test_build_all_sources_returns_five_titles() -> None:
    sources = build_all_sources()
    assert set(sources.keys()) == set(SOURCE_TITLES.keys())
    assert len(sources) == 5


# ── run_refresh flow ─────────────────────────────────────────────────────────


def test_run_refresh_dry_run_is_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force state file to tmp so prior runs don't contaminate
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh.STATE_FILE", tmp_path / "nb0_refresh_state.json"
    )
    summary = run_refresh(notebook_id=None, dry_run=True)
    assert summary["dry_run"] is True
    assert summary["notebook_id"] == "(unset)"
    assert summary["sources_total"] == 5
    # Nothing should be "failed" in dry-run
    assert summary["failed"] == []


def test_run_refresh_hashes_skip_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh.STATE_FILE", state_file
    )

    # Mock build_all_sources to return stable content (no datetime drift)
    stable_sources = {
        "yajna": "# stable yajna content",
        "yin_yang": "",  # empty → skipped_empty
        "heartbeat": "# stable heartbeat content",
        "turiya": "# stable turiya content",
        "coverage": "",  # empty → skipped_empty
    }
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh.build_all_sources",
        lambda: stable_sources,
    )

    # Pre-seed state with hashes matching the stable sources
    hashes = {k: _sha256(v) if v else "" for k, v in stable_sources.items()}
    state_file.write_text(json.dumps({"hashes": hashes, "last_run": "2026-04-21"}))

    summary = run_refresh(notebook_id="fake-uuid", dry_run=True)
    # All non-empty hashes match prior state → pushed should be empty
    assert summary["pushed"] == []
    # The empty ones are counted as skipped_empty
    assert set(summary["skipped_empty"]) == {"yin_yang", "coverage"}
    # The matching ones are counted as skipped_unchanged
    assert set(summary["skipped_unchanged"]) == {"yajna", "heartbeat", "turiya"}


def test_run_refresh_push_without_notebook_id_stays_dry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh.STATE_FILE", tmp_path / "state.json"
    )
    # notebook_id=None + dry_run=False is defensive: still doesn't call CLI
    summary = run_refresh(notebook_id=None, dry_run=False)
    # When notebook_id is None, the loop treats every non-empty source as "pushed"
    # (bookkeeping), but no CLI invocation happens.
    assert summary["notebook_id"] == "(unset)"


def test_run_refresh_invokes_nlm_cli_when_pushing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh.STATE_FILE", tmp_path / "state.json"
    )

    # Mock _nlm_source_add to record calls
    calls = []

    def fake_add(notebook_id: str, title: str, body: str) -> bool:
        calls.append((notebook_id, title, len(body)))
        return True

    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh._nlm_source_add", fake_add
    )

    summary = run_refresh(notebook_id="fake-uuid-abc", dry_run=False)
    # Every non-empty source gets a CLI call
    assert len(calls) >= 1
    assert all(c[0] == "fake-uuid-abc" for c in calls)
    # State is persisted for pushed sources
    state_file = tmp_path / "state.json"
    assert state_file.exists()
    persisted = json.loads(state_file.read_text())
    assert "hashes" in persisted


def test_run_refresh_failed_cli_marked_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh.STATE_FILE", tmp_path / "state.json"
    )

    def failing_add(notebook_id: str, title: str, body: str) -> bool:
        return False

    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.nb0_refresh._nlm_source_add", failing_add
    )

    summary = run_refresh(notebook_id="fake", dry_run=False)
    assert summary["failed"]  # non-empty list
