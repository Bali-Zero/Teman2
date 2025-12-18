"""
Unit tests for Collective Memory Emitter Service
100% coverage target with comprehensive mocking
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.collective_memory_emitter import CollectiveMemoryEmitter

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def emitter():
    """Create CollectiveMemoryEmitter instance"""
    return CollectiveMemoryEmitter()


@pytest.fixture
def mock_event_source():
    """Mock event source with send method"""
    source = AsyncMock()
    source.send = AsyncMock()
    return source


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init(emitter):
    """Test initialization"""
    assert emitter is not None


# ============================================================================
# Tests for emit_memory_stored
# ============================================================================


@pytest.mark.asyncio
async def test_emit_memory_stored_success(emitter, mock_event_source):
    """Test emit_memory_stored successful"""
    await emitter.emit_memory_stored(
        mock_event_source,
        memory_key="mem-123",
        category="work",
        content="Test memory",
        members=["user1", "user2"],
        importance=0.8,
    )

    mock_event_source.send.assert_called_once()
    call_args = mock_event_source.send.call_args[0][0]
    assert "data: " in call_args
    assert "collective_memory_stored" in call_args
    assert "mem-123" in call_args


@pytest.mark.asyncio
async def test_emit_memory_stored_exception(emitter, mock_event_source):
    """Test emit_memory_stored with exception"""
    mock_event_source.send.side_effect = Exception("Send error")

    # Should not raise exception
    await emitter.emit_memory_stored(
        mock_event_source,
        memory_key="mem-123",
        category="work",
        content="Test",
        members=[],
        importance=0.5,
    )


# ============================================================================
# Tests for emit_preference_detected
# ============================================================================


@pytest.mark.asyncio
async def test_emit_preference_detected_success(emitter, mock_event_source):
    """Test emit_preference_detected successful"""
    await emitter.emit_preference_detected(
        mock_event_source,
        member="user1",
        preference="coffee",
        category="food",
        context="Morning routine",
    )

    mock_event_source.send.assert_called_once()
    call_args = mock_event_source.send.call_args[0][0]
    assert "preference_detected" in call_args
    assert "user1" in call_args
    assert "coffee" in call_args


@pytest.mark.asyncio
async def test_emit_preference_detected_no_context(emitter, mock_event_source):
    """Test emit_preference_detected without context"""
    await emitter.emit_preference_detected(
        mock_event_source,
        member="user1",
        preference="coffee",
        category="food",
    )

    mock_event_source.send.assert_called_once()


@pytest.mark.asyncio
async def test_emit_preference_detected_exception(emitter, mock_event_source):
    """Test emit_preference_detected with exception"""
    mock_event_source.send.side_effect = Exception("Send error")

    await emitter.emit_preference_detected(
        mock_event_source, member="user1", preference="coffee", category="food"
    )


# ============================================================================
# Tests for emit_milestone_detected
# ============================================================================


@pytest.mark.asyncio
async def test_emit_milestone_detected_success(emitter, mock_event_source):
    """Test emit_milestone_detected successful"""
    await emitter.emit_milestone_detected(
        mock_event_source,
        member="user1",
        milestone_type="birthday",
        date="2025-01-01",
        message="Happy birthday!",
        recurring=True,
    )

    mock_event_source.send.assert_called_once()
    call_args = mock_event_source.send.call_args[0][0]
    assert "milestone_detected" in call_args
    assert "user1" in call_args
    assert "birthday" in call_args


@pytest.mark.asyncio
async def test_emit_milestone_detected_no_date(emitter, mock_event_source):
    """Test emit_milestone_detected without date"""
    await emitter.emit_milestone_detected(
        mock_event_source,
        member="user1",
        milestone_type="anniversary",
        date=None,
        message="Anniversary",
    )

    mock_event_source.send.assert_called_once()


@pytest.mark.asyncio
async def test_emit_milestone_detected_exception(emitter, mock_event_source):
    """Test emit_milestone_detected with exception"""
    mock_event_source.send.side_effect = Exception("Send error")

    await emitter.emit_milestone_detected(
        mock_event_source,
        member="user1",
        milestone_type="birthday",
        date="2025-01-01",
        message="Happy birthday!",
    )


# ============================================================================
# Tests for emit_relationship_updated
# ============================================================================


@pytest.mark.asyncio
async def test_emit_relationship_updated_success(emitter, mock_event_source):
    """Test emit_relationship_updated successful"""
    await emitter.emit_relationship_updated(
        mock_event_source,
        member_a="user1",
        member_b="user2",
        relationship_type="colleague",
        strength=0.7,
        context="Work together",
    )

    mock_event_source.send.assert_called_once()
    call_args = mock_event_source.send.call_args[0][0]
    assert "relationship_updated" in call_args
    assert "user1" in call_args
    assert "user2" in call_args


@pytest.mark.asyncio
async def test_emit_relationship_updated_no_context(emitter, mock_event_source):
    """Test emit_relationship_updated without context"""
    await emitter.emit_relationship_updated(
        mock_event_source,
        member_a="user1",
        member_b="user2",
        relationship_type="friend",
        strength=0.8,
    )

    mock_event_source.send.assert_called_once()


@pytest.mark.asyncio
async def test_emit_relationship_updated_exception(emitter, mock_event_source):
    """Test emit_relationship_updated with exception"""
    mock_event_source.send.side_effect = Exception("Send error")

    await emitter.emit_relationship_updated(
        mock_event_source,
        member_a="user1",
        member_b="user2",
        relationship_type="colleague",
        strength=0.7,
    )


# ============================================================================
# Tests for emit_memory_consolidated
# ============================================================================


@pytest.mark.asyncio
async def test_emit_memory_consolidated_success(emitter, mock_event_source):
    """Test emit_memory_consolidated successful"""
    await emitter.emit_memory_consolidated(
        mock_event_source,
        action="merge",
        original_memories=[{"id": "mem1"}, {"id": "mem2"}],
        new_memory="Consolidated memory",
        reason="Similar content",
    )

    mock_event_source.send.assert_called_once()
    call_args = mock_event_source.send.call_args[0][0]
    assert "memory_consolidated" in call_args
    assert "merge" in call_args


@pytest.mark.asyncio
async def test_emit_memory_consolidated_exception(emitter, mock_event_source):
    """Test emit_memory_consolidated with exception"""
    mock_event_source.send.side_effect = Exception("Send error")

    await emitter.emit_memory_consolidated(
        mock_event_source,
        action="merge",
        original_memories=[],
        new_memory="Test",
        reason="Test reason",
    )


# ============================================================================
# Tests for _send_sse_event
# ============================================================================


@pytest.mark.asyncio
async def test_send_sse_event_with_send(emitter, mock_event_source):
    """Test _send_sse_event with send method"""
    data = {"type": "test", "data": "test"}
    await emitter._send_sse_event(mock_event_source, data)

    mock_event_source.send.assert_called_once()
    call_args = mock_event_source.send.call_args[0][0]
    assert "data: " in call_args
    assert "test" in call_args


@pytest.mark.asyncio
async def test_send_sse_event_with_write(emitter):
    """Test _send_sse_event with write method"""
    mock_event_source = AsyncMock()
    mock_event_source.write = AsyncMock()
    # Remove send method
    del mock_event_source.send

    data = {"type": "test"}
    await emitter._send_sse_event(mock_event_source, data)

    mock_event_source.write.assert_called_once()


@pytest.mark.asyncio
async def test_send_sse_event_no_method(emitter):
    """Test _send_sse_event without send or write method"""
    mock_event_source = MagicMock()
    # Remove both send and write
    del mock_event_source.send
    del mock_event_source.write

    data = {"type": "test"}
    # Should not raise exception
    await emitter._send_sse_event(mock_event_source, data)


@pytest.mark.asyncio
async def test_send_sse_event_exception(emitter, mock_event_source):
    """Test _send_sse_event with exception"""
    mock_event_source.send.side_effect = Exception("Send error")

    data = {"type": "test"}
    # Should not raise exception
    await emitter._send_sse_event(mock_event_source, data)


@pytest.mark.asyncio
async def test_send_sse_event_json_format(emitter, mock_event_source):
    """Test _send_sse_event JSON format"""
    data = {"type": "test", "value": 123}
    await emitter._send_sse_event(mock_event_source, data)

    call_args = mock_event_source.send.call_args[0][0]
    # Should be valid JSON in SSE format
    assert "data: " in call_args
    json_str = call_args.replace("data: ", "").strip()
    parsed = json.loads(json_str)
    assert parsed["type"] == "test"
    assert parsed["value"] == 123


# ============================================================================
# Tests for outer exception handlers (logger.error in emit_* methods)
# ============================================================================


@pytest.mark.asyncio
async def test_emit_memory_stored_sse_exception(emitter, mock_event_source):
    """Test emit_memory_stored when _send_sse_event fails"""
    with patch.object(emitter, "_send_sse_event", side_effect=Exception("SSE error")):
        await emitter.emit_memory_stored(
            mock_event_source, "mem-123", "work", "Test", ["user1"], 0.5
        )


@pytest.mark.asyncio
async def test_emit_preference_detected_sse_exception(emitter, mock_event_source):
    """Test emit_preference_detected when _send_sse_event fails"""
    with patch.object(emitter, "_send_sse_event", side_effect=Exception("SSE error")):
        await emitter.emit_preference_detected(mock_event_source, "user1", "coffee", "food")


@pytest.mark.asyncio
async def test_emit_milestone_detected_sse_exception(emitter, mock_event_source):
    """Test emit_milestone_detected when _send_sse_event fails"""
    with patch.object(emitter, "_send_sse_event", side_effect=Exception("SSE error")):
        await emitter.emit_milestone_detected(
            mock_event_source, "user1", "birthday", "2025-01-01", "Happy birthday!"
        )


@pytest.mark.asyncio
async def test_emit_relationship_updated_sse_exception(emitter, mock_event_source):
    """Test emit_relationship_updated when _send_sse_event fails"""
    with patch.object(emitter, "_send_sse_event", side_effect=Exception("SSE error")):
        await emitter.emit_relationship_updated(
            mock_event_source, "user1", "user2", "colleague", 0.7
        )


@pytest.mark.asyncio
async def test_emit_memory_consolidated_sse_exception(emitter, mock_event_source):
    """Test emit_memory_consolidated when _send_sse_event fails"""
    with patch.object(emitter, "_send_sse_event", side_effect=Exception("SSE error")):
        await emitter.emit_memory_consolidated(
            mock_event_source, "merge", [{"id": "mem1"}], "New memory", "Test reason"
        )
