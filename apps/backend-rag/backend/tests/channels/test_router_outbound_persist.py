"""Outbound audit-trail tests for ChannelRouter (COS-LAW-013, Case OS P0-0).

Every bot reply routed through ChannelRouter must land in
conversation_messages with direction="outbound": the final "answer" event
carries the complete text, token deltas are the fallback, and the "error"
apology is itself an outbound message worth auditing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.channels.base import ChannelMessage, ChannelResponse
from backend.channels.router import ChannelRouter


def _make_engine(events: list[ChannelResponse]) -> MagicMock:
    """Engine whose process_message yields the given responses."""

    async def _stream(message, channel_config):
        for ev in events:
            yield ev

    engine = MagicMock()
    engine.process_message = _stream
    return engine


def _make_adapter(channel: str, text: str) -> AsyncMock:
    adapter = AsyncMock()
    adapter.channel_name = channel
    adapter.timeout = 30
    adapter.update_interval = 1
    adapter.supports_markdown = True
    adapter.supports_media = False
    adapter.max_message_length = 4096
    adapter.receive_message = AsyncMock(
        return_value=ChannelMessage(
            user_id=f"{channel}_123",
            session_id=f"{channel}_session",
            text=text,
            channel=channel,
        )
    )

    async def _consume(channel_id, stream):
        async for _ in stream:
            pass

    adapter.stream_response = AsyncMock(side_effect=_consume)
    return adapter


def _build_router(events: list[ChannelResponse], channel: str = "instagram") -> ChannelRouter:
    router = ChannelRouter(_make_engine(events))
    router.register_adapter(channel, _make_adapter(channel, "Quanto costa il KITAS?"))
    router._persist_message = AsyncMock()
    return router


def _persist_calls(router: ChannelRouter) -> list[dict]:
    return [call.kwargs for call in router._persist_message.await_args_list]


@pytest.mark.asyncio
async def test_outbound_persisted_from_answer_event():
    """The final 'answer' event text is persisted as direction=outbound."""
    events = [
        ChannelResponse(text="Il ", metadata={"event_type": "token"}),
        ChannelResponse(text="KITAS ", metadata={"event_type": "token"}),
        ChannelResponse(
            text="Il KITAS costa X — chiedi al team per la cifra esatta.",
            metadata={"event_type": "answer"},
        ),
    ]
    router = _build_router(events)

    await router.route_message("instagram", {"some": "payload"})

    calls = _persist_calls(router)
    assert len(calls) == 2
    assert calls[0]["direction"] == "inbound"
    assert calls[1]["direction"] == "outbound"
    assert calls[1]["sender_id"] == "zantara"
    assert calls[1]["content"] == "Il KITAS costa X — chiedi al team per la cifra esatta."
    assert calls[1]["channel"] == "instagram"


@pytest.mark.asyncio
async def test_outbound_falls_back_to_token_concat():
    """Without a final 'answer' event, token deltas are concatenated."""
    events = [
        ChannelResponse(text="Hello ", metadata={"event_type": "token"}),
        ChannelResponse(text="world", metadata={"event_type": "token"}),
    ]
    router = _build_router(events)

    await router.route_message("instagram", {})

    calls = _persist_calls(router)
    assert calls[1]["direction"] == "outbound"
    assert calls[1]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_error_apology_is_persisted():
    """The engine's error apology is an outbound message — it must be audited."""
    events = [
        ChannelResponse(
            text="Mi dispiace, si è verificato un errore. Riprova tra poco.",
            metadata={"event_type": "error", "error": "boom"},
        ),
    ]
    router = _build_router(events)

    await router.route_message("instagram", {})

    calls = _persist_calls(router)
    assert calls[1]["direction"] == "outbound"
    assert "Mi dispiace" in calls[1]["content"]


@pytest.mark.asyncio
async def test_empty_stream_persists_no_outbound():
    """No text produced → no phantom outbound row."""
    router = _build_router([])

    await router.route_message("instagram", {})

    calls = _persist_calls(router)
    assert len(calls) == 1
    assert calls[0]["direction"] == "inbound"


@pytest.mark.asyncio
async def test_both_persists_receive_session_id():
    """Audit unification: route_message must hand the ChannelMessage's
    session_id to BOTH persists — it is the key the session-context reader
    (conversation/engine.py) filters on."""
    events = [ChannelResponse(text="ok", metadata={"event_type": "answer"})]
    router = _build_router(events)

    await router.route_message("instagram", {})

    calls = _persist_calls(router)
    assert len(calls) == 2
    assert calls[0]["session_id"] == "instagram_session"
    assert calls[1]["session_id"] == "instagram_session"


@pytest.mark.asyncio
async def test_persist_metadata_json_gains_session_id():
    """GUILT (unified shape): the REAL _persist_message must fold session_id
    into the metadata JSON next to the adapter-native keys — before this,
    router-written rows had {message_id, wamid, ...} but NO session_id, so
    the engine's `metadata->>'session_id'` reader never saw them."""
    import json

    router = ChannelRouter(_make_engine([]))
    router._db_pool = AsyncMock()

    await router._persist_message(
        channel="whatsapp",
        direction="inbound",
        sender_id="whatsapp_628123",
        content="halo",
        metadata={"phone": "628123", "message_id": "wamid.X", "message_type": "text"},
        session_id="wa_session_628123",
    )

    args = router._db_pool.execute.await_args[0]
    meta = json.loads(args[-1])
    assert meta["session_id"] == "wa_session_628123"
    # adapter-native keys pass through untouched
    assert meta["phone"] == "628123"
    assert meta["message_id"] == "wamid.X"
    assert meta["message_type"] == "text"


@pytest.mark.asyncio
async def test_persist_does_not_clobber_explicit_session_id():
    """INNOCENCE: a session_id already present in metadata wins — the
    parameter is a fallback, never an overwrite."""
    import json

    router = ChannelRouter(_make_engine([]))
    router._db_pool = AsyncMock()

    await router._persist_message(
        channel="web",
        direction="inbound",
        sender_id="web_1",
        content="hi",
        metadata={"session_id": "explicit-session"},
        session_id="derived-session",
    )

    args = router._db_pool.execute.await_args[0]
    meta = json.loads(args[-1])
    assert meta["session_id"] == "explicit-session"


@pytest.mark.asyncio
async def test_persist_without_session_id_unchanged():
    """INNOCENCE: callers that pass no session_id (legacy/None) keep the old
    shape — no phantom empty key is written."""
    import json

    router = ChannelRouter(_make_engine([]))
    router._db_pool = AsyncMock()

    await router._persist_message(
        channel="telegram",
        direction="outbound",
        sender_id="zantara",
        content="ciao",
        metadata={"chat_id": 42},
    )

    args = router._db_pool.execute.await_args[0]
    meta = json.loads(args[-1])
    assert "session_id" not in meta
    assert meta["chat_id"] == 42


@pytest.mark.asyncio
async def test_stream_passthrough_unchanged():
    """The tee must not alter what the adapter receives."""
    events = [
        ChannelResponse(text="a", metadata={"event_type": "token"}),
        ChannelResponse(text="ab", metadata={"event_type": "answer"}),
    ]
    seen: list[str] = []

    router = ChannelRouter(_make_engine(events))
    adapter = _make_adapter("instagram", "hi")

    async def _collect(channel_id, stream):
        async for resp in stream:
            seen.append(resp.text)

    adapter.stream_response = AsyncMock(side_effect=_collect)
    router.register_adapter("instagram", adapter)
    router._persist_message = AsyncMock()

    await router.route_message("instagram", {})

    assert seen == ["a", "ab"]
