"""Tests for SSE/WebSocket event schemas."""

from nuzantara_schemas.events import SSEMessage, StreamEventType, StreamNodeEvent


class TestStreamNodeEvent:
    def test_create_event(self):
        event = StreamNodeEvent(
            run_id="abc-123",
            event_type=StreamEventType.NODE_START,
            node="understand",
            sequence=1,
        )
        assert event.event_type == StreamEventType.NODE_START

    def test_event_with_data(self):
        event = StreamNodeEvent(
            run_id="abc-123",
            event_type=StreamEventType.ANSWER_CHUNK,
            node="synthesize",
            data={"chunk": "The process for setting up..."},
            sequence=5,
        )
        assert event.data["chunk"].startswith("The process")


class TestSSEMessage:
    def test_to_sse_format(self):
        msg = SSEMessage(
            event="node_start",
            data='{"node": "understand"}',
            id="1",
        )
        sse = msg.to_sse()
        assert "event: node_start\n" in sse
        assert 'data: {"node": "understand"}\n' in sse
        assert "id: 1\n" in sse
        assert sse.endswith("\n\n")

    def test_to_sse_without_optional(self):
        msg = SSEMessage(event="done", data="{}")
        sse = msg.to_sse()
        assert "id:" not in sse
        assert "retry:" not in sse
