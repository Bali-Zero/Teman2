"""Regression tests for truth_dashboard() — S0.5 honest monitoring (2026-04-25).

Covers the scenario where gateway-written .last.json has fresh mtime but
stale ts, which is the "self-repair cieco" pattern that motivated the
pipeline_truth_dashboard view.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.evaluator.nlm_deep_research.heartbeat_monitor import (
    WITA,
    truth_dashboard,
)


def test_arch9_fresh_log_today_is_ok(tmp_path: Path) -> None:
    """Both heartbeat ARCH-9 and today log present → OK."""
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()

    now = datetime.now(tz=WITA)

    # ARCH-9 heartbeat fresh
    (state_dir / "heartbeat_nb2_pipeline.json").write_text(
        json.dumps({
            "pipeline": "nb2_pipeline",
            "last_success": (now - timedelta(hours=2)).isoformat(),
            "duration_seconds": 60.0,
        })
    )

    # Today log exists
    today_stamp = now.strftime("%Y%m%d")
    log_file = logs_dir / f"nb2_pipeline_{today_stamp}.log"
    log_file.write_text("02:10 [NB2] Starting pipeline\nOK\n")

    rows = truth_dashboard(
        registry={"nb2_pipeline": {"schedule": "weekday", "max_age_hours": 6}},
        state_dir=state_dir,
        logs_dir=logs_dir,
        today=now,
    )

    assert len(rows) == 1
    assert rows[0]["pipeline"] == "nb2_pipeline"
    assert rows[0]["verdict"] == "OK"
    assert rows[0]["arch9"]["fresh"] is True
    assert rows[0]["log"]["exists_today"] is True


def test_gateway_lies_detected(tmp_path: Path) -> None:
    """Gateway projection fresh BUT no ARCH-9 and no today log → GATEWAY_LIES.

    Classic self-repair cieco pattern: mtime of gateway .last.json is fresh
    (written 5 min ago) but the ts inside is 10 days old. This test proves
    truth_dashboard flags this as a lie rather than reporting 'OK'.
    """
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()

    now = datetime.now(tz=WITA)

    # Gateway projection with fresh-looking ts but inside structure is stale
    # max_age_hours=6 → fresh means ts < 6h ago
    fresh_ts = now.timestamp() - 3600  # 1h ago — fresh per max_age=6
    (state_dir / "nlm_nb3_company_setup.last.json").write_text(
        json.dumps({
            "job": "nlm-nb3-company-setup",
            "ts": fresh_ts,
            "status": "ok",
            "source": "openclaw-bridge",
        })
    )
    # NO heartbeat ARCH-9 file, NO log today

    rows = truth_dashboard(
        registry={"nb3_pipeline": {"schedule": "weekday", "max_age_hours": 6}},
        state_dir=state_dir,
        logs_dir=logs_dir,
        today=now,
    )

    assert len(rows) == 1
    r = rows[0]
    assert r["verdict"] == "GATEWAY_LIES"
    assert r["gateway"]["fresh"] is True      # gateway claims fresh
    assert r["arch9"]["present"] is False      # but no real evidence
    assert r["log"]["exists_today"] is False


def test_log_exists_no_heartbeat_is_incomplete(tmp_path: Path) -> None:
    """Script ran today (log exists) but didn't record success → LOG_NO_HEARTBEAT.

    Exact state of nb2_pipeline after manual force-run on 2026-04-25.
    """
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()

    now = datetime.now(tz=WITA)
    today_stamp = now.strftime("%Y%m%d")

    # Log exists but no heartbeat_ file
    log = logs_dir / f"nb2_pipeline_{today_stamp}.log"
    log.write_text("02:10 [NB2] Starting\n... ran into error\n")

    rows = truth_dashboard(
        registry={"nb2_pipeline": {"schedule": "weekday", "max_age_hours": 6}},
        state_dir=state_dir,
        logs_dir=logs_dir,
        today=now,
    )

    assert len(rows) == 1
    assert rows[0]["verdict"] == "LOG_NO_HEARTBEAT"
    assert rows[0]["log"]["exists_today"] is True
    assert rows[0]["arch9"]["present"] is False


def test_fully_dead_pipeline(tmp_path: Path) -> None:
    """No signals at all → DEAD."""
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()

    now = datetime.now(tz=WITA)

    rows = truth_dashboard(
        registry={"nb5_pipeline": {"schedule": "weekday", "max_age_hours": 6}},
        state_dir=state_dir,
        logs_dir=logs_dir,
        today=now,
    )

    assert rows[0]["verdict"] == "DEAD"
