"""
Comprehensive tests for services/collective_memory_emitter.py
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.collective_memory_emitter import CollectiveMemoryEmitter


class TestCollectiveMemoryEmitter:
    """Comprehensive test suite for CollectiveMemoryEmitter"""

    @pytest.fixture
    def emitter(self):
        """Create CollectiveMemoryEmitter instance"""
        return CollectiveMemoryEmitter()

    @pytest.fixture
    def mock_event_source(self):
        """Mock SSE event source"""
        source = MagicMock()
        source.send = AsyncMock()
        return source

    @pytest.mark.asyncio
    async def test_emit_memory_stored_success(self, emitter, mock_event_source):
        """Test emit_memory_stored success"""
        await emitter.emit_memory_stored(
            event_source=mock_event_source,
            memory_key="test_key",
            category="test_category",
            content="Test content",
            members=["member1"],
            importance=0.8,
        )
        mock_event_source.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_memory_stored_error(self, emitter, mock_event_source):
        """Test emit_memory_stored with error"""
        mock_event_source.send.side_effect = Exception("Error")
        await emitter.emit_memory_stored(
            event_source=mock_event_source,
            memory_key="test_key",
            category="test_category",
            content="Test content",
            members=["member1"],
            importance=0.8,
        )
        # Should not raise error

    @pytest.mark.asyncio
    async def test_emit_preference_detected_success(self, emitter, mock_event_source):
        """Test emit_preference_detected success"""
        await emitter.emit_preference_detected(
            event_source=mock_event_source,
            member="member1",
            preference="prefers_email",
            category="communication",
            context="Test context",
        )
        mock_event_source.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_preference_detected_no_context(self, emitter, mock_event_source):
        """Test emit_preference_detected without context"""
        await emitter.emit_preference_detected(
            event_source=mock_event_source,
            member="member1",
            preference="prefers_email",
            category="communication",
        )
        mock_event_source.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_preference_detected_error(self, emitter, mock_event_source):
        """Test emit_preference_detected with error"""
        mock_event_source.send.side_effect = Exception("Error")
        await emitter.emit_preference_detected(
            event_source=mock_event_source,
            member="member1",
            preference="prefers_email",
            category="communication",
        )
        # Should not raise error

    @pytest.mark.asyncio
    async def test_emit_milestone_detected_success(self, emitter, mock_event_source):
        """Test emit_milestone_detected success"""
        await emitter.emit_milestone_detected(
            event_source=mock_event_source,
            member="member1",
            milestone_type="anniversary",
            date="2024-01-01",
            message="Test milestone",
        )
        mock_event_source.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_relationship_updated_success(self, emitter, mock_event_source):
        """Test emit_relationship_updated success"""
        await emitter.emit_relationship_updated(
            event_source=mock_event_source,
            member_a="member1",
            member_b="member2",
            relationship_type="colleague",
            strength=0.8,
        )
        mock_event_source.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_memory_consolidated_success(self, emitter, mock_event_source):
        """Test emit_memory_consolidated success"""
        await emitter.emit_memory_consolidated(
            event_source=mock_event_source,
            action="merge",
            original_memories=["key1", "key2"],
            new_memory="merged_key",
            reason="Duplicate information",
        )
        mock_event_source.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_sse_event(self, emitter, mock_event_source):
        """Test _send_sse_event"""
        event_data = {"type": "test", "data": "test"}
        await emitter._send_sse_event(mock_event_source, event_data)
        mock_event_source.send.assert_called_once()
