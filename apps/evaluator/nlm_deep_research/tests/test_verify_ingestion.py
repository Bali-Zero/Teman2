"""Regression tests for verify_ingestion_uuid (Sprint 1 S1.2).

Covers the happy path (marker returned by NLM), the STALE path (marker
missing in answer → notebook ingestion is broken), and the failure paths
(upload error, query timeout). Uses monkeypatch on subprocess.run to
avoid touching real NotebookLM cloud.
"""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research import freshness_monitor as fm


def _fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a CompletedProcess-like object for mocking."""
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_verify_ingestion_dry_run_skips_cli():
    """--dry-run returns ok without touching NLM."""
    result = fm.verify_ingestion_uuid("dummy-nb-id", dry_run=True)
    assert result["status"] == "ok"
    assert result["error"] == "dry_run"


def test_verify_ingestion_happy_path(tmp_path, monkeypatch):
    """Upload succeeds, query returns the injected marker → status=ok."""
    # Redirect state file into tmp_path
    monkeypatch.setattr(
        fm, "FRESHNESS_STATE_FILE", tmp_path / "freshness_monitor_state.json"
    )

    captured_marker: dict[str, str] = {}

    def fake_run(cmd, **kwargs):
        if cmd[1] == "source" and cmd[2] == "add":
            # Extract marker from the --text payload
            text_idx = cmd.index("--text") + 1
            text = cmd[text_idx]
            # marker is the 12-char hex after "Query marker:"
            marker_line = [line for line in text.splitlines() if "Query marker:" in line][0]
            captured_marker["m"] = marker_line.split("Query marker:")[1].strip().rstrip(".")
            return _fake_completed(stdout=f"Source ID: fake-src-id\n✓ Added")
        if cmd[1] == "notebook" and cmd[2] == "query":
            # Echo the marker back as if NLM found it
            m = captured_marker.get("m", "")
            return _fake_completed(stdout=f"Found the marker: {m}")
        if cmd[1] == "source" and cmd[2] == "delete":
            return _fake_completed(stdout="deleted")
        pytest.fail(f"unexpected subprocess command: {cmd}")

    with patch.object(fm, "time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0)):
        with patch.object(fm.subprocess, "run", side_effect=fake_run):
            result = fm.verify_ingestion_uuid("nb-id", poll_seconds=0)

    assert result["status"] == "ok"
    assert result["error"] is None
    assert result["source_id"] == "fake-src-id"
    # State persisted
    saved = json.loads((tmp_path / "freshness_monitor_state.json").read_text())
    assert "ingestion_verifications" in saved
    assert saved["ingestion_verifications"]["nb-id"]["last"]["status"] == "ok"


def test_verify_ingestion_stale_when_marker_missing(tmp_path, monkeypatch):
    """Upload ok, query returns answer without marker → status=stale."""
    monkeypatch.setattr(
        fm, "FRESHNESS_STATE_FILE", tmp_path / "freshness_monitor_state.json"
    )

    def fake_run(cmd, **kwargs):
        if cmd[1] == "source" and cmd[2] == "add":
            return _fake_completed(stdout="Source ID: fake-src-id")
        if cmd[1] == "notebook" and cmd[2] == "query":
            # Answer that does NOT contain the marker
            return _fake_completed(stdout="Sorry, I could not find that in the sources.")
        if cmd[1] == "source" and cmd[2] == "delete":
            return _fake_completed(stdout="")
        pytest.fail(f"unexpected command: {cmd}")

    with patch.object(fm, "time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0)):
        with patch.object(fm.subprocess, "run", side_effect=fake_run):
            result = fm.verify_ingestion_uuid("nb-stale", poll_seconds=0)

    assert result["status"] == "stale"
    assert "marker not found" in (result["error"] or "")


def test_verify_ingestion_upload_failure(tmp_path, monkeypatch):
    """`nlm source add` nonzero exit → status=error, query skipped."""
    monkeypatch.setattr(
        fm, "FRESHNESS_STATE_FILE", tmp_path / "freshness_monitor_state.json"
    )

    def fake_run(cmd, **kwargs):
        if cmd[1] == "source" and cmd[2] == "add":
            return _fake_completed(
                stdout="", stderr="upload rejected: quota exceeded", returncode=1
            )
        pytest.fail(f"query should not be called after upload failure, got: {cmd}")

    with patch.object(fm, "time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0)):
        with patch.object(fm.subprocess, "run", side_effect=fake_run):
            result = fm.verify_ingestion_uuid("nb-upfail", poll_seconds=0)

    assert result["status"] == "error"
    assert "source add failed" in (result["error"] or "")
    assert result["source_id"] is None


def test_verify_ingestion_query_timeout(tmp_path, monkeypatch):
    """Query subprocess raises TimeoutExpired → status=error."""
    monkeypatch.setattr(
        fm, "FRESHNESS_STATE_FILE", tmp_path / "freshness_monitor_state.json"
    )

    def fake_run(cmd, **kwargs):
        if cmd[1] == "source" and cmd[2] == "add":
            return _fake_completed(stdout="Source ID: fake-id")
        if cmd[1] == "notebook" and cmd[2] == "query":
            raise subprocess.TimeoutExpired(cmd, 60)
        pytest.fail(f"unexpected: {cmd}")

    with patch.object(fm, "time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0)):
        with patch.object(fm.subprocess, "run", side_effect=fake_run):
            result = fm.verify_ingestion_uuid("nb-qtimeout", poll_seconds=0)

    assert result["status"] == "error"
    assert "timed out" in (result["error"] or "")


def test_verify_ingestion_persists_rolling_history(tmp_path, monkeypatch):
    """Multiple runs accumulate in history (max 20)."""
    state_file = tmp_path / "freshness_monitor_state.json"
    monkeypatch.setattr(fm, "FRESHNESS_STATE_FILE", state_file)

    # Seed state with 19 prior history entries
    prior = {
        "ingestion_verifications": {
            "nb-x": {
                "last": None,
                "history": [{"ts": "prior", "status": "ok", "uuid": "zzz", "age_seconds": 1, "error": None}] * 19,
            }
        }
    }
    state_file.write_text(json.dumps(prior))

    def fake_run(cmd, **kwargs):
        if cmd[1] == "source" and cmd[2] == "add":
            return _fake_completed(stdout="Source ID: s1")
        if cmd[1] == "notebook" and cmd[2] == "query":
            # No marker echo — so status=stale. Good for this test.
            return _fake_completed(stdout="empty")
        return _fake_completed(stdout="")

    with patch.object(fm, "time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0)):
        with patch.object(fm.subprocess, "run", side_effect=fake_run):
            fm.verify_ingestion_uuid("nb-x", poll_seconds=0)

    saved = json.loads(state_file.read_text())
    entry = saved["ingestion_verifications"]["nb-x"]
    # After append, history should be max 20 (prior 19 + new 1)
    assert len(entry["history"]) == 20
    assert entry["last"]["status"] == "stale"
