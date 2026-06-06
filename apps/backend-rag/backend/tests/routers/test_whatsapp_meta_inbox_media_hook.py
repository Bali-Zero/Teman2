"""Tests for the webhook → intake media hook (Anello 1, wiring).

M5-safe: ingest_live_media is patched, pool/request are stubs. Verifies the
official-number gating, the no-media short-circuit, and that the v1
received_by policy resolves to None.
"""

from __future__ import annotations

import pytest

import backend.app.routers.whatsapp_chat as wc
from backend.services.integrations.wa_outbox_worker import META_INBOX_PHONE_NUMBER_ID


class _StubRequest:
    """Minimal stand-in; _get_db_pool is patched so the shape is irrelevant."""


def _media_payload(phone_number_id: str, *, media=True):
    msg = (
        {"from": "62811", "id": "wamid.X", "type": "document",
         "document": {"id": "media-1", "mime_type": "application/pdf"}}
        if media
        else {"from": "62811", "id": "wamid.X", "type": "text", "text": {"body": "hi"}}
    )
    return {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": phone_number_id},
            "messages": [msg],
        }}]}]
    }


@pytest.mark.asyncio
async def test_received_by_policy_is_none_v1():
    # Honest v1: shared official line → no per-person receiver.
    assert await wc._meta_inbox_received_by(object()) is None


@pytest.mark.asyncio
async def test_ingest_called_for_official_line_media(monkeypatch):
    called = {}

    async def fake_ingest(raw_event, *, pool, http_client, access_token, dest_dir, resolve_received_by, api_version="v18.0"):
        called["yes"] = True
        called["token"] = access_token
        # resolver wired through
        called["resolved"] = await resolve_received_by(object())

        class _C:
            media_found = 1
            enqueued_new = 1
            already_present = 0
            download_errors = 0
            enqueue_errors = 0

        return _C()

    monkeypatch.setattr(wc, "_get_db_pool", lambda req: object())
    monkeypatch.setattr(wc.settings, "whatsapp_api_token", "tok-123", raising=False)
    monkeypatch.setattr(
        "backend.services.intake.whatsapp_live_adapter.ingest_live_media", fake_ingest
    )

    await wc._ingest_meta_inbox_media(_media_payload(META_INBOX_PHONE_NUMBER_ID), _StubRequest())
    assert called.get("yes") is True
    assert called["token"] == "tok-123"
    assert called["resolved"] is None


@pytest.mark.asyncio
async def test_ingest_skipped_for_other_number(monkeypatch):
    called = {}

    async def fake_ingest(*a, **k):
        called["yes"] = True

    monkeypatch.setattr(wc, "_get_db_pool", lambda req: object())
    monkeypatch.setattr(
        "backend.services.intake.whatsapp_live_adapter.ingest_live_media", fake_ingest
    )
    # A different phone_number_id → not the official line → no ingest.
    await wc._ingest_meta_inbox_media(_media_payload("9999999999"), _StubRequest())
    assert "yes" not in called


@pytest.mark.asyncio
async def test_ingest_skipped_for_text_only(monkeypatch):
    called = {}

    async def fake_ingest(*a, **k):
        called["yes"] = True

    monkeypatch.setattr(wc, "_get_db_pool", lambda req: object())
    monkeypatch.setattr(
        "backend.services.intake.whatsapp_live_adapter.ingest_live_media", fake_ingest
    )
    await wc._ingest_meta_inbox_media(
        _media_payload(META_INBOX_PHONE_NUMBER_ID, media=False), _StubRequest()
    )
    assert "yes" not in called


@pytest.mark.asyncio
async def test_ingest_skipped_when_no_token(monkeypatch):
    called = {}

    async def fake_ingest(*a, **k):
        called["yes"] = True

    monkeypatch.setattr(wc, "_get_db_pool", lambda req: object())
    monkeypatch.setattr(wc.settings, "whatsapp_api_token", "", raising=False)
    monkeypatch.setattr(
        "backend.services.intake.whatsapp_live_adapter.ingest_live_media", fake_ingest
    )
    await wc._ingest_meta_inbox_media(_media_payload(META_INBOX_PHONE_NUMBER_ID), _StubRequest())
    assert "yes" not in called
