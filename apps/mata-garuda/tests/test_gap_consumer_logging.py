"""Tests for gap_consumer.main split-stream logging — W8 cicatrix 2026-05-22."""
from __future__ import annotations

import io
import logging
import sys
from unittest.mock import patch


def _reset_root_logger():
    """Strip handlers + reset level so subsequent main() calls re-initialize."""
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.WARNING)


def test_main_routes_info_to_stdout(monkeypatch):
    """W8 cicatrix 2026-05-22 — INFO and below must hit stdout (silent in
    launchd `.error.log`)."""
    _reset_root_logger()
    fake_stdout = io.StringIO()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    from mata_garuda.workers import gap_consumer

    with patch.object(gap_consumer, "run_gap_consumer", lambda: None):
        gap_consumer.main()

    logger = logging.getLogger("test.gap_consumer")
    logger.info("INFO line — should go to stdout")
    logger.debug("DEBUG line — should also go to stdout")

    assert "INFO line" in fake_stdout.getvalue()
    assert "INFO line" not in fake_stderr.getvalue()


def test_main_routes_warning_to_stderr(monkeypatch):
    """WARNING and above must hit stderr (launchd `.error.log` shows real signal)."""
    _reset_root_logger()
    fake_stdout = io.StringIO()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    from mata_garuda.workers import gap_consumer

    with patch.object(gap_consumer, "run_gap_consumer", lambda: None):
        gap_consumer.main()

    logger = logging.getLogger("test.gap_consumer")
    logger.warning("WARN line — should go to stderr")
    logger.error("ERROR line — should also go to stderr")

    assert "WARN line" in fake_stderr.getvalue()
    assert "WARN line" not in fake_stdout.getvalue()
    assert "ERROR line" in fake_stderr.getvalue()


def test_main_replaces_preexisting_handlers(monkeypatch):
    """If basicConfig was called earlier in the import chain (legacy
    behaviour), main() must REPLACE handlers so the split routing is the
    sole behaviour — not just append to a single stderr stream."""
    _reset_root_logger()
    # Pre-install a single stderr handler (legacy basicConfig shape).
    legacy_stderr = io.StringIO()
    legacy = logging.StreamHandler(legacy_stderr)
    legacy.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(legacy)

    fake_stdout = io.StringIO()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    from mata_garuda.workers import gap_consumer

    with patch.object(gap_consumer, "run_gap_consumer", lambda: None):
        gap_consumer.main()

    logger = logging.getLogger("test.gap_consumer")
    logger.info("INFO line")

    # Legacy handler must no longer receive logs.
    assert "INFO line" not in legacy_stderr.getvalue()
    # Only the new stdout handler should have it.
    assert "INFO line" in fake_stdout.getvalue()
