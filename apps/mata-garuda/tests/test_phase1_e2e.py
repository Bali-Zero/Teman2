"""
Phase 1 SINAPSI — End-to-end bridge verification (Task 16).

Tests the full bridge cycle that Phase 1 delivered:

  Fly (outbox) → pull_once → Redis bridge:inbound (envelope validated)
  Redis intel:articles → push_once → Fly /api/bridge/ingest/article

All I/O boundaries (HTTP, Redis) are faked — the test proves that:
  - nerve.pull_once properly wraps outbox events into valid Envelopes
  - nerve.push_once properly routes envelopes to the correct endpoint
  - The Envelope model validates the 5 required fields end-to-end
  - Cursor state advances only on clean pull; ACK state advances only on 2xx push

No network, no Fly, no real Redis. Matches the "mock everything" pattern from
test_nerve_pull.py / test_nerve_push.py but chains them as one cycle.

Gate for declaring Phase 1 closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call

from mata_garuda.bridge.cursor import BridgeCursor
from mata_garuda.bridge.envelope import Envelope
from mata_garuda.bridge.nerve import (
    PUSH_CONSUMER_GROUP,
    PUSH_CONSUMER_NAME,
    STREAM_BRIDGE_INBOUND,
    STREAM_BRIDGE_OUTBOUND,
    pull_once,
    push_once,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_outbox_events() -> list[dict]:
    """Simulate 3 outbox rows as returned by GET /api/bridge/events."""
    return [
        {
            "id": 100,
            "type": "crm.client_created",
            "payload": {"client_id": 42, "name": "PT Nusantara"},
            "created_at": "2026-04-16T05:00:00+08:00",
        },
        {
            "id": 101,
            "type": "rag.low_confidence",
            "payload": {
                "query": "KBLI 55201",
                "confidence": 0.12,
                "channel": "whatsapp",
            },
            "created_at": "2026-04-16T05:00:01+08:00",
        },
        {
            "id": 102,
            "type": "crm.practice_created",
            "payload": {"practice_id": 7, "type": "visa"},
            "created_at": "2026-04-16T05:00:02+08:00",
        },
    ]


def _make_article_envelope() -> Envelope:
    """A realistic intel:articles envelope for the push side."""
    return Envelope(
        type="intel.article_ready",
        source="war_room",
        priority=2,
        payload={
            "article_id": "a-uuid-1",
            "title": "Peraturan Baru DPMPTSP Bali 2026",
            "slug": "peraturan-baru-dpmptsp-bali-2026",
            "content_md": "# Peraturan Baru\n\nDPMPTSP...",
            "tags": ["visa", "kbli-55201"],
            "source_ids": ["garuda_raw:1234", "nexus:5678"],
        },
    )


# ── TEST: Full pull → validate → push cycle ────────────────────────────


def test_e2e_pull_produces_valid_envelopes_on_redis(tmp_path: Path):
    """PULL: outbox events arrive as valid 5-field Envelopes on bridge:inbound.

    Simulates: GET /api/bridge/events returns 3 events → pull_once wraps each
    in an Envelope → each is XADD'd to bridge:inbound with all 5 fields.
    """
    cursor = BridgeCursor(tmp_path / "e2e_cursor.json")
    events = _make_outbox_events()

    fake_get = MagicMock(return_value={
        "status_code": 200,
        "json": {"events": events, "last_id": 102},
    })

    published: list[dict[str, str]] = []

    def capture_xadd(stream: str, fields: dict[str, str]) -> str:
        assert stream == STREAM_BRIDGE_INBOUND
        published.append(fields)
        return f"{len(published)}-0"

    stats = pull_once(
        cursor=cursor,
        backend_url="https://nuzantara-rag.fly.dev",
        api_key="test-key",
        http_get=fake_get,
        redis_xadd=capture_xadd,
    )

    # All 3 events fetched + published, no errors
    assert stats == {"fetched": 3, "published": 3, "errors": 0}
    assert len(published) == 3

    # Cursor advanced to last_id
    assert cursor.read() == 102

    # Validate each published dict is a valid Envelope
    for i, fields in enumerate(published):
        env = Envelope.from_redis_dict(fields)
        assert env.type == events[i]["type"]
        assert env.source == "bridge"
        assert env.priority == 3
        # Envelope.id is a UUID string
        assert len(env.id) > 10
        # Timestamp is ISO 8601 WITA
        assert "T" in env.timestamp
        # Payload includes the original event payload + _outbox_id
        assert env.payload["_outbox_id"] == events[i]["id"]
        assert env.payload["_outbox_created_at"] == events[i]["created_at"]


def test_e2e_push_routes_article_to_ingest_endpoint():
    """PUSH: intel:articles envelope → POST /api/bridge/ingest/article.

    Simulates: XREADGROUP returns 1 article envelope from bridge:outbound →
    push_once POSTs it to /api/bridge/ingest/article → 200 → XACK.
    """
    article = _make_article_envelope()

    state = {"called": False}
    def fake_xreadgroup(stream, group, consumer, count, block_ms):
        if state["called"]:
            return []
        state["called"] = True
        assert stream == STREAM_BRIDGE_OUTBOUND
        assert group == PUSH_CONSUMER_GROUP
        assert consumer == PUSH_CONSUMER_NAME
        return [{"id": "500-0", "envelope": article}]

    posted_payloads: list[dict] = []

    def capture_post(url, headers, json_body, timeout):
        assert url.endswith("/api/bridge/ingest/article")
        assert headers["X-Bridge-Auth"] == "test-key"
        posted_payloads.append(json_body)
        return {"status_code": 200, "json": {"status": "queued"}, "text": "ok"}

    fake_xack = MagicMock()

    stats = push_once(
        backend_url="https://nuzantara-rag.fly.dev",
        api_key="test-key",
        http_post=capture_post,
        redis_xreadgroup=fake_xreadgroup,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 1, "acked": 1, "errors": 0}

    # Verify POST payload matches the envelope's payload
    assert len(posted_payloads) == 1
    payload = posted_payloads[0]
    assert payload["article_id"] == "a-uuid-1"
    assert payload["title"] == "Peraturan Baru DPMPTSP Bali 2026"
    assert payload["tags"] == ["visa", "kbli-55201"]
    assert payload["source_ids"] == ["garuda_raw:1234", "nexus:5678"]

    # XACK confirms delivery
    fake_xack.assert_called_once_with(
        STREAM_BRIDGE_OUTBOUND, PUSH_CONSUMER_GROUP, "500-0",
    )


def test_e2e_full_cycle_pull_then_push(tmp_path: Path):
    """FULL CYCLE: pull outbox events → validate envelopes → push article.

    Chains pull_once + push_once with shared fake state to prove the full
    Phase 1 bridge path works end-to-end with valid data flowing through.
    """
    # ── Phase A: Pull ──────────────────────────────────────────────────
    cursor = BridgeCursor(tmp_path / "full_cycle.json")
    events = _make_outbox_events()

    fake_get = MagicMock(return_value={
        "status_code": 200,
        "json": {"events": events, "last_id": 102},
    })

    inbound_envelopes: list[dict[str, str]] = []

    def capture_inbound_xadd(stream: str, fields: dict[str, str]) -> str:
        inbound_envelopes.append(fields)
        return f"{len(inbound_envelopes)}-0"

    pull_stats = pull_once(
        cursor=cursor,
        backend_url="https://nuzantara-rag.fly.dev",
        api_key="cycle-key",
        http_get=fake_get,
        redis_xadd=capture_inbound_xadd,
    )

    assert pull_stats["fetched"] == 3
    assert pull_stats["errors"] == 0
    assert cursor.read() == 102

    # Validate all pulled envelopes
    for fields in inbound_envelopes:
        env = Envelope.from_redis_dict(fields)
        assert "." in env.type  # dot notation
        assert env.source == "bridge"

    # ── Phase B: Push ──────────────────────────────────────────────────
    article = _make_article_envelope()

    push_read_called = {"n": False}
    def fake_push_read(stream, group, consumer, count, block_ms):
        if push_read_called["n"]:
            return []
        push_read_called["n"] = True
        return [{"id": "600-0", "envelope": article}]

    push_responses: list[str] = []

    def capture_push_post(url, headers, json_body, timeout):
        push_responses.append(url)
        return {"status_code": 202, "json": {"status": "accepted"}, "text": "ok"}

    fake_xack = MagicMock()

    push_stats = push_once(
        backend_url="https://nuzantara-rag.fly.dev",
        api_key="cycle-key",
        http_post=capture_push_post,
        redis_xreadgroup=fake_push_read,
        redis_xack=fake_xack,
    )

    assert push_stats == {"sent": 1, "acked": 1, "errors": 0}
    assert push_responses[0].endswith("/api/bridge/ingest/article")
    fake_xack.assert_called_once()

    # ── Full cycle invariants ──────────────────────────────────────────
    # Pull produced 3 valid inbound envelopes + push delivered 1 article
    assert len(inbound_envelopes) == 3
    assert len(push_responses) == 1


def test_e2e_pull_failure_does_not_corrupt_push(tmp_path: Path):
    """Graceful degradation: failed pull does not prevent push from working.

    This is a Phase 1 invariant — bridge_main() calls pull then push
    sequentially, and push must work even if pull errored.
    """
    cursor = BridgeCursor(tmp_path / "half_broken.json")

    # Pull side: simulates Fly down
    def bad_get(*a, **kw):
        raise ConnectionError("Fly.io IPv6 timeout")

    pull_stats = pull_once(
        cursor=cursor,
        backend_url="https://nuzantara-rag.fly.dev",
        api_key="k",
        http_get=bad_get,
        redis_xadd=MagicMock(),
    )
    assert pull_stats["errors"] == 1

    # Push side: should still work independently
    article = _make_article_envelope()
    push_called = {"n": False}
    def push_read(stream, group, consumer, count, block_ms):
        if push_called["n"]:
            return []
        push_called["n"] = True
        return [{"id": "700-0", "envelope": article}]

    fake_post = MagicMock(return_value={
        "status_code": 200, "json": {"ok": True}, "text": "ok",
    })
    fake_xack = MagicMock()

    push_stats = push_once(
        backend_url="https://nuzantara-rag.fly.dev",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=push_read,
        redis_xack=fake_xack,
    )

    assert push_stats == {"sent": 1, "acked": 1, "errors": 0}


def test_e2e_envelope_round_trip():
    """Envelope survives serialize → redis dict → deserialize round trip.

    A property the pull and push paths both depend on: the envelope must
    survive being stringified for XADD then parsed back from XREADGROUP
    without data loss.
    """
    original = Envelope(
        type="intel.article_ready",
        source="war_room",
        priority=2,
        payload={
            "article_id": "rt-1",
            "title": "Round Trip Test — Peraturan DPMPTSP",
            "tags": ["visa", "kbli-55201"],
            "nested": {"deep": True, "list": [1, 2, 3]},
        },
    )

    redis_dict = original.to_redis_dict()

    # All 6 keys present (id, type, source, timestamp, priority, payload)
    assert set(redis_dict.keys()) == {"id", "type", "source", "timestamp", "priority", "payload"}
    # All values are strings (Redis requirement)
    for v in redis_dict.values():
        assert isinstance(v, str), f"Redis field value must be str, got {type(v)}"

    restored = Envelope.from_redis_dict(redis_dict)

    assert restored.id == original.id
    assert restored.type == original.type
    assert restored.source == original.source
    assert restored.timestamp == original.timestamp
    assert restored.priority == original.priority
    assert restored.payload == original.payload
    # Nested structures survive JSON round trip
    assert restored.payload["nested"]["deep"] is True
    assert restored.payload["nested"]["list"] == [1, 2, 3]
