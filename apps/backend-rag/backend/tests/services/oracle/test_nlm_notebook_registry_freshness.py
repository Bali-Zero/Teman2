"""Regression tests for S1.3 — NLM oracle gate on stale ingestion.

Covers:
  - check_ingestion_freshness against various state file shapes
  - resolve_notebook backward-compatible default (no gate, returns NB)
  - resolve_notebook with enforce_freshness=True (returns None when stale)
  - env var NLM_ENFORCE_FRESHNESS toggles default
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.services.oracle import nlm_notebook_registry as reg


def _write_state(path: Path, ingestion_verifications: dict) -> None:
    path.write_text(json.dumps({"ingestion_verifications": ingestion_verifications}))


# ── check_ingestion_freshness ────────────────────────────────────────────────

def test_freshness_fresh_when_recent_ok(tmp_path):
    state = tmp_path / "fresh_state.json"
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    _write_state(state, {
        "nb-1": {
            "last": {"started_at": now_iso, "status": "ok", "uuid": "abc123"},
            "history": [],
        }
    })
    verdict = reg.check_ingestion_freshness("nb-1", state_path=state)
    assert verdict["status"] == "fresh"
    assert verdict["last_status"] == "ok"
    assert verdict["age_hours"] is not None
    assert verdict["age_hours"] < 1  # just written
    assert verdict["last_uuid"] == "abc123"


def test_freshness_stale_when_canary_status_not_ok(tmp_path):
    state = tmp_path / "state.json"
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    _write_state(state, {
        "nb-1": {
            "last": {"started_at": now_iso, "status": "stale", "uuid": "x"},
        }
    })
    verdict = reg.check_ingestion_freshness("nb-1", state_path=state)
    assert verdict["status"] == "stale"
    assert "status=stale" in verdict["reason"]


def test_freshness_stale_when_too_old(tmp_path):
    state = tmp_path / "state.json"
    old = (datetime.now(tz=timezone.utc) - timedelta(hours=48)).isoformat()
    _write_state(state, {
        "nb-1": {
            "last": {"started_at": old, "status": "ok", "uuid": "x"},
        }
    })
    # Default threshold = 24h
    verdict = reg.check_ingestion_freshness("nb-1", state_path=state, max_stale_hours=24)
    assert verdict["status"] == "stale"
    assert verdict["age_hours"] > 24
    assert "threshold" in verdict["reason"]


def test_freshness_never_verified_when_no_entry(tmp_path):
    state = tmp_path / "state.json"
    _write_state(state, {})  # empty verifications dict
    verdict = reg.check_ingestion_freshness("never-seen-nb", state_path=state)
    assert verdict["status"] == "never_verified"
    assert "no canary verification" in verdict["reason"]


def test_freshness_handles_missing_state_file(tmp_path):
    state = tmp_path / "does_not_exist.json"
    verdict = reg.check_ingestion_freshness("any-nb", state_path=state)
    assert verdict["status"] == "never_verified"
    assert "not found" in verdict["reason"]


def test_freshness_handles_corrupt_json(tmp_path):
    state = tmp_path / "broken.json"
    state.write_text("{ not json")
    verdict = reg.check_ingestion_freshness("nb", state_path=state)
    assert verdict["status"] == "never_verified"
    assert "malformed" in verdict["reason"]


# ── resolve_notebook with enforce_freshness ──────────────────────────────────

def test_resolve_notebook_default_does_not_gate(tmp_path, monkeypatch):
    """Backward compatibility: default behavior is NO gating."""
    monkeypatch.delenv("NLM_ENFORCE_FRESHNESS", raising=False)
    result = reg.resolve_notebook("KITAS visa requirements")
    assert result is not None
    assert result["domain"] == "immigration"
    assert "freshness" not in result  # gate not invoked


def test_resolve_notebook_returns_none_when_stale_and_gated(tmp_path, monkeypatch):
    """enforce_freshness=True + stale state → None (caller falls back)."""
    state = tmp_path / "state.json"
    old = (datetime.now(tz=timezone.utc) - timedelta(hours=48)).isoformat()
    _write_state(state, {
        # Use the actual NB-2 UUID from registry
        "cff93ab0-813a-42f2-a8de-36987e724271": {
            "last": {"started_at": old, "status": "ok", "uuid": "x"},
        }
    })
    monkeypatch.setenv("NLM_FRESHNESS_STATE_FILE", str(state))
    result = reg.resolve_notebook(
        "KITAS visa requirements",
        enforce_freshness=True,
        max_stale_hours=24,
    )
    assert result is None


def test_resolve_notebook_returns_nb_when_fresh_and_gated(tmp_path, monkeypatch):
    """enforce_freshness=True + fresh state → NB returned with freshness verdict."""
    state = tmp_path / "state.json"
    now = datetime.now(tz=timezone.utc).isoformat()
    _write_state(state, {
        "cff93ab0-813a-42f2-a8de-36987e724271": {
            "last": {"started_at": now, "status": "ok", "uuid": "fresh"},
        }
    })
    monkeypatch.setenv("NLM_FRESHNESS_STATE_FILE", str(state))
    result = reg.resolve_notebook("KITAS visa", enforce_freshness=True)
    assert result is not None
    assert result["domain"] == "immigration"
    assert result["freshness"]["status"] == "fresh"


def test_resolve_notebook_env_var_enables_gate(tmp_path, monkeypatch):
    """NLM_ENFORCE_FRESHNESS=1 enables gating without explicit arg."""
    state = tmp_path / "state.json"
    _write_state(state, {})  # empty → never_verified
    monkeypatch.setenv("NLM_FRESHNESS_STATE_FILE", str(state))
    monkeypatch.setenv("NLM_ENFORCE_FRESHNESS", "1")
    result = reg.resolve_notebook("KITAS visa")
    assert result is None  # blocked by missing canary


def test_resolve_notebook_env_var_off_disables_gate(tmp_path, monkeypatch):
    """NLM_ENFORCE_FRESHNESS=0 keeps the gate disabled."""
    monkeypatch.setenv("NLM_ENFORCE_FRESHNESS", "0")
    result = reg.resolve_notebook("KITAS visa")
    assert result is not None
    assert "freshness" not in result


def test_resolve_notebook_explicit_false_overrides_env(tmp_path, monkeypatch):
    """Explicit enforce_freshness=False wins over env=1."""
    monkeypatch.setenv("NLM_ENFORCE_FRESHNESS", "1")
    result = reg.resolve_notebook("KITAS visa", enforce_freshness=False)
    assert result is not None
    assert "freshness" not in result
