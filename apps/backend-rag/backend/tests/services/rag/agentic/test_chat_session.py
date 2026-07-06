from __future__ import annotations

from typing import Any

import pytest

from backend.services.rag.agentic.chat_session import ChatSession, MockChatSession


class TextChunk:
    def __init__(self, text: str) -> None:
        self.text = text


class CandidatePart:
    def __init__(self, text: str) -> None:
        self.text = text


class CandidateContent:
    def __init__(self, parts: list[CandidatePart]) -> None:
        self.parts = parts


class Candidate:
    def __init__(self, content: CandidateContent) -> None:
        self.content = content


class CandidateChunk:
    def __init__(self, text: str) -> None:
        self.candidates = [Candidate(CandidateContent([CandidatePart(text)]))]


class FakeUnderlyingChat:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []

    def send_message(self, message: str, stream: bool = False) -> Any:
        self.messages.append((message, stream))
        if stream:
            return [TextChunk("hello "), CandidateChunk("world")]
        return {"text": f"reply to {message}"}


class FakeClient:
    def __init__(self) -> None:
        self.chat = FakeUnderlyingChat()
        self.start_chat_kwargs: dict[str, Any] | None = None

    def start_chat(self, **kwargs: Any) -> FakeUnderlyingChat:
        self.start_chat_kwargs = kwargs
        return self.chat


@pytest.mark.asyncio
async def test_chat_session_initializes_client_with_history_and_system_instruction() -> None:
    client = FakeClient()
    history = [{"role": "user", "parts": [{"text": "hi"}]}]

    session = ChatSession(
        client=client,
        model="gemini-test",
        history=history,
        system_instruction="system",
    )

    assert client.start_chat_kwargs == {
        "model": "gemini-test",
        "history": history,
        "system_instruction": "system",
    }
    assert session.get_history() == history


@pytest.mark.asyncio
async def test_send_message_delegates_to_underlying_chat() -> None:
    client = FakeClient()
    session = ChatSession(client=client, model="gemini-test")

    response = await session.send_message("hello")

    assert response == {"text": "reply to hello"}
    assert client.chat.messages == [("hello", False)]


@pytest.mark.asyncio
async def test_send_message_raises_when_session_is_not_initialized() -> None:
    session = ChatSession(client=FakeClient(), model="gemini-test")
    session._chat_session = None

    with pytest.raises(RuntimeError, match="not initialized"):
        await session.send_message("hello")


@pytest.mark.asyncio
async def test_send_message_stream_yields_text_and_candidate_parts() -> None:
    client = FakeClient()
    session = ChatSession(client=client, model="gemini-test")

    chunks = [chunk async for chunk in session.send_message_stream("hello")]

    assert chunks == ["hello ", "world"]
    assert client.chat.messages == [("hello", True)]


def test_add_to_history_appends_model_format_and_get_history_returns_copy() -> None:
    session = ChatSession(client=FakeClient(), model="gemini-test")

    session.add_to_history("user", "hello")
    history = session.get_history()
    history.append({"role": "model", "parts": [{"text": "mutated"}]})

    assert session.history == [{"role": "user", "parts": [{"text": "hello"}]}]


@pytest.mark.asyncio
async def test_mock_chat_session_returns_fallback_response() -> None:
    session = MockChatSession(model="mock")

    response = await session.send_message("hello")

    assert response.text.startswith("Mi dispiace")
    assert response.candidates == []


@pytest.mark.asyncio
async def test_mock_chat_session_streams_fallback_words() -> None:
    session = MockChatSession(model="mock")

    words = [word async for word in session.send_message_stream("hello")]

    assert words[0] == "Mi "
    assert words[-1].endswith(" ")


def test_mock_chat_session_history_helpers_match_chat_session_shape() -> None:
    session = MockChatSession(history=[])

    session.add_to_history("model", "fallback")

    assert session.get_history() == [{"role": "model", "parts": [{"text": "fallback"}]}]
