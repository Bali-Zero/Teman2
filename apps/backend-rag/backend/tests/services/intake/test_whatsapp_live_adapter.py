"""Tests for Anello 1b orchestrator — whatsapp_live_adapter.ingest_live_media.

TWO layers:

1. M5-safe (this file): the ORCHESTRATION logic — chaining, per-attachment
   error isolation, counters, received_by resolution — with download_media and
   enqueue patched. No DB, no network. Verifies the wiring is correct.

2. Pro-only (NOT here): a real integration test that runs enqueue against
   nuzantara_dev to prove the m218 received_by column round-trips and the
   intake_key dedup holds. That test MUST run on the Pro (pool fixture skips on
   M5 — an M5 skip is NOT a pass; see #1145).

These M5 tests use monkeypatch on the adapter module's imported names, so they
never import asyncpg connectivity.
"""

from __future__ import annotations

import httpx
import pytest

import backend.services.intake.whatsapp_live_adapter as mod
from backend.channels.whatsapp.media_download import DownloadedMedia, MediaDownloadError
from backend.services.intake.enqueue import EnqueueResult


def _doc_envelope(media_id="m1", wamid="wamid.1"):
    return {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "1104946272705747"},
            "contacts": [{"profile": {"name": "Mario"}}],
            "messages": [{
                "from": "62811", "id": wamid, "type": "document",
                "document": {"id": media_id, "mime_type": "application/pdf", "filename": "p.pdf"},
            }],
        }}]}]
    }


@pytest.fixture
def http_client():
    # Never actually used (download_media is patched), but the signature wants one.
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))


async def _resolver_const(email):
    async def _r(media):
        return email
    return _r


@pytest.mark.asyncio
async def test_happy_path_downloads_and_enqueues(monkeypatch, http_client):
    seen = {}

    async def fake_download(client, *, media_id, access_token, dest_dir, api_version="v18.0"):
        return DownloadedMedia(blob_path=f"/tmp/{media_id}.pdf", mime_type="application/pdf",
                               sha256="hash-" + media_id, byte_size=10, media_id=media_id)

    async def fake_enqueue(pool, **kw):
        seen.update(kw)
        return EnqueueResult(instance_id=1, queue_id=2, was_new=True)

    monkeypatch.setattr(mod, "download_media", fake_download)
    monkeypatch.setattr(mod, "enqueue", fake_enqueue)

    async with http_client:
        counters = await mod.ingest_live_media(
            _doc_envelope(), pool=object(), http_client=http_client,
            access_token="t", dest_dir="/tmp",
            resolve_received_by=(await _resolver_const("ari@balizero.com")),
        )

    assert counters.media_found == 1
    assert counters.enqueued_new == 1
    assert counters.already_present == 0
    # received_by + source_ref carried into enqueue
    assert seen["received_by"] == "ari@balizero.com"
    assert seen["source"] == "whatsapp"
    assert seen["source_ref"] == "whatsapp-live:wamid.1"
    assert seen["blob_hash"] == "hash-m1"


@pytest.mark.asyncio
async def test_download_error_isolated_not_fatal(monkeypatch, http_client):
    calls = {"dl": 0, "enq": 0}

    async def fake_download(client, *, media_id, **kw):
        calls["dl"] += 1
        if media_id == "bad":
            raise MediaDownloadError("boom")
        return DownloadedMedia(blob_path=f"/tmp/{media_id}", mime_type=None,
                               sha256="h", byte_size=1, media_id=media_id)

    async def fake_enqueue(pool, **kw):
        calls["enq"] += 1
        return EnqueueResult(instance_id=1, queue_id=2, was_new=True)

    monkeypatch.setattr(mod, "download_media", fake_download)
    monkeypatch.setattr(mod, "enqueue", fake_enqueue)

    env = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "1", "id": "a", "type": "document", "document": {"id": "bad", "mime_type": "application/pdf"}},
        {"from": "1", "id": "b", "type": "image", "image": {"id": "good", "mime_type": "image/jpeg"}},
    ]}}]}]}

    async with http_client:
        counters = await mod.ingest_live_media(
            env, pool=object(), http_client=http_client, access_token="t",
            dest_dir="/tmp", resolve_received_by=(await _resolver_const(None)),
        )

    assert counters.media_found == 2
    assert counters.download_errors == 1
    assert counters.enqueued_new == 1   # the good one still went through
    assert calls["enq"] == 1            # enqueue only called for the good one


@pytest.mark.asyncio
async def test_resolver_failure_does_not_lose_doc(monkeypatch, http_client):
    captured = {}

    async def fake_download(client, *, media_id, **kw):
        return DownloadedMedia(blob_path="/tmp/x", mime_type=None, sha256="h", byte_size=1, media_id=media_id)

    async def fake_enqueue(pool, **kw):
        captured.update(kw)
        return EnqueueResult(instance_id=1, queue_id=2, was_new=True)

    async def boom_resolver(media):
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(mod, "download_media", fake_download)
    monkeypatch.setattr(mod, "enqueue", fake_enqueue)

    async with http_client:
        counters = await mod.ingest_live_media(
            _doc_envelope(), pool=object(), http_client=http_client, access_token="t",
            dest_dir="/tmp", resolve_received_by=boom_resolver,
        )

    # Doc still enqueued, just with received_by=None (resolver failure tolerated).
    assert counters.enqueued_new == 1
    assert captured["received_by"] is None


@pytest.mark.asyncio
async def test_dup_counts_as_already_present(monkeypatch, http_client):
    async def fake_download(client, *, media_id, **kw):
        return DownloadedMedia(blob_path="/tmp/x", mime_type=None, sha256="h", byte_size=1, media_id=media_id)

    async def fake_enqueue(pool, **kw):
        return EnqueueResult(instance_id=1, queue_id=2, was_new=False)  # already present

    monkeypatch.setattr(mod, "download_media", fake_download)
    monkeypatch.setattr(mod, "enqueue", fake_enqueue)

    async with http_client:
        counters = await mod.ingest_live_media(
            _doc_envelope(), pool=object(), http_client=http_client, access_token="t",
            dest_dir="/tmp", resolve_received_by=(await _resolver_const("x@balizero.com")),
        )
    assert counters.already_present == 1
    assert counters.enqueued_new == 0


@pytest.mark.asyncio
async def test_no_media_is_noop(monkeypatch, http_client):
    async def fake_download(*a, **k):  # should never be called
        raise AssertionError("download must not run for text-only webhook")

    monkeypatch.setattr(mod, "download_media", fake_download)
    env = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "1", "id": "t", "type": "text", "text": {"body": "hi"}}
    ]}}]}]}

    async with http_client:
        counters = await mod.ingest_live_media(
            env, pool=object(), http_client=http_client, access_token="t",
            dest_dir="/tmp", resolve_received_by=(await _resolver_const(None)),
        )
    assert counters.media_found == 0
    assert counters.enqueued_new == 0
