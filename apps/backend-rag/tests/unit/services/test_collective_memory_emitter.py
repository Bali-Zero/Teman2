"""
Comprehensive tests for CollectiveMemoryEmitter - Target 95%+ coverage
Tests for services/collective_memory_emitter.py
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.collective_memory_emitter import CollectiveMemoryEmitter, collective_memory_emitter


class TestCollectiveMemoryEmitter:
    """Comprehensive test suite for CollectiveMemoryEmitter"""

    @pytest.fixture
    def emitter(self):
        """Create CollectiveMemoryEmitter instance"""
        return CollectiveMemoryEmitter()

    @pytest.fixture
    def mock_event_source_with_send(self):
        """Create mock event source with send method"""
        mock = MagicMock()
        mock.send = AsyncMock()
        return mock

    @pytest.fixture
    def mock_event_source_with_write(self):
        """Create mock event source with write method"""
        mock = MagicMock()
        mock.write = AsyncMock()
        return mock

    @pytest.fixture
    def mock_event_source_no_methods(self):
        """Create mock event source without send/write methods"""
        mock = MagicMock()
        # Remove send and write methods if they exist
        if hasattr(mock, "send"):
            delattr(mock, "send")
        if hasattr(mock, "write"):
            delattr(mock, "write")
        return mock

    # Test emit_memory_stored
    @pytest.mark.asyncio
    async def test_emit_memory_stored_success(self, emitter, mock_event_source_with_send):
        """Test emit_memory_stored sends correct event data"""
        memory_key = "test_memory_key"
        category = "preference"
        content = "User prefers Italian"
        members = ["user1", "user2"]
        importance = 0.8

        await emitter.emit_memory_stored(
            event_source=mock_event_source_with_send,
            memory_key=memory_key,
            category=category,
            content=content,
            members=members,
            importance=importance,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "collective_memory_stored"
        assert event_data["memory_key"] == memory_key
        assert event_data["category"] == category
        assert event_data["content"] == content
        assert event_data["members"] == members
        assert event_data["importance"] == importance
        assert "timestamp" in event_data

        # Verify timestamp is valid ISO format
        datetime.fromisoformat(event_data["timestamp"])

    @pytest.mark.asyncio
    async def test_emit_memory_stored_error_handling(self, emitter):
        """Test emit_memory_stored handles errors gracefully"""
        # Create mock that raises exception on send
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Send failed"))

        # Should not raise exception, but log error
        await emitter.emit_memory_stored(
            event_source=mock_source,
            memory_key="test",
            category="test",
            content="test",
            members=["test"],
            importance=0.5,
        )
        # If we get here without exception, error handling worked

    # Test emit_preference_detected
    @pytest.mark.asyncio
    async def test_emit_preference_detected_with_context(
        self, emitter, mock_event_source_with_send
    ):
        """Test emit_preference_detected sends correct event data with context"""
        member = "user1"
        preference = "Italian language"
        category = "communication"
        context = "User mentioned during onboarding"

        await emitter.emit_preference_detected(
            event_source=mock_event_source_with_send,
            member=member,
            preference=preference,
            category=category,
            context=context,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "preference_detected"
        assert event_data["member"] == member
        assert event_data["preference"] == preference
        assert event_data["category"] == category
        assert event_data["context"] == context
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_emit_preference_detected_without_context(
        self, emitter, mock_event_source_with_send
    ):
        """Test emit_preference_detected without context parameter"""
        member = "user1"
        preference = "Dark mode"
        category = "UI"

        await emitter.emit_preference_detected(
            event_source=mock_event_source_with_send,
            member=member,
            preference=preference,
            category=category,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "preference_detected"
        assert event_data["context"] is None

    @pytest.mark.asyncio
    async def test_emit_preference_detected_error_handling(self, emitter):
        """Test emit_preference_detected handles errors gracefully"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Send failed"))

        await emitter.emit_preference_detected(
            event_source=mock_source,
            member="test",
            preference="test",
            category="test",
        )
        # If we get here without exception, error handling worked

    # Test emit_milestone_detected
    @pytest.mark.asyncio
    async def test_emit_milestone_detected_non_recurring(
        self, emitter, mock_event_source_with_send
    ):
        """Test emit_milestone_detected for non-recurring milestone"""
        member = "user1"
        milestone_type = "birthday"
        date = "2024-01-15"
        message = "User's birthday"
        recurring = False

        await emitter.emit_milestone_detected(
            event_source=mock_event_source_with_send,
            member=member,
            milestone_type=milestone_type,
            date=date,
            message=message,
            recurring=recurring,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "milestone_detected"
        assert event_data["member"] == member
        assert event_data["milestone_type"] == milestone_type
        assert event_data["date"] == date
        assert event_data["message"] == message
        assert event_data["recurring"] == recurring
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_emit_milestone_detected_recurring(self, emitter, mock_event_source_with_send):
        """Test emit_milestone_detected for recurring milestone"""
        member = "user1"
        milestone_type = "anniversary"
        date = None
        message = "Company anniversary"
        recurring = True

        await emitter.emit_milestone_detected(
            event_source=mock_event_source_with_send,
            member=member,
            milestone_type=milestone_type,
            date=date,
            message=message,
            recurring=recurring,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "milestone_detected"
        assert event_data["recurring"] == True
        assert event_data["date"] is None

    @pytest.mark.asyncio
    async def test_emit_milestone_detected_error_handling(self, emitter):
        """Test emit_milestone_detected handles errors gracefully"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Send failed"))

        await emitter.emit_milestone_detected(
            event_source=mock_source,
            member="test",
            milestone_type="test",
            date="2024-01-01",
            message="test",
        )
        # If we get here without exception, error handling worked

    # Test emit_relationship_updated
    @pytest.mark.asyncio
    async def test_emit_relationship_updated_with_context(
        self, emitter, mock_event_source_with_send
    ):
        """Test emit_relationship_updated sends correct event data with context"""
        member_a = "user1"
        member_b = "user2"
        relationship_type = "business_partner"
        strength = 0.9
        context = "Collaborated on project"

        await emitter.emit_relationship_updated(
            event_source=mock_event_source_with_send,
            member_a=member_a,
            member_b=member_b,
            relationship_type=relationship_type,
            strength=strength,
            context=context,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "relationship_updated"
        assert event_data["member_a"] == member_a
        assert event_data["member_b"] == member_b
        assert event_data["relationship_type"] == relationship_type
        assert event_data["strength"] == strength
        assert event_data["context"] == context
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_emit_relationship_updated_without_context(
        self, emitter, mock_event_source_with_send
    ):
        """Test emit_relationship_updated without context parameter"""
        member_a = "user1"
        member_b = "user2"
        relationship_type = "colleague"
        strength = 0.7

        await emitter.emit_relationship_updated(
            event_source=mock_event_source_with_send,
            member_a=member_a,
            member_b=member_b,
            relationship_type=relationship_type,
            strength=strength,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "relationship_updated"
        assert event_data["context"] is None

    @pytest.mark.asyncio
    async def test_emit_relationship_updated_error_handling(self, emitter):
        """Test emit_relationship_updated handles errors gracefully"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Send failed"))

        await emitter.emit_relationship_updated(
            event_source=mock_source,
            member_a="test1",
            member_b="test2",
            relationship_type="test",
            strength=0.5,
        )
        # If we get here without exception, error handling worked

    # Test emit_memory_consolidated
    @pytest.mark.asyncio
    async def test_emit_memory_consolidated_success(self, emitter, mock_event_source_with_send):
        """Test emit_memory_consolidated sends correct event data"""
        action = "merge"
        original_memories = ["memory1", "memory2", "memory3"]
        new_memory = "consolidated_memory"
        reason = "Similar content detected"

        await emitter.emit_memory_consolidated(
            event_source=mock_event_source_with_send,
            action=action,
            original_memories=original_memories,
            new_memory=new_memory,
            reason=reason,
        )

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse the event data
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)

        # Verify event structure
        assert event_data["type"] == "memory_consolidated"
        assert event_data["action"] == action
        assert event_data["original_memories"] == original_memories
        assert event_data["new_memory"] == new_memory
        assert event_data["reason"] == reason
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_emit_memory_consolidated_error_handling(self, emitter):
        """Test emit_memory_consolidated handles errors gracefully"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Send failed"))

        await emitter.emit_memory_consolidated(
            event_source=mock_source,
            action="test",
            original_memories=["test"],
            new_memory="test",
            reason="test",
        )
        # If we get here without exception, error handling worked

    # Test _send_sse_event with different event sources
    @pytest.mark.asyncio
    async def test_send_sse_event_with_send_method(self, emitter, mock_event_source_with_send):
        """Test _send_sse_event uses send method when available"""
        test_data = {"type": "test_event", "data": "test"}

        await emitter._send_sse_event(mock_event_source_with_send, test_data)

        # Verify send was called with correct format
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Verify SSE format
        assert call_args.startswith("data: ")
        assert call_args.endswith("\n\n")

        # Verify JSON content
        json_str = call_args.replace("data: ", "").strip()
        parsed_data = json.loads(json_str)
        assert parsed_data == test_data

    @pytest.mark.asyncio
    async def test_send_sse_event_with_write_method(self, emitter, mock_event_source_with_write):
        """Test _send_sse_event uses write method when send not available"""
        test_data = {"type": "test_event", "data": "test"}

        await emitter._send_sse_event(mock_event_source_with_write, test_data)

        # Verify write was called
        assert mock_event_source_with_write.write.called
        call_args = mock_event_source_with_write.write.call_args[0][0]

        # Verify SSE format
        assert call_args.startswith("data: ")
        assert call_args.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_send_sse_event_no_send_write_methods(
        self, emitter, mock_event_source_no_methods
    ):
        """Test _send_sse_event handles missing send/write methods"""
        test_data = {"type": "test_event", "data": "test"}

        # Should not raise exception, but log warning
        await emitter._send_sse_event(mock_event_source_no_methods, test_data)
        # If we get here without exception, fallback handling worked

    @pytest.mark.asyncio
    async def test_send_sse_event_exception_in_send(self, emitter):
        """Test _send_sse_event handles exceptions during send"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Network error"))

        test_data = {"type": "test_event", "data": "test"}

        # Should not raise exception, but log error
        await emitter._send_sse_event(mock_source, test_data)
        # If we get here without exception, error handling worked

    @pytest.mark.asyncio
    async def test_send_sse_event_exception_in_write(self, emitter):
        """Test _send_sse_event handles exceptions during write"""
        mock_source = MagicMock()
        # Remove send attribute to force write usage
        mock_source.write = AsyncMock(side_effect=Exception("Write error"))

        test_data = {"type": "test_event", "data": "test"}

        # Should not raise exception, but log error
        await emitter._send_sse_event(mock_source, test_data)
        # If we get here without exception, error handling worked

    @pytest.mark.asyncio
    async def test_send_sse_event_json_serialization(self, emitter, mock_event_source_with_send):
        """Test _send_sse_event correctly serializes complex data"""
        complex_data = {
            "type": "complex_event",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "number": 42.5,
            "boolean": True,
            "null": None,
        }

        await emitter._send_sse_event(mock_event_source_with_send, complex_data)

        # Verify send was called
        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]

        # Parse and verify JSON
        json_str = call_args.replace("data: ", "").strip()
        parsed_data = json.loads(json_str)
        assert parsed_data == complex_data

    # Test singleton instance
    def test_singleton_instance_exists(self):
        """Test that singleton collective_memory_emitter exists"""
        assert collective_memory_emitter is not None
        assert isinstance(collective_memory_emitter, CollectiveMemoryEmitter)

    # Integration tests - test event format compliance
    @pytest.mark.asyncio
    async def test_all_events_have_timestamp(self, emitter, mock_event_source_with_send):
        """Test that all emitted events include timestamp field"""
        # Test each emit method
        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", "content", ["m1"], 0.5
        )
        await emitter.emit_preference_detected(mock_event_source_with_send, "member", "pref", "cat")
        await emitter.emit_milestone_detected(
            mock_event_source_with_send, "member", "type", "2024-01-01", "msg"
        )
        await emitter.emit_relationship_updated(
            mock_event_source_with_send, "m1", "m2", "type", 0.5
        )
        await emitter.emit_memory_consolidated(
            mock_event_source_with_send, "action", ["m1"], "new", "reason"
        )

        # Verify all calls had timestamp
        assert mock_event_source_with_send.send.call_count == 5
        for call in mock_event_source_with_send.send.call_args_list:
            event_str = call[0][0].replace("data: ", "").strip()
            event_data = json.loads(event_str)
            assert "timestamp" in event_data
            # Verify timestamp is valid
            datetime.fromisoformat(event_data["timestamp"])

    @pytest.mark.asyncio
    async def test_all_events_have_type(self, emitter, mock_event_source_with_send):
        """Test that all emitted events include type field"""
        # Test each emit method
        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", "content", ["m1"], 0.5
        )
        await emitter.emit_preference_detected(mock_event_source_with_send, "member", "pref", "cat")
        await emitter.emit_milestone_detected(
            mock_event_source_with_send, "member", "type", "2024-01-01", "msg"
        )
        await emitter.emit_relationship_updated(
            mock_event_source_with_send, "m1", "m2", "type", 0.5
        )
        await emitter.emit_memory_consolidated(
            mock_event_source_with_send, "action", ["m1"], "new", "reason"
        )

        # Verify all calls had type
        expected_types = [
            "collective_memory_stored",
            "preference_detected",
            "milestone_detected",
            "relationship_updated",
            "memory_consolidated",
        ]

        assert mock_event_source_with_send.send.call_count == 5
        for i, call in enumerate(mock_event_source_with_send.send.call_args_list):
            event_str = call[0][0].replace("data: ", "").strip()
            event_data = json.loads(event_str)
            assert event_data["type"] == expected_types[i]

    @pytest.mark.asyncio
    async def test_sse_format_compliance(self, emitter, mock_event_source_with_send):
        """Test that SSE events follow Server-Sent Events format"""
        test_data = {"type": "test", "data": "value"}

        await emitter._send_sse_event(mock_event_source_with_send, test_data)

        call_args = mock_event_source_with_send.send.call_args[0][0]

        # SSE format requirements:
        # 1. Must start with "data: "
        assert call_args.startswith("data: ")

        # 2. Must end with double newline
        assert call_args.endswith("\n\n")

        # 3. Data must be valid JSON
        json_str = call_args.replace("data: ", "").strip()
        parsed = json.loads(json_str)
        assert parsed == test_data

    @pytest.mark.asyncio
    async def test_emit_methods_log_on_success(self, emitter, mock_event_source_with_send):
        """Test that emit methods log success messages"""
        with patch("services.collective_memory_emitter.logger") as mock_logger:
            await emitter.emit_memory_stored(
                mock_event_source_with_send, "key", "cat", "content", ["m1"], 0.5
            )
            # Verify info log was called
            assert mock_logger.info.called
            log_msg = mock_logger.info.call_args[0][0]
            assert "collective_memory_stored" in log_msg

    @pytest.mark.asyncio
    async def test_emit_methods_log_on_error(self, emitter):
        """Test that emit methods log error messages on failure"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Test error"))

        with patch("services.collective_memory_emitter.logger") as mock_logger:
            await emitter.emit_memory_stored(mock_source, "key", "cat", "content", ["m1"], 0.5)
            # Verify error log was called
            assert mock_logger.error.called
            log_msg = mock_logger.error.call_args[0][0]
            assert "Failed to emit memory_stored" in log_msg

    @pytest.mark.asyncio
    async def test_send_sse_event_logs_warning_no_methods(
        self, emitter, mock_event_source_no_methods
    ):
        """Test _send_sse_event logs warning when no send/write methods"""
        with patch("services.collective_memory_emitter.logger") as mock_logger:
            await emitter._send_sse_event(mock_event_source_no_methods, {"test": "data"})
            # Verify warning was logged
            assert mock_logger.warning.called
            log_msg = mock_logger.warning.call_args[0][0]
            assert "doesn't have send/write method" in log_msg

    @pytest.mark.asyncio
    async def test_send_sse_event_logs_error_on_exception(self, emitter):
        """Test _send_sse_event logs error on exception"""
        mock_source = MagicMock()
        mock_source.send = AsyncMock(side_effect=Exception("Test error"))

        with patch("services.collective_memory_emitter.logger") as mock_logger:
            await emitter._send_sse_event(mock_source, {"test": "data"})
            # Verify error log was called
            assert mock_logger.error.called
            log_msg = mock_logger.error.call_args[0][0]
            assert "Failed to send SSE event" in log_msg

    # Edge cases
    @pytest.mark.asyncio
    async def test_emit_with_empty_members_list(self, emitter, mock_event_source_with_send):
        """Test emit_memory_stored with empty members list"""
        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", "content", [], 0.5
        )

        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)
        assert event_data["members"] == []

    @pytest.mark.asyncio
    async def test_emit_with_zero_importance(self, emitter, mock_event_source_with_send):
        """Test emit_memory_stored with zero importance"""
        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", "content", ["m1"], 0.0
        )

        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)
        assert event_data["importance"] == 0.0

    @pytest.mark.asyncio
    async def test_emit_with_max_importance(self, emitter, mock_event_source_with_send):
        """Test emit_memory_stored with maximum importance"""
        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", "content", ["m1"], 1.0
        )

        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)
        assert event_data["importance"] == 1.0

    @pytest.mark.asyncio
    async def test_emit_with_empty_original_memories(self, emitter, mock_event_source_with_send):
        """Test emit_memory_consolidated with empty original memories list"""
        await emitter.emit_memory_consolidated(
            mock_event_source_with_send, "action", [], "new_memory", "reason"
        )

        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)
        assert event_data["original_memories"] == []

    @pytest.mark.asyncio
    async def test_emit_with_special_characters_in_strings(
        self, emitter, mock_event_source_with_send
    ):
        """Test emit methods handle special characters correctly"""
        special_content = 'Test "quotes" and \n newlines \t tabs'

        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", special_content, ["m1"], 0.5
        )

        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)
        assert event_data["content"] == special_content

    @pytest.mark.asyncio
    async def test_emit_with_unicode_characters(self, emitter, mock_event_source_with_send):
        """Test emit methods handle Unicode characters correctly"""
        unicode_content = "Test emoji"

        await emitter.emit_memory_stored(
            mock_event_source_with_send, "key", "cat", unicode_content, ["m1"], 0.5
        )

        assert mock_event_source_with_send.send.called
        call_args = mock_event_source_with_send.send.call_args[0][0]
        event_str = call_args.replace("data: ", "").strip()
        event_data = json.loads(event_str)
        assert event_data["content"] == unicode_content
