"""Tests for the webhook → outbox media handoff (Anello 1 PULL, Fly side).

M5-safe: the DB pool/connection/transaction are stubs that capture
``outbox.publish`` calls. Verifies official-number gating, the no-media and
text-only short-circuits, and the metadata-only payload shape — and that the
Fly side downloads NOTHING (Law 2: PII never leaves the Pro).
"""

from __future__ import annotations

import pytest

import backend.app.routers.whatsapp_chat as wc
from backend.services.integrations.wa_outbox_worker import META_INBOX_PHONE_NUMBER_ID


class _StubRequest:
    """Minimal stand-in; _get_db_pool is patched so the shape is irrelevant."""


class _StubTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _StubConn:
    def transaction(self):
        return _StubTx()


class _StubAcquire:
    async def __aenter__(self):
        return _StubConn()

    async def __aexit__(self, *exc):
        return False


class _StubPool:
    """pool.acquire() async-context-manager yielding a stub connection."""

    def acquire(self):
        return _StubAcquire()


def _media_payload(phone_number_id: str, *, media=True):
    msg = (
        {
            "from": "62811",
            "id": "wamid.X",
            "type": "document",
            "document": {
                "id": "media-1",
                "mime_type": "application/pdf",
                "filename": "passport.pdf",
                "sha256": "deadbeef",
            },
        }
        if media
        else {"from": "62811", "id": "wamid.X", "type": "text", "text": {"body": "hi"}}
    )
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [
                                {"profile": {"name": "Marina"}, "wa_id": "62811"}
                            ],
                            "messages": [msg],
                        }
                    }
                ]
            }
        ]
    }


def _capture_publish(monkeypatch):
    """Patch outbox.publish; return the list it appends (channel, payload) to."""
    calls: list[tuple[str, dict]] = []

    async def fake_publish(conn, channel, payload):
        calls.append((channel, payload))
        return len(calls)

    import backend.services.events.outbox as outbox

    monkeypatch.setattr(outbox, "publish", fake_publish)
    return calls


@pytest.mark.asyncio
async def test_publishes_one_per_official_media(monkeypatch):
    calls = _capture_publish(monkeypatch)
    monkeypatch.setattr(wc, "_get_db_pool", lambda req: _StubPool())

    await wc._ingest_meta_inbox_media(
        _media_payload(META_INBOX_PHONE_NUMBER_ID), _StubRequest()
    )

    assert len(calls) == 1
    channel, payload = calls[0]
    assert channel == "whatsapp_media_pending"
    # Metadata only — NO bytes, NO blob_path, NO local file.
    assert payload["media_id"] == "media-1"
    assert payload["mime_type"] == "application/pdf"
    assert payload["message_type"] == "document"
    assert payload["filename"] == "passport.pdf"
    assert payload["declared_sha256"] == "deadbeef"
    assert payload["wa_message_id"] == "wamid.X"
    assert payload["from_phone"] == "62811"
    assert payload["phone_number_id"] == META_INBOX_PHONE_NUMBER_ID
    assert payload["sender_name"] == "Marina"
    # The hand-off carries no file payload at all.
    assert "blob_path" not in payload
    assert "bytes" not in payload


@pytest.mark.asyncio
async def test_no_token_needed_on_fly(monkeypatch):
    """Fly publishes regardless of token — the Pro worker holds the token."""
    calls = _capture_publish(monkeypatch)
    monkeypatch.setattr(wc, "_get_db_pool", lambda req: _StubPool())
    monkeypatch.setattr(wc.settings, "whatsapp_api_token", "", raising=False)

    await wc._ingest_meta_inbox_media(
        _media_payload(META_INBOX_PHONE_NUMBER_ID), _StubRequest()
    )
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_skipped_for_other_number(monkeypatch):
    calls = _capture_publish(monkeypatch)
    monkeypatch.setattr(wc, "_get_db_pool", lambda req: _StubPool())

    await wc._ingest_meta_inbox_media(_media_payload("9999999999"), _StubRequest())
    assert calls == []


@pytest.mark.asyncio
async def test_skipped_for_text_only(monkeypatch):
    calls = _capture_publish(monkeypatch)
    monkeypatch.setattr(wc, "_get_db_pool", lambda req: _StubPool())

    await wc._ingest_meta_inbox_media(
        _media_payload(META_INBOX_PHONE_NUMBER_ID, media=False), _StubRequest()
    )
    assert calls == []


@pytest.mark.asyncio
async def test_skipped_when_no_pool(monkeypatch):
    calls = _capture_publish(monkeypatch)
    monkeypatch.setattr(wc, "_get_db_pool", lambda req: None)

    await wc._ingest_meta_inbox_media(
        _media_payload(META_INBOX_PHONE_NUMBER_ID), _StubRequest()
    )
    assert calls == []
