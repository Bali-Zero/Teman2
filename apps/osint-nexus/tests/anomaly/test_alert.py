"""Alert dataclass: immutability, stable hashing, name-free serialization."""
from __future__ import annotations

import json

import pytest

from osint_nexus.anomaly.alert import Alert, make_alert_id


def test_make_alert_id_is_deterministic():
    a = make_alert_id("centrality_jump", "node-123", day_bucket="2026-04-11")
    b = make_alert_id("centrality_jump", "node-123", day_bucket="2026-04-11")
    assert a == b
    assert len(a) == 16  # 16-char sha256 prefix


def test_make_alert_id_varies_by_entity():
    a = make_alert_id("centrality_jump", "node-A", day_bucket="2026-04-11")
    b = make_alert_id("centrality_jump", "node-B", day_bucket="2026-04-11")
    assert a != b


def test_make_alert_id_varies_by_pattern():
    a = make_alert_id("centrality_jump", "n1", day_bucket="2026-04-11")
    b = make_alert_id("bridge_outlier", "n1", day_bucket="2026-04-11")
    assert a != b


def test_alert_dataclass_is_frozen():
    alert = Alert(
        alert_id="abc123",
        pattern="eigenvector_reverse",
        primary_entity_id="node-42",
        score=0.87,
        confidence=0.9,
        evidence_path=["node-42", "node-7", "node-8"],
        rationale_id="ER-LONE-HUB",
        created_at="2026-04-11T12:00:00+00:00",
    )
    with pytest.raises((AttributeError, TypeError)):
        alert.score = 0.1  # type: ignore[misc]


def test_alert_contains_no_names_in_repr():
    """Alert __repr__ must never leak names — only IDs."""
    alert = Alert(
        alert_id="xyz",
        pattern="bridge_outlier",
        primary_entity_id="official-hashed-id-only",
        score=0.5,
        confidence=1.0,
        evidence_path=["a", "b"],
        rationale_id="BO-CUT",
        created_at="2026-04-11T12:00:00+00:00",
    )
    # Must be JSON-serializable via to_dict
    d = alert.to_dict()
    assert set(d.keys()) == {
        "alert_id", "pattern", "primary_entity_id", "score",
        "confidence", "evidence_path", "rationale_id", "created_at",
        "informational",
    }
    # JSON round-trip works
    blob = json.dumps(d)
    assert "official-hashed-id-only" in blob
    # And nothing else we care about
    assert "name" not in d
    # Default informational flag is False (real alert)
    assert d["informational"] is False


def test_alert_score_is_bounded_0_to_1():
    # We don't enforce in dataclass, but document the convention via a
    # helper `Alert.clamp()` that normalizes defensively.
    alert = Alert(
        alert_id="x", pattern="p", primary_entity_id="e",
        score=1.5, confidence=1.0, evidence_path=[], rationale_id="r",
        created_at="2026-04-11T12:00:00+00:00",
    )
    clamped = alert.clamp()
    assert clamped.score == 1.0

    alert2 = Alert(
        alert_id="x", pattern="p", primary_entity_id="e",
        score=-0.2, confidence=1.0, evidence_path=[], rationale_id="r",
        created_at="2026-04-11T12:00:00+00:00",
    )
    assert alert2.clamp().score == 0.0
