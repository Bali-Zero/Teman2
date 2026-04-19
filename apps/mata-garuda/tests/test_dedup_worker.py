"""Tests for mata_garuda.workers.dedup_worker — URL canonicalisation + dedup flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from mata_garuda.workers import dedup_worker


def test_normalize_url_strips_scheme_www_and_trailing_slash():
    a = dedup_worker.normalize_url("https://www.example.com/foo/")
    b = dedup_worker.normalize_url("http://example.com/foo")
    assert a == b


def test_normalize_url_strips_tracking_params():
    a = dedup_worker.normalize_url(
        "https://example.com/x?utm_source=twitter&utm_medium=ref&id=42"
    )
    b = dedup_worker.normalize_url("https://example.com/x?id=42")
    assert a == b


def test_normalize_url_drops_fragment():
    a = dedup_worker.normalize_url("https://example.com/x#section")
    b = dedup_worker.normalize_url("https://example.com/x")
    assert a == b


def test_normalize_url_sorts_query_params_for_stable_hash():
    a = dedup_worker.normalize_url("https://example.com/?b=2&a=1")
    b = dedup_worker.normalize_url("https://example.com/?a=1&b=2")
    assert a == b


def test_normalize_url_returns_empty_on_empty_input():
    assert dedup_worker.normalize_url("") == ""
    assert dedup_worker.normalize_url("   ") == ""


def test_url_fingerprint_stable_across_trivial_variants():
    fp1 = dedup_worker.url_fingerprint("https://www.example.com/a/")
    fp2 = dedup_worker.url_fingerprint("http://example.com/a")
    assert fp1 and fp1 == fp2


def test_url_fingerprint_differs_for_different_paths():
    fp1 = dedup_worker.url_fingerprint("https://example.com/a")
    fp2 = dedup_worker.url_fingerprint("https://example.com/b")
    assert fp1 != fp2


def test_is_seen_and_mark_seen_roundtrip():
    store: set[str] = set()

    def fake_redis(*args: str) -> str:
        cmd = args[0]
        if cmd == "SISMEMBER":
            return "1" if args[2] in store else "0"
        if cmd == "SADD":
            store.add(args[2])
            return "1"
        if cmd == "EXPIRE":
            return "1"
        return ""

    fp = dedup_worker.url_fingerprint("https://example.com/x")
    assert dedup_worker.is_seen(fp, redis=fake_redis) is False
    dedup_worker.mark_seen(fp, redis=fake_redis)
    assert dedup_worker.is_seen(fp, redis=fake_redis) is True


def test_mark_seen_ignores_empty_fingerprint():
    calls = []

    def fake_redis(*args: str) -> str:
        calls.append(args)
        return ""

    dedup_worker.mark_seen("", redis=fake_redis)
    assert calls == []


def test_title_similarity_bounds():
    assert dedup_worker.title_similarity("", "hello") == 0.0
    assert dedup_worker.title_similarity("hello world", "hello world") == 1.0
    partial = dedup_worker.title_similarity(
        "Indonesia tightens visa rules",
        "Indonesia visa rules change",
    )
    assert 0.2 < partial < 1.0


def test_run_dedup_forwards_new_and_drops_duplicate():
    items = [
        {"id": "1-0", "data": {"url": "https://example.com/a", "title": "A"}},
        {"id": "2-0", "data": {"url": "https://www.example.com/a/", "title": "A again"}},
        {"id": "3-0", "data": {"url": "https://example.com/b", "title": "B"}},
    ]
    store: set[str] = set()

    def fake_redis(*args: str) -> str:
        cmd = args[0]
        if cmd == "SISMEMBER":
            return "1" if args[2] in store else "0"
        if cmd in ("SADD",):
            store.add(args[2])
            return "1"
        return "1"

    published = []
    acked = []

    with patch.object(dedup_worker, "stream_read_new", return_value=items):
        stats = dedup_worker.run_dedup(
            redis=fake_redis,
            publish=lambda s, d: published.append((s, dict(d))) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats == {
        "processed": 3,
        "duplicates": 1,
        "forwarded": 2,
        "skipped_no_url": 0,
    }
    assert len(published) == 2
    assert {p[1]["title"] for p in published} == {"A", "B"}
    # Every item is ack'd, including the duplicate
    assert set(acked) == {"1-0", "2-0", "3-0"}
    # Forwarded payloads carry the dedup provenance fields
    for _, payload in published:
        assert payload["dedup_passed"] == "true"
        assert payload["dedup_url_fingerprint"]


def test_run_dedup_skips_item_with_no_url():
    items = [{"id": "1-0", "data": {"title": "no url"}}]

    def fake_redis(*args: str) -> str:
        return "0"

    published = []
    acked = []

    with patch.object(dedup_worker, "stream_read_new", return_value=items):
        stats = dedup_worker.run_dedup(
            redis=fake_redis,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["skipped_no_url"] == 1
    assert stats["forwarded"] == 0
    assert published == []
    assert acked == ["1-0"]


def test_run_dedup_returns_empty_stats_when_stream_empty():
    with patch.object(dedup_worker, "stream_read_new", return_value=[]):
        stats = dedup_worker.run_dedup()
    assert stats == {
        "processed": 0,
        "duplicates": 0,
        "forwarded": 0,
        "skipped_no_url": 0,
    }
