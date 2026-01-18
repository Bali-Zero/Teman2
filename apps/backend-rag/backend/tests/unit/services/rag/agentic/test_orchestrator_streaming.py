"""
Unit tests for OrchestratorStreamingManager

Test coverage target: >95%
"""

import pytest

from backend.services.rag.agentic.orchestrator_streaming import (
    OrchestratorStreamingManager,
)


@pytest.fixture
def streaming_manager():
    """Create OrchestratorStreamingManager instance"""
    return OrchestratorStreamingManager(max_event_errors=3, event_validation_enabled=True)


@pytest.fixture
def streaming_manager_no_validation():
    """Create OrchestratorStreamingManager without validation"""
    return OrchestratorStreamingManager(max_event_errors=3, event_validation_enabled=False)


def test_create_error_event(streaming_manager):
    """Test error event creation"""
    event = streaming_manager.create_error_event(
        error_type="test_error", message="Test message", correlation_id="corr123"
    )

    assert event["type"] == "error"
    assert event["data"]["error_type"] == "test_error"
    assert event["data"]["message"] == "Test message"
    assert event["data"]["correlation_id"] == "corr123"
    assert "timestamp" in event


def test_validate_event_valid(streaming_manager):
    """Test validation of valid event"""
    valid_event = {"type": "token", "data": "test", "timestamp": 123456.0}
    result = streaming_manager.validate_event(valid_event, "corr123")

    assert result == valid_event


def test_validate_event_none(streaming_manager):
    """Test validation of None event"""
    result = streaming_manager.validate_event(None, "corr123")

    assert result is None


def test_validate_event_invalid_type(streaming_manager):
    """Test validation of invalid event type"""
    result = streaming_manager.validate_event("not a dict", "corr123")

    assert result is None


def test_validate_event_invalid_schema(streaming_manager):
    """Test validation of event with invalid schema"""
    invalid_event = {"type": "token"}  # Missing required 'data' field
    result = streaming_manager.validate_event(invalid_event, "corr123")

    assert result is None


def test_validate_event_no_validation(streaming_manager_no_validation):
    """Test validation disabled"""
    event = {"type": "token", "data": "test"}
    result = streaming_manager_no_validation.validate_event(event, "corr123")

    assert result == event


@pytest.mark.asyncio
async def test_process_event_stream_valid_events(streaming_manager):
    """Test processing stream with valid events"""

    async def event_generator():
        yield {"type": "token", "data": "hello"}
        yield {"type": "token", "data": " world"}
        yield {"type": "done", "data": None}

    events = []
    async for event in streaming_manager.process_event_stream(
        event_generator(), "corr123", "user123"
    ):
        events.append(event)

    assert len(events) == 3
    assert events[0]["type"] == "token"
    assert events[1]["type"] == "token"
    assert events[2]["type"] == "done"


@pytest.mark.asyncio
async def test_process_event_stream_with_errors(streaming_manager):
    """Test processing stream with some invalid events"""

    async def event_generator():
        yield {"type": "token", "data": "valid"}
        yield None  # Invalid
        yield {"type": "token", "data": "also valid"}
        yield "not a dict"  # Invalid
        yield {"type": "done", "data": None}

    events = []
    async for event in streaming_manager.process_event_stream(
        event_generator(), "corr123", "user123"
    ):
        events.append(event)

    # Should skip invalid events but continue
    assert len(events) >= 2  # At least valid events


@pytest.mark.asyncio
async def test_process_event_stream_too_many_errors(streaming_manager):
    """Test processing stream aborting after too many errors"""

    async def event_generator():
        for _ in range(5):
            yield None  # All invalid

    events = []
    async for event in streaming_manager.process_event_stream(
        event_generator(), "corr123", "user123"
    ):
        events.append(event)

    # Should abort after max_event_errors
    assert len(events) > 0
    # Last event should be error
    assert events[-1]["type"] == "error"


def test_create_initial_status_event(streaming_manager):
    """Test initial status event creation"""
    event = streaming_manager.create_initial_status_event("corr123")

    assert event["type"] == "status"
    assert event["data"]["status"] == "processing"
    assert event["data"]["correlation_id"] == "corr123"
    assert "timestamp" in event


def test_create_done_event(streaming_manager):
    """Test done event creation"""
    event = streaming_manager.create_done_event(execution_time=1.5, route_used="test-route")

    assert event["type"] == "done"
    assert event["data"]["execution_time"] == 1.5
    assert event["data"]["route_used"] == "test-route"


def test_create_metadata_event(streaming_manager):
    """Test metadata event creation"""
    metadata = {"status": "processing", "model": "gemini-flash"}
    event = streaming_manager.create_metadata_event(metadata)

    assert event["type"] == "metadata"
    assert event["data"] == metadata
    assert "timestamp" in event


@pytest.mark.asyncio
async def test_stream_text_response(streaming_manager):
    """Test simple text response streaming"""
    events = []
    async for event in streaming_manager.stream_text_response(
        text="Hello world", status="success", route="direct"
    ):
        events.append(event)

    assert len(events) > 0
    assert events[0]["type"] == "metadata"
    assert events[0]["data"]["status"] == "success"
    assert any(e["type"] == "token" for e in events)
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_text_response_empty(streaming_manager):
    """Test streaming empty text"""
    events = []
    async for event in streaming_manager.stream_text_response(text=""):
        events.append(event)

    # Should still emit metadata and done
    assert len(events) >= 2
