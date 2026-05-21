"""Tests for health_tools consumer-group lag helpers — W5 cicatrix 2026-05-22."""
from __future__ import annotations

from unittest.mock import patch

from mata_garuda.tools import health_tools


_XINFO_GROUPS_OUTPUT = """name
nexus-bridge
consumers
1
pending
0
last-delivered-id
1777154510217-0
entries-read
1376
lag
2279
name
normalizer
consumers
1
pending
9
last-delivered-id
1778590659927-0
entries-read
2797
lag
858"""


def test_stream_groups_lag_parses_xinfo_output(monkeypatch):
    """Parse the alternating key/value lines produced by redis-cli XINFO GROUPS."""
    monkeypatch.setattr(health_tools, "_redis_cmd", lambda *a, **kw: _XINFO_GROUPS_OUTPUT)
    groups = health_tools.stream_groups_lag("garuda:raw")

    assert len(groups) == 2
    g1, g2 = groups
    assert g1["group"] == "nexus-bridge"
    assert g1["consumers"] == 1
    assert g1["pending"] == 0
    assert g1["lag"] == 2279
    assert g2["group"] == "normalizer"
    assert g2["pending"] == 9
    assert g2["lag"] == 858


def test_stream_groups_lag_empty_on_redis_unavailable(monkeypatch):
    """If redis-cli returns None, return []."""
    monkeypatch.setattr(health_tools, "_redis_cmd", lambda *a, **kw: None)
    assert health_tools.stream_groups_lag("garuda:raw") == []


def test_get_consumer_groups_lag_filters_by_threshold(monkeypatch):
    """Only groups with lag >= threshold are returned."""
    monkeypatch.setattr(health_tools, "HEALTH_STREAMS", ["garuda:raw"])
    monkeypatch.setattr(health_tools, "_redis_cmd", lambda *a, **kw: _XINFO_GROUPS_OUTPUT)

    # threshold 1000 — only nexus-bridge (2279) qualifies
    alerts = health_tools.get_consumer_groups_lag(lag_threshold=1000)
    assert len(alerts) == 1
    assert alerts[0]["group"] == "nexus-bridge"
    assert alerts[0]["lag"] == 2279
    assert alerts[0]["stream"] == "garuda:raw"

    # threshold 100 — both qualify
    alerts = health_tools.get_consumer_groups_lag(lag_threshold=100)
    assert len(alerts) == 2
    groups = {a["group"] for a in alerts}
    assert groups == {"nexus-bridge", "normalizer"}


def test_get_consumer_groups_lag_handles_missing_lag(monkeypatch):
    """Groups without a parseable lag field are silently dropped from results."""
    no_lag_output = """name
mystery
consumers
1
pending
0
last-delivered-id
1777154510217-0
entries-read
1376"""
    monkeypatch.setattr(health_tools, "HEALTH_STREAMS", ["garuda:raw"])
    monkeypatch.setattr(health_tools, "_redis_cmd", lambda *a, **kw: no_lag_output)
    alerts = health_tools.get_consumer_groups_lag(lag_threshold=1)
    assert alerts == []
