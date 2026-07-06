"""Guilt + innocence tests for the codex access receptor (scar #3 discipline).

Guilt: a POST 303 from a European edge MUST alert.
Innocence: self-noise (sfo1/iad1 probes) and already-seen ids MUST stay silent.
"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "codex_access_watch", Path(__file__).resolve().parents[1] / "codex_access_watch.py"
)
watch = importlib.util.module_from_spec(spec)
sys.modules["codex_access_watch"] = watch
spec.loader.exec_module(watch)


def _row(rid: str, method: str, status: int, regions: list[str]) -> dict:
    return {
        "requestId": rid,
        "timestamp": "2026-07-06T12:18:59.000Z",
        "requestPath": "/codex",
        "requestMethod": method,
        "statusCode": status,
        "proxyEvents": [{"region": r} for r in regions],
    }


def test_guilt_eu_entry_alerts():
    events = watch.classify_new_foreign([_row("a1", "POST", 303, ["fra1"])], seen={})
    assert len(events) == 1
    assert events[0]["regions"] == ["fra1"]
    msg = watch.build_message(events)
    assert "ENTRATO" in msg and "fra1" in msg and "Europa" in msg


def test_guilt_eu_wrong_pin_alerts_as_door():
    events = watch.classify_new_foreign([_row("a2", "POST", 401, ["cdg1"])], seen={})
    assert len(events) == 1
    msg = watch.build_message(events)
    assert "ENTRATO" not in msg and "sbagliato" in msg


def test_innocence_self_edges_stay_silent():
    rows = [
        _row("b1", "POST", 303, ["sfo1"]),
        _row("b2", "GET", 200, ["iad1", "sfo1"]),
    ]
    assert watch.classify_new_foreign(rows, seen={}) == []


def test_innocence_seen_ids_not_realerted():
    row = _row("c1", "POST", 303, ["fra1"])
    assert watch.classify_new_foreign([row], seen={"c1": 1.0}) == []


def test_mixed_edge_still_foreign():
    # a request seen by both a US and an EU edge is not self-noise
    events = watch.classify_new_foreign([_row("d1", "GET", 200, ["iad1", "fra1"])], seen={})
    assert len(events) == 1 and events[0]["regions"] == ["fra1"]
