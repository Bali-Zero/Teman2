"""
Unit tests for backend/services/communication/thread_manager.py

Covers:
  - get_or_create_thread (client_id, sender_id, new thread)
  - add_message_to_thread
  - assign_thread
  - resolve_thread
  - update_thread
  - mark_read
  - get_thread_messages
  - get_threads (filters, RBAC)
  - get_thread_summary
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.services.communication.models import Priority, ThreadFilter, ThreadStatus
from backend.services.communication.thread_manager import ThreadManager


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def manager(mock_db):
    return ThreadManager(mock_db)


THREAD_UUID = uuid4()
NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


# ============================================================
# get_or_create_thread
# ============================================================


class TestGetOrCreateThread:
    @pytest.mark.asyncio
    async def test_finds_existing_thread_for_client(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=THREAD_UUID)
        mock_db.execute = AsyncMock()

        result = await manager.get_or_create_thread(client_id=1, channel="whatsapp")
        assert result == THREAD_UUID
        # Should have updated channels
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_thread_for_client(self, manager, mock_db):
        # fetchval returns None (no existing), then returns new UUID
        mock_db.fetchval = AsyncMock(side_effect=[None, THREAD_UUID])

        result = await manager.get_or_create_thread(client_id=1, channel="telegram")
        assert result == THREAD_UUID
        assert mock_db.fetchval.call_count == 2  # search + create

    @pytest.mark.asyncio
    async def test_finds_existing_by_sender_id(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=THREAD_UUID)

        result = await manager.get_or_create_thread(
            client_id=None, channel="whatsapp", sender_id="628123456"
        )
        assert result == THREAD_UUID

    @pytest.mark.asyncio
    async def test_creates_thread_for_unidentified_sender(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(side_effect=[None, THREAD_UUID])

        result = await manager.get_or_create_thread(
            client_id=None, channel="web", sender_id="anon-123"
        )
        assert result == THREAD_UUID
        # Should include sender_id in metadata
        create_call = mock_db.fetchval.call_args_list[1]
        metadata = json.loads(create_call[0][4])
        assert metadata["sender_id"] == "anon-123"

    @pytest.mark.asyncio
    async def test_creates_thread_with_subject(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(side_effect=[None, THREAD_UUID])

        result = await manager.get_or_create_thread(
            client_id=1, channel="web", subject="KITAS inquiry"
        )
        assert result == THREAD_UUID

    @pytest.mark.asyncio
    async def test_no_client_no_sender(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=THREAD_UUID)

        result = await manager.get_or_create_thread(client_id=None, channel="web")
        assert result == THREAD_UUID


# ============================================================
# add_message_to_thread
# ============================================================


class TestAddMessageToThread:
    @pytest.mark.asyncio
    async def test_inbound_increments_unread(self, manager, mock_db):
        mock_db.execute = AsyncMock()

        await manager.add_message_to_thread(
            THREAD_UUID, 1, "whatsapp", preview="Hello", direction="inbound"
        )
        # Should call execute twice (update message, update thread)
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_outbound_no_unread_increment(self, manager, mock_db):
        mock_db.execute = AsyncMock()

        await manager.add_message_to_thread(
            THREAD_UUID, 2, "telegram", direction="outbound"
        )
        # Check the thread update query doesn't contain unread_count
        second_call = mock_db.execute.call_args_list[1]
        query = second_call[0][0]
        assert "unread_count" not in query

    @pytest.mark.asyncio
    async def test_no_preview(self, manager, mock_db):
        mock_db.execute = AsyncMock()

        await manager.add_message_to_thread(THREAD_UUID, 3, "web")
        assert mock_db.execute.call_count == 2


# ============================================================
# assign_thread
# ============================================================


class TestAssignThread:
    @pytest.mark.asyncio
    async def test_assigns_to_email(self, manager, mock_db):
        mock_db.execute = AsyncMock()

        await manager.assign_thread(THREAD_UUID, "zero@balizero.com")
        mock_db.execute.assert_called_once()
        args = mock_db.execute.call_args[0]
        assert THREAD_UUID in args
        assert "zero@balizero.com" in args


# ============================================================
# resolve_thread
# ============================================================


class TestResolveThread:
    @pytest.mark.asyncio
    async def test_resolves(self, manager, mock_db):
        mock_db.execute = AsyncMock()

        await manager.resolve_thread(THREAD_UUID)
        mock_db.execute.assert_called_once()
        query = mock_db.execute.call_args[0][0]
        assert "resolved" in query


# ============================================================
# update_thread
# ============================================================


class TestUpdateThread:
    @pytest.mark.asyncio
    async def test_update_status(self, manager, mock_db):
        mock_db.execute = AsyncMock(return_value="UPDATE 1")

        result = await manager.update_thread(THREAD_UUID, status=ThreadStatus.ASSIGNED)
        assert result is True

    @pytest.mark.asyncio
    async def test_update_priority(self, manager, mock_db):
        mock_db.execute = AsyncMock(return_value="UPDATE 1")

        result = await manager.update_thread(THREAD_UUID, priority=Priority.URGENT)
        assert result is True

    @pytest.mark.asyncio
    async def test_update_assigned_to(self, manager, mock_db):
        mock_db.execute = AsyncMock(return_value="UPDATE 1")

        result = await manager.update_thread(THREAD_UUID, assigned_to="admin@balizero.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_all_fields(self, manager, mock_db):
        mock_db.execute = AsyncMock(return_value="UPDATE 1")

        result = await manager.update_thread(
            THREAD_UUID,
            status=ThreadStatus.RESOLVED,
            priority=Priority.HIGH,
            assigned_to="zero@balizero.com",
        )
        assert result is True
        query = mock_db.execute.call_args[0][0]
        assert "resolved_at" in query  # resolved status adds resolved_at

    @pytest.mark.asyncio
    async def test_no_updates_returns_true(self, manager, mock_db):
        result = await manager.update_thread(THREAD_UUID)
        assert result is True
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_thread_not_found(self, manager, mock_db):
        mock_db.execute = AsyncMock(return_value="UPDATE 0")

        result = await manager.update_thread(THREAD_UUID, status=ThreadStatus.CLOSED)
        assert result is False


# ============================================================
# mark_read
# ============================================================


class TestMarkRead:
    @pytest.mark.asyncio
    async def test_resets_unread(self, manager, mock_db):
        mock_db.execute = AsyncMock()

        await manager.mark_read(THREAD_UUID)
        mock_db.execute.assert_called_once()
        query = mock_db.execute.call_args[0][0]
        assert "unread_count = 0" in query


# ============================================================
# get_thread_messages
# ============================================================


class TestGetThreadMessages:
    @pytest.mark.asyncio
    async def test_returns_messages(self, manager, mock_db):
        mock_db.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "channel": "whatsapp",
                    "direction": "inbound",
                    "sender_id": "628123456",
                    "content": "Hello",
                    "metadata": json.dumps({"sender_name": "John"}),
                    "created_at": NOW,
                },
                {
                    "id": 2,
                    "channel": "whatsapp",
                    "direction": "outbound",
                    "sender_id": "system",
                    "content": "Hi John!",
                    "metadata": {},
                    "created_at": NOW,
                },
            ]
        )

        messages = await manager.get_thread_messages(THREAD_UUID)
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[0].metadata["sender_name"] == "John"
        assert messages[1].direction == "outbound"

    @pytest.mark.asyncio
    async def test_empty_messages(self, manager, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])

        messages = await manager.get_thread_messages(THREAD_UUID)
        assert messages == []

    @pytest.mark.asyncio
    async def test_handles_none_metadata(self, manager, mock_db):
        mock_db.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "channel": "web",
                    "direction": "inbound",
                    "sender_id": "anon",
                    "content": "Test",
                    "metadata": None,
                    "created_at": None,
                },
            ]
        )

        messages = await manager.get_thread_messages(THREAD_UUID)
        assert len(messages) == 1
        assert messages[0].metadata == {}
        assert messages[0].created_at == ""


# ============================================================
# get_threads
# ============================================================


class TestGetThreads:
    @pytest.mark.asyncio
    async def test_no_filters(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=1)
        mock_db.fetch = AsyncMock(
            return_value=[
                {
                    "id": THREAD_UUID,
                    "client_id": 1,
                    "status": "open",
                    "priority": "normal",
                    "assigned_to": None,
                    "subject": "Test",
                    "channels": ["whatsapp"],
                    "intent": "lead",
                    "unread_count": 2,
                    "last_message_preview": "Hello",
                    "last_activity_at": NOW,
                    "created_at": NOW,
                    "metadata": "{}",
                    "client_name": "John",
                    "client_email": "john@example.com",
                },
            ]
        )

        threads, total = await manager.get_threads(ThreadFilter(), is_admin=True)
        assert total == 1
        assert len(threads) == 1
        assert threads[0]["client_name"] == "John"

    @pytest.mark.asyncio
    async def test_with_status_filter(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])

        threads, total = await manager.get_threads(
            ThreadFilter(status=ThreadStatus.RESOLVED), is_admin=True
        )
        assert total == 0
        assert threads == []

    @pytest.mark.asyncio
    async def test_non_admin_rbac(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])

        await manager.get_threads(
            ThreadFilter(), user_email="staff@balizero.com", is_admin=False
        )
        # Should add RBAC condition
        fetchval_query = mock_db.fetchval.call_args[0][0]
        assert "assigned_to" in fetchval_query

    @pytest.mark.asyncio
    async def test_handles_json_string_metadata(self, manager, mock_db):
        mock_db.fetchval = AsyncMock(return_value=1)
        mock_db.fetch = AsyncMock(
            return_value=[
                {
                    "id": THREAD_UUID,
                    "client_id": None,
                    "status": "open",
                    "priority": "low",
                    "assigned_to": None,
                    "subject": None,
                    "channels": None,
                    "intent": None,
                    "unread_count": 0,
                    "last_message_preview": None,
                    "last_activity_at": None,
                    "created_at": None,
                    "metadata": json.dumps({"key": "val"}),
                    "client_name": None,
                    "client_email": None,
                },
            ]
        )

        threads, _ = await manager.get_threads(ThreadFilter(), is_admin=True)
        assert threads[0]["metadata"] == {"key": "val"}
        assert threads[0]["channels"] == []


# ============================================================
# get_thread_summary
# ============================================================


class TestGetThreadSummary:
    @pytest.mark.asyncio
    async def test_summary_format(self, manager, mock_db):
        mock_db.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "channel": "whatsapp",
                    "direction": "inbound",
                    "sender_id": "628123456",
                    "content": "Hello, I need help with my KITAS",
                    "metadata": json.dumps({"sender_name": "John"}),
                    "created_at": NOW,
                },
                {
                    "id": 2,
                    "channel": "whatsapp",
                    "direction": "outbound",
                    "sender_id": "system",
                    "content": "Hi John, happy to help!",
                    "metadata": {},
                    "created_at": NOW,
                },
            ]
        )

        summary = await manager.get_thread_summary(THREAD_UUID)
        assert "[WH]" in summary  # channel[:2].upper()
        assert "John" in summary
        assert "KITAS" in summary

    @pytest.mark.asyncio
    async def test_summary_empty_thread(self, manager, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])

        summary = await manager.get_thread_summary(THREAD_UUID)
        assert summary == ""

    @pytest.mark.asyncio
    async def test_summary_uses_first_name(self, manager, mock_db):
        mock_db.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "channel": "telegram",
                    "direction": "inbound",
                    "sender_id": "tg_123",
                    "content": "Help",
                    "metadata": json.dumps({"first_name": "Marco"}),
                    "created_at": NOW,
                },
            ]
        )

        summary = await manager.get_thread_summary(THREAD_UUID)
        assert "Marco" in summary
