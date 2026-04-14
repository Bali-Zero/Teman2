"""Tests for bridge nerve — push side (Pro→Fly)."""
from __future__ import annotations

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
