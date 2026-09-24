import json

import pytest

from backend.services.memory.collective_memory_emitter import CollectiveMemoryEmitter


class SendEventSource:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def send(self, event: str) -> None:
        self.events.append(event)


class WriteEventSource:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def write(self, event: str) -> None:
        self.events.append(event)


class RaisingEventSource:
    async def send(self, event: str) -> None:
        raise RuntimeError("connection closed")


def _decode_sse(event: str) -> dict:
    assert event.startswith("data: ")
    assert event.endswith("\n\n")
    return json.loads(event.removeprefix("data: ").strip())


@pytest.mark.asyncio
async def test_emit_memory_stored_sends_standard_sse_payload() -> None:
    emitter = CollectiveMemoryEmitter()
    source = SendEventSource()

    await emitter.emit_memory_stored(
        source,
        memory_key="process:pt-pma",
        category="process",
        content="PT PMA setup takes several steps",
        members=["ops", "legal"],
        importance=0.91,
    )

    assert len(source.events) == 1
    payload = _decode_sse(source.events[0])
    assert payload["type"] == "collective_memory_stored"
    assert payload["memory_key"] == "process:pt-pma"
    assert payload["members"] == ["ops", "legal"]
    assert payload["importance"] == 0.91
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_emit_preference_detected_uses_write_fallback() -> None:
    emitter = CollectiveMemoryEmitter()
    source = WriteEventSource()

    await emitter.emit_preference_detected(
        source,
        member="client-1",
        preference="short updates",
        category="communication",
        context="WhatsApp",
    )

    payload = _decode_sse(source.events[0])
    assert payload["type"] == "preference_detected"
    assert payload["member"] == "client-1"
    assert payload["context"] == "WhatsApp"


@pytest.mark.asyncio
async def test_other_memory_events_include_domain_fields() -> None:
    emitter = CollectiveMemoryEmitter()
    milestone_source = SendEventSource()
    relationship_source = SendEventSource()
    consolidated_source = SendEventSource()

    await emitter.emit_milestone_detected(
        milestone_source,
        member="client-1",
        milestone_type="approval",
        date="2026-07-05",
        message="Visa approved",
        recurring=False,
    )
    await emitter.emit_relationship_updated(
        relationship_source,
        member_a="client-1",
        member_b="advisor-1",
        relationship_type="primary_contact",
        strength=0.8,
        context="case handoff",
    )
    await emitter.emit_memory_consolidated(
        consolidated_source,
        action="merge",
        original_memories=["old-a", "old-b"],
        new_memory="merged",
        reason="duplicate facts",
    )

    assert _decode_sse(milestone_source.events[0])["milestone_type"] == "approval"
    assert _decode_sse(relationship_source.events[0])["strength"] == 0.8
    assert _decode_sse(consolidated_source.events[0])["original_memories"] == [
        "old-a",
        "old-b",
    ]


@pytest.mark.asyncio
async def test_emit_errors_are_swallowed_for_broken_streams() -> None:
    emitter = CollectiveMemoryEmitter()

    await emitter.emit_memory_consolidated(
        RaisingEventSource(),
        action="merge",
        original_memories=[],
        new_memory="fallback",
        reason="test",
    )
