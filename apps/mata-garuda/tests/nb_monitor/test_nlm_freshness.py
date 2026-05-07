"""Tests for nb_monitor.collectors.nlm_freshness."""
from __future__ import annotations

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from mata_garuda.scripts.nb_monitor.collectors.nlm_freshness import (
    fetch_source_count,
    fetch_source_freshness_age_days,
    NLMFreshnessError,
)


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["nlm"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_fetch_source_count_parses_json_output():
    fake_out = '{"sources": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]}'
    with patch("subprocess.run", return_value=_completed(fake_out)):
        n = fetch_source_count("uuid-1")
    assert n == 3


def test_fetch_source_count_returns_none_on_cookie_error():
    with patch(
        "subprocess.run",
        return_value=_completed("Authentication required: re-run nlm login", returncode=1),
    ):
        n = fetch_source_count("uuid-1")
    assert n is None


def test_fetch_source_count_returns_none_on_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nlm", timeout=10)):
        n = fetch_source_count("uuid-1")
    assert n is None


def test_fetch_source_freshness_age_days_uses_oldest_source():
    """Median age across N sources, in days, rounded down."""
    fake_out = (
        '{"sources":['
        '{"updated_at":"2026-04-01T00:00:00Z"},'
        '{"updated_at":"2026-05-01T00:00:00Z"},'
        '{"updated_at":"2026-04-15T00:00:00Z"}'
        "]}"
    )
    with patch("subprocess.run", return_value=_completed(fake_out)):
        age = fetch_source_freshness_age_days(
            "uuid-1", now_iso="2026-05-07T00:00:00Z"
        )
    assert age == 22


def test_fetch_source_freshness_age_days_returns_none_on_empty_sources():
    fake_out = '{"sources": []}'
    with patch("subprocess.run", return_value=_completed(fake_out)):
        age = fetch_source_freshness_age_days("uuid-1", now_iso="2026-05-07T00:00:00Z")
    assert age is None


def test_fetch_source_freshness_age_days_returns_none_on_malformed():
    with patch("subprocess.run", return_value=_completed("not json")):
        age = fetch_source_freshness_age_days("uuid-1", now_iso="2026-05-07T00:00:00Z")
    assert age is None


def test_subprocess_uses_get_command_not_info():
    """Regression guard: nlm CLI removed 'notebook info' — use 'notebook get'.

    Reference: 2026-05-07 first cron run logged returncode=2 because
    `nlm notebook info` does not exist. Real command is `nlm notebook get`.
    """
    captured: dict = {}

    def _capture(args, **kwargs):
        captured["args"] = args
        return _completed('{"sources": []}')

    with patch("subprocess.run", side_effect=_capture):
        fetch_source_count("uuid-1")
    assert captured["args"][:3] == ["nlm", "notebook", "get"], (
        f"Expected ['nlm', 'notebook', 'get'], got {captured['args'][:3]}"
    )


def test_fetch_source_count_handles_nested_value_wrapper():
    """Real schema wraps body in {"value": {...}} (verified 2026-05-08)."""
    real_schema = (
        '{"value": {"notebook_id": "uuid-1", "sources": ['
        '{"id": "s1", "title": "feed_a.txt"},'
        '{"id": "s2", "title": "feed_b.txt"},'
        '{"id": "s3", "title": "feed_c.txt"}'
        "]}}"
    )
    with patch("subprocess.run", return_value=_completed(real_schema)):
        n = fetch_source_count("uuid-1")
    assert n == 3


def test_fetch_source_freshness_real_schema_returns_none():
    """Real-world schema (no timestamp fields) → returns None gracefully.

    Reference: empirical 2026-05-08 — `nlm notebook get <uuid> --json` returns
    sources as [{"id", "title"}] without updated_at/created_at. Until an
    alternative timestamp source is wired (design doc 2026-05-08), this
    function returns None on every real call even when the call succeeds.
    """
    real_schema = (
        '{"value": {"notebook_id": "uuid-1", "sources": ['
        '{"id": "s1", "title": "feed_a.txt"},'
        '{"id": "s2", "title": "feed_b.txt"}'
        "]}}"
    )
    with patch("subprocess.run", return_value=_completed(real_schema)):
        age = fetch_source_freshness_age_days("uuid-1", now_iso="2026-05-07T00:00:00Z")
    assert age is None
