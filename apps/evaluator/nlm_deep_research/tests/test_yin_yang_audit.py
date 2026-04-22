"""Tests for yin_yang_audit weekly balance check."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.yin_yang_audit import (
    STATUS_HEALTHY,
    STATUS_YANG_FLOOD,
    STATUS_YIN_FAMINE,
    STATUS_UNKNOWN,
    YANG_FLOOD_THRESHOLD,
    YIN_FAMINE_THRESHOLD,
    build_recommendations,
    classify_ratio,
    compute_nb_ratios,
    detect_streaks,
    load_latest_metrics,
    run_audit,
)


# ── classify_ratio ───────────────────────────────────────────────────────────


def test_classify_ratio_bands() -> None:
    assert classify_ratio(1.0) == STATUS_HEALTHY
    assert classify_ratio(0.5) == STATUS_HEALTHY  # inclusive lower bound
    assert classify_ratio(3.0) == STATUS_HEALTHY  # inclusive upper bound
    assert classify_ratio(0.49) == STATUS_YIN_FAMINE
    assert classify_ratio(3.01) == STATUS_YANG_FLOOD
    assert classify_ratio(0) == STATUS_UNKNOWN
    assert classify_ratio(-1) == STATUS_UNKNOWN


# ── compute_nb_ratios ────────────────────────────────────────────────────────


def test_compute_nb_ratios_healthy_balance() -> None:
    metrics = {
        "per_nb": {
            "nb4": {"offered": 10, "cited": 5, "promoted": 0},
        }
    }
    out = compute_nb_ratios(metrics)
    # ratio = 10 / (5 + 0 + 1) = 10/6 = 1.667 → HEALTHY
    assert out["nb4"]["ratio"] == round(10 / 6, 3)
    assert out["nb4"]["status"] == STATUS_HEALTHY


def test_compute_nb_ratios_yang_flood() -> None:
    metrics = {"per_nb": {"nb5": {"offered": 50, "cited": 2, "promoted": 1}}}
    out = compute_nb_ratios(metrics)
    # 50 / 4 = 12.5 → YANG_FLOOD
    assert out["nb5"]["status"] == STATUS_YANG_FLOOD


def test_compute_nb_ratios_yin_famine() -> None:
    metrics = {"per_nb": {"nb3": {"offered": 2, "cited": 5, "promoted": 3}}}
    out = compute_nb_ratios(metrics)
    # 2 / 9 = 0.222 → YIN_FAMINE
    assert out["nb3"]["status"] == STATUS_YIN_FAMINE


def test_compute_nb_ratios_zero_activity() -> None:
    metrics = {"per_nb": {"nb6": {"offered": 0, "cited": 0, "promoted": 0}}}
    out = compute_nb_ratios(metrics)
    # 0 / 1 = 0 → UNKNOWN (not YIN_FAMINE, because no production at all)
    assert out["nb6"]["ratio"] == 0
    assert out["nb6"]["status"] == STATUS_UNKNOWN


def test_compute_nb_ratios_empty_input() -> None:
    assert compute_nb_ratios({}) == {}
    assert compute_nb_ratios({"per_nb": {}}) == {}


# ── detect_streaks ───────────────────────────────────────────────────────────


def test_detect_streaks_single_week_not_adjustable() -> None:
    current = {"nb5": {"offered": 50, "cited": 2, "promoted": 1, "ratio": 12.5, "status": STATUS_YANG_FLOOD}}
    streaks = detect_streaks(audits=[], current_per_nb=current)
    assert streaks["nb5"]["consecutive_weeks"] == 1
    assert streaks["nb5"]["adjustable"] is False


def test_detect_streaks_two_weeks_adjustable() -> None:
    prior_audit = {"per_nb": {"nb5": {"status": STATUS_YANG_FLOOD}}}
    current = {"nb5": {"offered": 50, "cited": 2, "promoted": 1, "ratio": 12.5, "status": STATUS_YANG_FLOOD}}
    streaks = detect_streaks(audits=[prior_audit], current_per_nb=current)
    assert streaks["nb5"]["consecutive_weeks"] == 2
    assert streaks["nb5"]["adjustable"] is True


def test_detect_streaks_three_weeks() -> None:
    prior = [
        {"per_nb": {"nb5": {"status": STATUS_YANG_FLOOD}}},
        {"per_nb": {"nb5": {"status": STATUS_YANG_FLOOD}}},
    ]
    current = {"nb5": {"offered": 50, "cited": 2, "promoted": 1, "ratio": 12.5, "status": STATUS_YANG_FLOOD}}
    streaks = detect_streaks(audits=prior, current_per_nb=current)
    assert streaks["nb5"]["consecutive_weeks"] == 3


def test_detect_streaks_interrupted_resets() -> None:
    prior = [
        {"per_nb": {"nb5": {"status": STATUS_YANG_FLOOD}}},
        {"per_nb": {"nb5": {"status": STATUS_HEALTHY}}},  # interruption
    ]
    current = {"nb5": {"offered": 50, "cited": 2, "promoted": 1, "ratio": 12.5, "status": STATUS_YANG_FLOOD}}
    streaks = detect_streaks(audits=prior, current_per_nb=current)
    assert streaks["nb5"]["consecutive_weeks"] == 1
    assert streaks["nb5"]["adjustable"] is False


def test_detect_streaks_healthy_never_adjustable() -> None:
    prior = [{"per_nb": {"nb4": {"status": STATUS_HEALTHY}}}] * 5
    current = {"nb4": {"offered": 10, "cited": 5, "ratio": 1.6, "status": STATUS_HEALTHY, "promoted": 0}}
    streaks = detect_streaks(audits=prior, current_per_nb=current)
    assert streaks["nb4"]["adjustable"] is False


# ── build_recommendations ────────────────────────────────────────────────────


def test_build_recommendations_yang_flood_auto_enabled() -> None:
    streaks = {"nb5": {"adjustable": True, "current_status": STATUS_YANG_FLOOD, "consecutive_weeks": 2}}
    recs = build_recommendations(streaks, auto_enabled=True)
    assert len(recs) == 1
    assert recs[0]["nb"] == "nb5"
    assert recs[0]["action"] == "synth_cadence_to_daily"
    assert recs[0]["auto_applied"] is True
    assert recs[0]["reversible"] is True


def test_build_recommendations_yang_flood_kill_switch() -> None:
    streaks = {"nb5": {"adjustable": True, "current_status": STATUS_YANG_FLOOD, "consecutive_weeks": 2}}
    recs = build_recommendations(streaks, auto_enabled=False)
    assert recs[0]["action"] == "propose_synth_cadence_to_daily"
    assert recs[0]["auto_applied"] is False


def test_build_recommendations_yin_famine_never_auto_applied() -> None:
    streaks = {"nb3": {"adjustable": True, "current_status": STATUS_YIN_FAMINE, "consecutive_weeks": 2}}
    # Even with auto enabled, YIN_FAMINE is always propose-only (adding cluster = irreversible work)
    recs = build_recommendations(streaks, auto_enabled=True)
    assert recs[0]["action"] == "propose_add_cluster_rotation"
    assert recs[0]["auto_applied"] is False
    assert recs[0]["reversible"] is False


def test_build_recommendations_filters_non_adjustable() -> None:
    streaks = {
        "nb4": {"adjustable": False, "current_status": STATUS_YANG_FLOOD, "consecutive_weeks": 1},
        "nb5": {"adjustable": True, "current_status": STATUS_YANG_FLOOD, "consecutive_weeks": 2},
    }
    recs = build_recommendations(streaks, auto_enabled=True)
    assert len(recs) == 1
    assert recs[0]["nb"] == "nb5"


# ── run_audit integration ────────────────────────────────────────────────────


def test_run_audit_no_metrics(tmp_path: Path) -> None:
    metrics_file = tmp_path / "yajna_metrics.jsonl"  # doesn't exist
    state_file = tmp_path / "yin_yang_state.jsonl"
    audit = run_audit(metrics_file=metrics_file, state_file=state_file)
    assert audit["status"] == "no_metrics"
    assert audit["per_nb"] == {}
    # State file still written (audit marker exists)
    assert state_file.exists()


def test_run_audit_healthy_nb_writes_zero_recs(tmp_path: Path) -> None:
    metrics_file = tmp_path / "yajna_metrics.jsonl"
    state_file = tmp_path / "yin_yang_state.jsonl"
    metrics_line = {
        "window_days": 30,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "per_nb": {"nb4": {"offered": 10, "cited": 5, "promoted": 2}},
    }
    metrics_file.write_text(json.dumps(metrics_line) + "\n")

    audit = run_audit(metrics_file=metrics_file, state_file=state_file)
    assert audit["per_nb"]["nb4"]["status"] == STATUS_HEALTHY
    assert audit["recommendations"] == []


def test_run_audit_detects_two_week_yang_flood_streak(tmp_path: Path) -> None:
    metrics_file = tmp_path / "yajna_metrics.jsonl"
    state_file = tmp_path / "yin_yang_state.jsonl"

    # Prior audit: yang flood last week
    prior_audit = {
        "ts": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "per_nb": {"nb5": {"offered": 50, "cited": 2, "promoted": 1, "ratio": 12.5, "status": STATUS_YANG_FLOOD}},
        "recommendations": [],
    }
    state_file.write_text(json.dumps(prior_audit) + "\n")

    # Current metrics: same yang flood
    metrics_line = {
        "window_days": 30,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "per_nb": {"nb5": {"offered": 40, "cited": 1, "promoted": 1}},
    }
    metrics_file.write_text(json.dumps(metrics_line) + "\n")

    audit = run_audit(metrics_file=metrics_file, state_file=state_file)
    assert len(audit["recommendations"]) == 1
    rec = audit["recommendations"][0]
    assert rec["nb"] == "nb5"
    assert rec["action"].endswith("synth_cadence_to_daily")


def test_run_audit_kill_switch_marks_recommendations_propose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YIN_YANG_AUTO_DISABLED", "1")
    metrics_file = tmp_path / "yajna_metrics.jsonl"
    state_file = tmp_path / "yin_yang_state.jsonl"

    prior_audit = {
        "ts": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "per_nb": {"nb5": {"status": STATUS_YANG_FLOOD}},
    }
    state_file.write_text(json.dumps(prior_audit) + "\n")

    metrics_line = {
        "window_days": 30,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "per_nb": {"nb5": {"offered": 40, "cited": 1, "promoted": 1}},
    }
    metrics_file.write_text(json.dumps(metrics_line) + "\n")

    audit = run_audit(metrics_file=metrics_file, state_file=state_file)
    assert audit["auto_adjust_enabled"] is False
    assert audit["recommendations"][0]["auto_applied"] is False
    assert "propose" in audit["recommendations"][0]["action"]


# ── load_latest_metrics ──────────────────────────────────────────────────────


def test_load_latest_metrics_returns_last_line(tmp_path: Path) -> None:
    path = tmp_path / "yajna_metrics.jsonl"
    path.write_text(
        json.dumps({"ts": "a", "totals": {"offered": 1}}) + "\n"
        + json.dumps({"ts": "b", "totals": {"offered": 2}}) + "\n"
        + json.dumps({"ts": "c", "totals": {"offered": 3}}) + "\n"
    )
    m = load_latest_metrics(path)
    assert m is not None
    assert m["totals"]["offered"] == 3


def test_load_latest_metrics_missing_file(tmp_path: Path) -> None:
    assert load_latest_metrics(tmp_path / "nonexistent.jsonl") is None
