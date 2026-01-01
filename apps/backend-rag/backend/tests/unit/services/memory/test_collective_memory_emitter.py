"""
Unit tests for CollectiveMemoryEmitter
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.memory.collective_memory_emitter import CollectiveMemoryEmitter


@pytest.fixture
def mock_event_source():
    """Mock event source"""
    source = MagicMock()
    source.send = AsyncMock()
    return source


@pytest.fixture
def emitter():
    """Create CollectiveMemoryEmitter instance"""
    emitter = CollectiveMemoryEmitter()
    emitter._send_sse_event = AsyncMock()
    return emitter


class TestCollectiveMemoryEmitter:
    """Tests for CollectiveMemoryEmitter"""

    @pytest.mark.asyncio
    async def test_emit_memory_stored(self, emitter, mock_event_source):
        """Test emitting memory stored event"""
        await emitter.emit_memory_stored(
            mock_event_source,
            memory_key="test_key",
            category="fact",
            content="Test content",
            members=["member1"],
            importance=0.8
        )
        emitter._send_sse_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_preference_detected(self, emitter, mock_event_source):
        """Test emitting preference detected event"""
        await emitter.emit_preference_detected(
            mock_event_source,
            member="member1",
            preference="Italian language",
            category="language",
            context="conversation"
        )
        emitter._send_sse_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_milestone_detected(self, emitter, mock_event_source):
        """Test emitting milestone detected event"""
        await emitter.emit_milestone_detected(
            mock_event_source,
            member="member1",
            milestone_type="deadline",
            date="2024-12-31",
            message="Project deadline",
            recurring=False
        )
        emitter._send_sse_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_relationship_updated(self, emitter, mock_event_source):
        """Test emitting relationship updated event"""
        await emitter.emit_relationship_updated(
            mock_event_source,
            member_a="member1",
            member_b="member2",
            relationship_type="collaboration",
            strength=0.7,
            context="project"
        )
        emitter._send_sse_event.assert_called_once()

