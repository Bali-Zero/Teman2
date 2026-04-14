"""Tests for bridge envelope model."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from mata_garuda.bridge.envelope import Envelope


def test_envelope_minimal_creation():
    """Envelope with only required fields should validate."""
    env = Envelope(
        type="crm.client_created",
        source="bridge",
        priority=3,
        payload={"client_id": 42},
    )
    assert env.type == "crm.client_created"
    assert env.source == "bridge"
    assert env.priority == 3
    assert env.payload == {"client_id": 42}
    # Auto-generated fields
    assert env.id is not None
    assert len(env.id) == 36  # UUID v4 string
    assert env.timestamp.endswith("+08:00")  # WITA timezone


def test_envelope_priority_validation():
    """Priority must be 1-5."""
    with pytest.raises(ValidationError):
        Envelope(type="x.y", source="x", priority=0, payload={})
    with pytest.raises(ValidationError):
        Envelope(type="x.y", source="x", priority=6, payload={})


def test_envelope_type_dot_notation():
    """Type must use dot notation (category.subtype)."""
    # Valid
    Envelope(type="crm.client_created", source="b", priority=3, payload={})
    # Invalid: no dot
    with pytest.raises(ValidationError):
        Envelope(type="invalid", source="b", priority=3, payload={})


def test_envelope_to_redis_dict():
    """to_redis_dict() returns flat dict ready for XADD."""
    env = Envelope(
        type="harvest.lhkpn",
        source="lhkpn_harvester",
        priority=2,
        payload={"nip": "123"},
    )
    d = env.to_redis_dict()
    assert d["type"] == "harvest.lhkpn"
    assert d["source"] == "lhkpn_harvester"
    assert d["priority"] == "2"  # XADD requires strings
    assert isinstance(d["payload"], str)  # JSON-encoded
    parsed = json.loads(d["payload"])
    assert parsed == {"nip": "123"}


def test_envelope_from_redis_dict_roundtrip():
    """from_redis_dict() can reconstruct an envelope from XREADGROUP output."""
    original = Envelope(
        type="gap.missing_nip",
        source="gap_detector",
        priority=2,
        payload={"person_name": "Budi"},
    )
    redis_data = original.to_redis_dict()
    restored = Envelope.from_redis_dict(redis_data)
    assert restored.type == original.type
    assert restored.source == original.source
    assert restored.priority == original.priority
    assert restored.payload == original.payload
    assert restored.id == original.id


def test_envelope_filter_by_prefix():
    """Type prefix matching for consumer routing."""
    env = Envelope(type="crm.client_created", source="b", priority=3, payload={})
    assert env.matches_prefix("crm")           # top-level category matches
    assert not env.matches_prefix("intel")     # unrelated category does not match

    # Positive multi-segment: dot-segment boundary
    env2 = Envelope(type="crm.client.details", source="b", priority=3, payload={})
    assert env2.matches_prefix("crm.client")   # True: dot-segment boundary

    # Negative cross-segment: client != clientele segment
    env3 = Envelope(type="crm.clientele.foo", source="b", priority=3, payload={})
    assert not env3.matches_prefix("crm.client")  # False: client != clientele segment


def test_envelope_from_redis_dict_missing_payload_key():
    """from_redis_dict handles missing payload key (defaults to {})."""
    data = {
        "id": "00000000-0000-0000-0000-000000000001",
        "type": "test.thing",
        "source": "test",
        "timestamp": "2026-04-14T10:00:00+08:00",
        "priority": "3",
        # No payload key!
    }
    env = Envelope.from_redis_dict(data)
    assert env.payload == {}
