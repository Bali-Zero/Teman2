"""Web session_id namespacing: session_id is CLIENT-controlled on the web
channel — without a server-side namespace a caller could persist rows under
"wa_session_<phone>" and poison another channel's session-context history
(Codex review 2026-07-13)."""

import pytest

from backend.channels.web.adapter import WebChannelAdapter


@pytest.fixture
def adapter() -> WebChannelAdapter:
    return WebChannelAdapter(config={})


@pytest.mark.asyncio
async def test_guilt_forged_cross_channel_session_id_is_namespaced(adapter):
    msg = await adapter.receive_message(
        {"user_id": "u1", "session_id": "wa_session_628123", "query": "hi"}
    )
    assert msg.session_id == "web_wa_session_628123"


@pytest.mark.asyncio
async def test_innocence_documented_web_prefix_unchanged(adapter):
    msg = await adapter.receive_message(
        {"user_id": "u1", "session_id": "web_session_123", "query": "hi"}
    )
    assert msg.session_id == "web_session_123"


@pytest.mark.asyncio
async def test_missing_session_id_gets_web_fallback(adapter):
    msg = await adapter.receive_message({"user_id": "u1", "query": "hi"})
    assert msg.session_id == "web_session_unknown"
