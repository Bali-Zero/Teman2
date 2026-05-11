"""Tests for nb_monitor.collectors.feeder_log."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.collectors.feeder_log import (
    parse_feeder_log,
    compute_global_push_success_rate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_feeder_log_extracts_alerts_and_enriched():
    rows = list(parse_feeder_log(FIXTURES / "feeder_sample.jsonl"))
    assert len(rows) == 4
    first = rows[0]
    assert first["alerts"]["processed"] == 10
    assert first["alerts"]["fed"] == 9
    assert first["alerts"]["errors"] == 0


def test_parse_feeder_log_skips_malformed():
    rows = list(parse_feeder_log(FIXTURES / "feeder_sample.jsonl"))
    assert all("not" not in (r.get("agent") or "") for r in rows)


def test_parse_feeder_log_returns_empty_for_missing_file(tmp_path):
    rows = list(parse_feeder_log(tmp_path / "nope.log"))
    assert rows == []


def test_compute_global_push_success_rate_uses_alerts_plus_enriched():
    rate = compute_global_push_success_rate(
        FIXTURES / "feeder_sample.jsonl", window_seconds=10**9
    )
    assert rate is not None
    assert 0.86 <= rate <= 0.88


def test_compute_global_push_success_rate_returns_none_when_no_processed(tmp_path):
    p = tmp_path / "empty_feeder.jsonl"
    p.write_text(
        '{"alerts":{"processed":0,"fed":0,"skipped":0,"errors":0},"enriched":{"processed":0,"fed":0,"skipped":0,"errors":0}}\n'
    )
    rate = compute_global_push_success_rate(p, window_seconds=10**9)
    assert rate is None


def test_compute_global_push_success_rate_filters_by_mtime(tmp_path):
    p = tmp_path / "old_feeder.jsonl"
    p.write_text(
        '{"alerts":{"processed":10,"fed":9,"skipped":0,"errors":1},"enriched":{"processed":0,"fed":0,"skipped":0,"errors":0}}\n'
    )
    long_ago = int(time.time()) - 30 * 86400
    os.utime(p, (long_ago, long_ago))
    rate = compute_global_push_success_rate(p, window_seconds=7 * 86400)
    assert rate is None


def test_compute_global_push_success_rate_handles_stats_legacy_shape(tmp_path):
    p = tmp_path / "legacy.jsonl"
    p.write_text(
        '{"agent":"nlm_feeder_stream","stats":{"processed":10,"fed":7,"skipped":0,"errors":3}}\n'
    )
    rate = compute_global_push_success_rate(p, window_seconds=10**9)
    assert rate == 0.7
