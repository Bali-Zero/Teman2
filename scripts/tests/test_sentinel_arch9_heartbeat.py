"""
Regression tests for T16 fix — nuzantara-sentinel.py ARCH-9 heartbeat preference.

Covers the case where the openclaw-gateway writes a stale .last.json with
fresh mtime (self-repair cieco pattern) and the sentinel must prefer the
ARCH-9 native heartbeat_{name}.json as source of truth.

Root cause: research/nlm-elevation/08-s02-dispatcher-diagnosis.md.
Fix commit: T16 (2026-04-25).
"""
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _load_sentinel_module():
    """Load nuzantara-sentinel.py as module (hyphen in filename blocks direct import)."""
    repo_root = Path(__file__).resolve().parents[2]
    sentinel_path = repo_root / "scripts" / "nuzantara-sentinel.py"
    spec = importlib.util.spec_from_file_location("sentinel_under_test", sentinel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sentinel_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Run sentinel with isolated STATE_DIR so tests do not touch real files."""
    sentinel = _load_sentinel_module()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    # Patch module-level STATE_DIR
    monkeypatch.setattr(sentinel, "STATE_DIR", str(state_dir))
    # Prevent SSH fan-out in tests (we are not Pro-host by default)
    monkeypatch.setattr(sentinel, "PRO_HOST", os.uname().nodename)
    # Bypass the openclaw-bridge collector: we test heartbeat override
    # in isolation.
    monkeypatch.setattr(sentinel, "_collect_openclaw_states", lambda registry: {})
    return sentinel, state_dir


def test_arch9_heartbeat_overrides_stale_gateway(isolated_state_dir):
    """ARCH-9 heartbeat is newer than gateway projection → ARCH-9 wins."""
    sentinel, sdir = isolated_state_dir

    # Gateway projection with stale ts (Apr 14)
    stale_ts = datetime(2026, 4, 14, 0, 0, tzinfo=timezone.utc).timestamp()
    (sdir / "nlm_nb2_pipeline.last.json").write_text(json.dumps({
        "job": "nlm_nb2_pipeline",
        "ts": stale_ts,
        "status": "failed",
        "source": "openclaw-bridge",
        "last_error": "OpenClaw consecutiveErrors=0, lastStatus=pending",
    }))

    # ARCH-9 heartbeat with fresh ts (today)
    fresh_iso = datetime.now(tz=timezone.utc).isoformat()
    (sdir / "heartbeat_nb2_pipeline.json").write_text(json.dumps({
        "pipeline": "nb2_pipeline",
        "last_success": fresh_iso,
        "duration_seconds": 56.0,
    }))

    registry = {"nlm_nb2_pipeline": {"type": "openclaw"}}
    states = sentinel.collect_state_files(registry=registry)

    assert "nlm_nb2_pipeline" in states
    s = states["nlm_nb2_pipeline"]
    assert s["_source"] == "arch9_heartbeat"
    assert s["status"] == "ok"
    assert s["duration_seconds"] == 56.0
    # ts must be close to now, NOT Apr 14
    now_ts = datetime.now(tz=timezone.utc).timestamp()
    assert abs(s["ts"] - now_ts) < 5  # within 5s


def test_arch9_heartbeat_missing_falls_back_to_gateway(isolated_state_dir):
    """No ARCH-9 heartbeat → gateway projection wins (legacy behavior)."""
    sentinel, sdir = isolated_state_dir

    ts = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc).timestamp()
    (sdir / "nlm_nb5_pipeline.last.json").write_text(json.dumps({
        "job": "nlm_nb5_pipeline",
        "ts": ts,
        "status": "ok",
        "source": "openclaw-bridge",
    }))
    # No heartbeat_nb5_pipeline.json

    registry = {"nlm_nb5_pipeline": {"type": "openclaw"}}
    states = sentinel.collect_state_files(registry=registry)

    s = states["nlm_nb5_pipeline"]
    # Not arch9_heartbeat — gateway projection preserved
    assert s.get("_source") != "arch9_heartbeat"
    assert s["ts"] == ts


def test_arch9_older_than_existing_does_not_override(isolated_state_dir):
    """If an existing state has a newer ts than ARCH-9, do not override.

    Prevents regressing to an older timestamp when the pipeline just ran
    successfully via a different codepath that already wrote .last.json.
    """
    sentinel, sdir = isolated_state_dir

    # Gateway projection already has fresh ts (e.g. just ran via cron-agent)
    newer_ts = datetime.now(tz=timezone.utc).timestamp()
    (sdir / "nlm_nb3_pipeline.last.json").write_text(json.dumps({
        "job": "nlm_nb3_pipeline",
        "ts": newer_ts,
        "status": "ok",
        "source": "openclaw-bridge",
    }))

    # ARCH-9 heartbeat with older ts
    older_iso = (datetime.now(tz=timezone.utc) - timedelta(hours=12)).isoformat()
    (sdir / "heartbeat_nb3_pipeline.json").write_text(json.dumps({
        "pipeline": "nb3_pipeline",
        "last_success": older_iso,
    }))

    registry = {"nlm_nb3_pipeline": {"type": "openclaw"}}
    states = sentinel.collect_state_files(registry=registry)

    s = states["nlm_nb3_pipeline"]
    # Newer gateway ts preserved
    assert s["ts"] == newer_ts


def test_fuzzy_match_nb_prefix(isolated_state_dir):
    """heartbeat_nb2_pipeline matches registry key nlm_nb2_immigration via nbN prefix."""
    sentinel, sdir = isolated_state_dir

    fresh_iso = datetime.now(tz=timezone.utc).isoformat()
    (sdir / "heartbeat_nb2_pipeline.json").write_text(json.dumps({
        "pipeline": "nb2_pipeline",
        "last_success": fresh_iso,
    }))

    # Registry uses different naming than the heartbeat file
    registry = {"nlm_nb2_immigration": {"type": "openclaw"}}
    states = sentinel.collect_state_files(registry=registry)

    assert "nlm_nb2_immigration" in states
    assert states["nlm_nb2_immigration"]["_source"] == "arch9_heartbeat"


def test_heartbeat_without_last_success_is_ignored(isolated_state_dir):
    """Malformed ARCH-9 heartbeat (missing last_success) is silently skipped."""
    sentinel, sdir = isolated_state_dir

    (sdir / "heartbeat_nb4_pipeline.json").write_text(json.dumps({
        "pipeline": "nb4_pipeline",
        "duration_seconds": 30.0,
        # no last_success field
    }))

    # Also write a valid gateway projection so we can verify fallback
    ts = datetime(2026, 4, 20, tzinfo=timezone.utc).timestamp()
    (sdir / "nlm_nb4_pipeline.last.json").write_text(json.dumps({
        "job": "nlm_nb4_pipeline",
        "ts": ts,
        "status": "ok",
    }))

    registry = {"nlm_nb4_pipeline": {"type": "openclaw"}}
    states = sentinel.collect_state_files(registry=registry)

    s = states["nlm_nb4_pipeline"]
    # Not overridden — gateway projection stays
    assert s.get("_source") != "arch9_heartbeat"
    assert s["ts"] == ts
