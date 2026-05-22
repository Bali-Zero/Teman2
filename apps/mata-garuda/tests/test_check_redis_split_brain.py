"""W16: Pro<->Mini Redis split-brain detector tests."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_redis_split_brain as srb  # noqa: E402


def test_constants_match_design():
    assert srb.PRO_HOST == "127.0.0.1"
    assert srb.MINI_HOST == "100.93.236.6"
    assert srb.DRIFT_THRESHOLD_MS == 3600 * 1000
    assert "garuda:raw" in srb.STREAMS
    assert "garuda:enriched" in srb.STREAMS
    assert "garuda:alerts" in srb.STREAMS


def test_host_stream_state_parses_xinfo_stream():
    fake_out = (
        "length\n"
        "4337\n"
        "radix-tree-keys\n"
        "47\n"
        "radix-tree-nodes\n"
        "150\n"
        "last-generated-id\n"
        "1779421119230-0\n"
        "max-deleted-entry-id\n"
        "0-0\n"
        "entries-added\n"
        "4337\n"
        "first-entry\n"
        "1775772000000-0\n"
        "last-entry\n"
        "1779421119230-0\n"
    )
    with patch.object(srb, "rcli", return_value=fake_out):
        state = srb.host_stream_state("127.0.0.1", "garuda:enriched")
    assert state == {"length": 4337, "last_id_ms": 1779421119230}


def test_host_stream_state_returns_none_on_missing_stream():
    with patch.object(srb, "rcli", return_value="(error) ERR no such key 'garuda:missing'"):
        state = srb.host_stream_state("127.0.0.1", "garuda:missing")
    assert state is None


def test_host_stream_state_returns_none_on_unreachable():
    with patch.object(srb, "rcli", return_value=""):
        state = srb.host_stream_state("100.93.236.6", "garuda:raw")
    assert state is None


def test_detect_split_brain_emits_alert_when_drift_exceeds_threshold():
    """Pro fresh @ 1779421119230, Mini stale @ 1779386477934 → 9.6h drift."""
    states = {
        ("127.0.0.1", "garuda:raw"):       {"length": 100, "last_id_ms": 1779421119230},
        ("127.0.0.1", "garuda:enriched"):  {"length": 4337, "last_id_ms": 1779421119230},
        ("127.0.0.1", "garuda:alerts"):    {"length": 290, "last_id_ms": 1779421119230},
        ("100.93.236.6", "garuda:raw"):    {"length": 100, "last_id_ms": 1779421119230},
        ("100.93.236.6", "garuda:enriched"): {"length": 1145, "last_id_ms": 1779386477934},
        ("100.93.236.6", "garuda:alerts"): {"length": 290, "last_id_ms": 1779421119230},
    }

    def fake_state(host, stream):
        return states[(host, stream)]

    with patch.object(srb, "host_stream_state", side_effect=fake_state):
        rep = srb.detect_split_brain()

    assert len(rep["alerts"]) == 1
    alert = rep["alerts"][0]
    assert alert["stream"] == "garuda:enriched"
    assert alert["stale_host"] == "mini"
    assert alert["fresh_host"] == "pro"
    assert alert["stale_length"] == 1145
    assert alert["fresh_length"] == 4337


def test_detect_split_brain_silent_when_in_sync():
    """Both hosts within 5min of each other → no alert."""
    states = {
        ("127.0.0.1", s): {"length": 100, "last_id_ms": 1779421119230}
        for s in srb.STREAMS
    }
    states.update({
        ("100.93.236.6", s): {"length": 100, "last_id_ms": 1779421119230 - 60000}
        for s in srb.STREAMS  # 60s drift, well under 1h threshold
    })

    def fake_state(host, stream):
        return states[(host, stream)]

    with patch.object(srb, "host_stream_state", side_effect=fake_state):
        rep = srb.detect_split_brain()

    assert rep["alerts"] == []


def test_detect_split_brain_silent_when_one_host_unreachable():
    """If Mini is offline, no alert (only one host alive → not split-brain)."""
    states = {("127.0.0.1", s): {"length": 100, "last_id_ms": 1779421119230} for s in srb.STREAMS}
    states.update({("100.93.236.6", s): None for s in srb.STREAMS})

    def fake_state(host, stream):
        return states[(host, stream)]

    with patch.object(srb, "host_stream_state", side_effect=fake_state):
        rep = srb.detect_split_brain()

    assert rep["alerts"] == []
