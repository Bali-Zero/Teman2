"""Tests for bridge nerve — push side (Pro→Fly)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from mata_garuda.bridge.envelope import Envelope
from mata_garuda.bridge.nerve import push_once


def _xreadgroup_stub_factory(envelopes_with_ids):
    """Return a stub that yields the given (msg_id, envelope) pairs once,
    then [] forever after."""
    state = {"called": False}

    def stub(stream, group, consumer, count, block_ms):
        if state["called"]:
            return []
        state["called"] = True
        return [
            {"id": msg_id, "envelope": env}
            for msg_id, env in envelopes_with_ids
        ]

    return stub


def test_push_once_routes_article_to_correct_endpoint():
    """intel.article_ready → POST /api/bridge/ingest/article."""
    env = Envelope(
        type="intel.article_ready",
        source="intel_scraper",
        priority=2,
        payload={
            "article_id": "abc-123",
            "title": "Test",
            "body_mdx": "# x",
            "topic": "test",
        },
    )

    fake_resp = {"status_code": 200, "json": {"article_id": "abc-123", "status": "queued"}}
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("17-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 1, "acked": 1, "errors": 0}
    fake_post.assert_called_once()
    args, kwargs = fake_post.call_args
    # First positional arg is URL
    assert args[0].endswith("/api/bridge/ingest/article")
    fake_xack.assert_called_once_with("bridge:outbound", "bridge-push", "17-0")


def test_push_once_routes_enrichment_to_correct_endpoint():
    """enrichment.kb_entry → POST /api/bridge/ingest/enrichment."""
    env = Envelope(
        type="enrichment.kb_entry",
        source="enrichment_agent",
        priority=3,
        payload={"kb_entry_id": "kb-1", "content": "x", "source": "test"},
    )

    fake_resp = {"status_code": 200, "json": {"kb_entry_id": "kb-1", "status": "queued"}}
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("18-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 1, "acked": 1, "errors": 0}
    args, _ = fake_post.call_args
    assert args[0].endswith("/api/bridge/ingest/enrichment")


def test_push_once_does_not_ack_on_http_500():
    """If POST fails (non-2xx), do NOT XACK — message redelivered next cycle."""
    env = Envelope(
        type="intel.article_ready",
        source="intel_scraper",
        priority=2,
        payload={"article_id": "x", "title": "t", "body_mdx": "b"},
    )

    fake_resp = {"status_code": 500, "json": None, "text": "server error"}
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("19-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats["sent"] == 1
    assert stats["acked"] == 0
    assert stats["errors"] == 1
    fake_xack.assert_not_called()


def test_push_once_does_not_ack_on_http_exception():
    """If POST raises (network down), do NOT XACK."""
    env = Envelope(
        type="intel.article_ready",
        source="intel_scraper",
        priority=2,
        payload={"article_id": "x", "title": "t", "body_mdx": "b"},
    )

    def bad_post(*a, **kw):
        raise ConnectionError("backend unreachable")

    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("20-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=bad_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats["acked"] == 0
    assert stats["errors"] == 1
    fake_xack.assert_not_called()


def test_push_once_skips_unknown_type_with_ack():
    """Unknown envelope type: log + ACK (no infinite loop) + count error."""
    env = Envelope(
        type="intel.unknown_subtype",
        source="x",
        priority=3,
        payload={},
    )

    fake_post = MagicMock()
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("21-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats["sent"] == 0
    assert stats["acked"] == 1
    assert stats["errors"] == 1
    fake_post.assert_not_called()
    fake_xack.assert_called_once_with("bridge:outbound", "bridge-push", "21-0")


def test_push_once_empty_queue_no_op():
    """No messages → all-zero stats, no calls."""
    fake_post = MagicMock()
    fake_xack = MagicMock()
    fake_read = MagicMock(return_value=[])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 0, "acked": 0, "errors": 0}
    fake_post.assert_not_called()
    fake_xack.assert_not_called()


def test_push_once_accepts_202():
    """Status 202 (accepted/queued) is treated as success."""
    env = Envelope(
        type="intel.article_ready",
        source="x",
        priority=3,
        payload={"article_id": "y", "title": "t", "body_mdx": "b"},
    )
    fake_resp = {"status_code": 202, "json": {"status": "queued"}}
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("22-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 1, "acked": 1, "errors": 0}
    fake_xack.assert_called_once()


# ── W3 cicatrix 2026-05-22 push-side silent-idle heartbeat ─────────────


def test_push_once_idle_increments_heartbeat_counter(tmp_path: Path, monkeypatch):
    """W3 cicatrix 2026-05-22 — push_once must emit a heartbeat every N
    consecutive empty-stream ticks, mirroring pull-side W1. Without it the
    push cron is indistinguishable from a dead cron during quiet periods."""
    # Redirect BRIDGE_CURSOR_PATH to tmp so the sidecar lands in test scope.
    monkeypatch.setenv("BRIDGE_PUSH_HEARTBEAT_IDLE_TICKS", "3")
    monkeypatch.setattr(
        "mata_garuda.bridge.nerve.BRIDGE_CURSOR_PATH",
        tmp_path / "bridge_cursor.json",
    )
    import importlib
    import mata_garuda.bridge.nerve as nerve_mod
    importlib.reload(nerve_mod)
    # Re-apply monkeypatch after reload (module reload reset the patched attr).
    monkeypatch.setattr(
        "mata_garuda.bridge.nerve.BRIDGE_CURSOR_PATH",
        tmp_path / "bridge_cursor.json",
    )

    sidecar = tmp_path / "bridge-push-idle-ticks.json"
    empty_read = MagicMock(return_value=[])

    # Ticks 1+2: counter accumulates.
    for expected in (1, 2):
        nerve_mod.push_once(
            backend_url="https://x", api_key="k",
            http_post=MagicMock(),
            redis_xreadgroup=empty_read,
            redis_xack=MagicMock(),
        )
        assert sidecar.exists()
        assert json.loads(sidecar.read_text())["count"] == expected

    # Tick 3: threshold hit → heartbeat fires, counter resets.
    nerve_mod.push_once(
        backend_url="https://x", api_key="k",
        http_post=MagicMock(),
        redis_xreadgroup=empty_read,
        redis_xack=MagicMock(),
    )
    assert json.loads(sidecar.read_text())["count"] == 0


def test_push_once_non_idle_resets_heartbeat_counter(tmp_path: Path, monkeypatch):
    """A tick that sends >0 messages OR errors out must clear the sidecar
    — heartbeat is only for genuine quiet periods."""
    monkeypatch.setenv("BRIDGE_PUSH_HEARTBEAT_IDLE_TICKS", "5")
    monkeypatch.setattr(
        "mata_garuda.bridge.nerve.BRIDGE_CURSOR_PATH",
        tmp_path / "bridge_cursor.json",
    )
    import importlib
    import mata_garuda.bridge.nerve as nerve_mod
    importlib.reload(nerve_mod)
    monkeypatch.setattr(
        "mata_garuda.bridge.nerve.BRIDGE_CURSOR_PATH",
        tmp_path / "bridge_cursor.json",
    )

    sidecar = tmp_path / "bridge-push-idle-ticks.json"
    empty_read = MagicMock(return_value=[])

    # Prime with 2 idle ticks.
    for _ in range(2):
        nerve_mod.push_once(
            backend_url="https://x", api_key="k",
            http_post=MagicMock(),
            redis_xreadgroup=empty_read,
            redis_xack=MagicMock(),
        )
    assert json.loads(sidecar.read_text())["count"] == 2

    # Non-idle tick: 1 message sent successfully.
    env = Envelope(type="crm.x", source="pro", priority=3, payload={"a": 1})
    items_read = MagicMock(return_value=[{"id": "1-0", "envelope": env}])
    # Route crm.x to a valid endpoint — patch PUSH_ROUTING.
    monkeypatch.setattr(
        "mata_garuda.bridge.nerve.PUSH_ROUTING",
        {"crm.x": "/api/test/x"},
    )
    good_post = MagicMock(return_value={"status_code": 200, "json": {}, "text": ""})

    nerve_mod.push_once(
        backend_url="https://x", api_key="k",
        http_post=good_post,
        redis_xreadgroup=items_read,
        redis_xack=MagicMock(),
    )
    assert not sidecar.exists()
