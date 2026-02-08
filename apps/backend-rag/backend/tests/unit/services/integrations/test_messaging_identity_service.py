"""
Comprehensive pytest suite for Messaging Identity Service.
Tests: get_user_by_phone, get_user_by_telegram, create_mapping,
       update_last_message, get_mappings_for_user, deactivate_mapping,
       get_messaging_identity_service (singleton)

Target: 80%+ coverage

Uses:
- pytest.mark.asyncio for async database operations
- pytest.mark.parametrize for input validation variants
- AsyncMock for asyncpg pool/connection mocking
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set env vars before importing
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")


# ============================================================================
# FIXTURES
# ============================================================================


def _create_async_cm(return_value):
    """Helper: create async context manager mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def mock_conn():
    """Mock asyncpg connection with async methods."""
    return AsyncMock()


@pytest.fixture
def mock_pool(mock_conn):
    """Mock asyncpg pool returning mock_conn from acquire()."""
    pool = MagicMock()
    pool.acquire.return_value = _create_async_cm(mock_conn)
    return pool


@pytest.fixture
def service(mock_pool):
    """MessagingIdentityService instance with mocked pool."""
    from backend.services.integrations.messaging_identity_service import (
        MessagingIdentityService,
    )

    return MessagingIdentityService(db_pool=mock_pool)


@pytest.fixture
def sample_user_row():
    """Sample database row for messaging_users table."""
    return {
        "user_id": "abc-123-def-456",
        "display_name": "Marco Rossi",
        "verified": True,
        "last_message_at": "2026-01-15T10:30:00",
    }


@pytest.fixture
def sample_mapping_rows():
    """Multiple mapping rows for a user."""
    return [
        {
            "id": 1,
            "channel": "whatsapp",
            "phone": "628123456789",
            "telegram_chat_id": None,
            "display_name": "Marco Rossi",
            "verified": True,
            "last_message_at": "2026-01-15T10:30:00",
        },
        {
            "id": 2,
            "channel": "telegram",
            "phone": None,
            "telegram_chat_id": 98765432,
            "display_name": "Marco R.",
            "verified": False,
            "last_message_at": "2026-01-14T08:00:00",
        },
    ]


# ============================================================================
# get_user_by_phone TESTS
# ============================================================================


class TestGetUserByPhone:
    """Tests for get_user_by_phone method."""

    @pytest.mark.asyncio
    async def test_found(self, service, mock_conn, sample_user_row) -> None:
        """Return user when phone is mapped."""
        mock_conn.fetchrow.return_value = sample_user_row

        result = await service.get_user_by_phone("628123456789")

        assert result is not None
        assert result["user_id"] == "abc-123-def-456"
        assert result["display_name"] == "Marco Rossi"
        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_not_found(self, service, mock_conn) -> None:
        """Return None when phone is not mapped."""
        mock_conn.fetchrow.return_value = None

        result = await service.get_user_by_phone("000000000")
        assert result is None

    @pytest.mark.asyncio
    async def test_strips_plus_prefix(self, service, mock_conn) -> None:
        """Phone number is normalized (+ prefix stripped)."""
        mock_conn.fetchrow.return_value = None

        await service.get_user_by_phone("+628123456789")

        # Verify the query was called with normalized phone (no +)
        call_args = mock_conn.fetchrow.call_args
        assert call_args[0][1] == "628123456789"

    @pytest.mark.asyncio
    async def test_database_error(self, service, mock_conn) -> None:
        """Database error returns None (graceful degradation)."""
        import asyncpg

        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Connection lost")

        result = await service.get_user_by_phone("628123456789")
        assert result is None

    @pytest.mark.asyncio
    async def test_query_uses_correct_sql(self, service, mock_conn) -> None:
        """Verify the SQL query structure."""
        mock_conn.fetchrow.return_value = None

        await service.get_user_by_phone("628111")

        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        assert "messaging_users" in query
        assert "channel = 'whatsapp'" in query
        assert "active = TRUE" in query


# ============================================================================
# get_user_by_telegram TESTS
# ============================================================================


class TestGetUserByTelegram:
    """Tests for get_user_by_telegram method."""

    @pytest.mark.asyncio
    async def test_found(self, service, mock_conn, sample_user_row) -> None:
        """Return user when telegram chat_id is mapped."""
        mock_conn.fetchrow.return_value = sample_user_row

        result = await service.get_user_by_telegram(98765432)

        assert result is not None
        assert result["user_id"] == "abc-123-def-456"

    @pytest.mark.asyncio
    async def test_not_found(self, service, mock_conn) -> None:
        """Return None when telegram chat_id is not mapped."""
        mock_conn.fetchrow.return_value = None

        result = await service.get_user_by_telegram(000000)
        assert result is None

    @pytest.mark.asyncio
    async def test_database_error(self, service, mock_conn) -> None:
        """Database error returns None."""
        import asyncpg

        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Timeout")

        result = await service.get_user_by_telegram(12345)
        assert result is None

    @pytest.mark.asyncio
    async def test_query_uses_telegram_channel(self, service, mock_conn) -> None:
        """Query filters by telegram channel."""
        mock_conn.fetchrow.return_value = None

        await service.get_user_by_telegram(12345)

        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        assert "channel = 'telegram'" in query
        assert "telegram_chat_id = $1" in query


# ============================================================================
# create_mapping TESTS
# ============================================================================


class TestCreateMapping:
    """Tests for create_mapping method."""

    @pytest.mark.asyncio
    async def test_whatsapp_mapping_success(self, service, mock_conn) -> None:
        """Successfully create WhatsApp mapping."""
        result = await service.create_mapping(
            user_id="user-uuid-123",
            channel="whatsapp",
            phone="+628123456789",
            display_name="Test User",
            verified=True,
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_telegram_mapping_success(self, service, mock_conn) -> None:
        """Successfully create Telegram mapping."""
        result = await service.create_mapping(
            user_id="user-uuid-456",
            channel="telegram",
            telegram_chat_id=98765432,
            display_name="TG User",
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_channel(self, service) -> None:
        """Invalid channel returns False."""
        result = await service.create_mapping(
            user_id="user-uuid",
            channel="email",  # Invalid channel
            phone="628123",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_whatsapp_without_phone(self, service) -> None:
        """WhatsApp channel without phone returns False."""
        result = await service.create_mapping(
            user_id="user-uuid",
            channel="whatsapp",
            # phone not provided
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_telegram_without_chat_id(self, service) -> None:
        """Telegram channel without chat_id returns False."""
        result = await service.create_mapping(
            user_id="user-uuid",
            channel="telegram",
            # telegram_chat_id not provided
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_phone_normalized(self, service, mock_conn) -> None:
        """Phone number is normalized (+ prefix stripped)."""
        await service.create_mapping(
            user_id="user-uuid",
            channel="whatsapp",
            phone="+628123456789",
        )

        call_args = mock_conn.execute.call_args
        # phone should be normalized (3rd positional arg after query)
        params = call_args[0]
        assert params[3] == "628123456789"  # phone param position

    @pytest.mark.asyncio
    async def test_unique_violation(self, service, mock_conn) -> None:
        """UniqueViolationError returns False."""
        import asyncpg

        mock_conn.execute.side_effect = asyncpg.UniqueViolationError("duplicate key")

        result = await service.create_mapping(
            user_id="user-uuid",
            channel="whatsapp",
            phone="628123",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_database_error(self, service, mock_conn) -> None:
        """Generic database error returns False."""
        import asyncpg

        mock_conn.execute.side_effect = asyncpg.PostgresError("Connection lost")

        result = await service.create_mapping(
            user_id="user-uuid",
            channel="whatsapp",
            phone="628123",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_upsert_on_conflict(self, service, mock_conn) -> None:
        """Query uses ON CONFLICT DO UPDATE for idempotent creates."""
        await service.create_mapping(
            user_id="user-uuid",
            channel="whatsapp",
            phone="628123",
        )

        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        assert "ON CONFLICT" in query
        assert "DO UPDATE SET" in query


# ============================================================================
# update_last_message TESTS
# ============================================================================


class TestUpdateLastMessage:
    """Tests for update_last_message method."""

    @pytest.mark.asyncio
    async def test_update_whatsapp(self, service, mock_conn) -> None:
        """Update last_message_at for WhatsApp."""
        result = await service.update_last_message(phone="+628123456789")
        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_telegram(self, service, mock_conn) -> None:
        """Update last_message_at for Telegram."""
        result = await service.update_last_message(telegram_chat_id=98765)
        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_identifier(self, service) -> None:
        """No phone or chat_id returns False."""
        result = await service.update_last_message()
        assert result is False

    @pytest.mark.asyncio
    async def test_database_error(self, service, mock_conn) -> None:
        """Database error returns False."""
        import asyncpg

        mock_conn.execute.side_effect = asyncpg.PostgresError("Error")

        result = await service.update_last_message(phone="628123")
        assert result is False


# ============================================================================
# get_mappings_for_user TESTS
# ============================================================================


class TestGetMappingsForUser:
    """Tests for get_mappings_for_user method."""

    @pytest.mark.asyncio
    async def test_returns_mappings(self, service, mock_conn, sample_mapping_rows) -> None:
        """Return list of mappings for a user."""
        mock_conn.fetch.return_value = sample_mapping_rows

        result = await service.get_mappings_for_user("user-uuid-123")

        assert len(result) == 2
        assert result[0]["channel"] == "whatsapp"
        assert result[1]["channel"] == "telegram"

    @pytest.mark.asyncio
    async def test_no_mappings(self, service, mock_conn) -> None:
        """Return empty list when no mappings found."""
        mock_conn.fetch.return_value = []

        result = await service.get_mappings_for_user("unknown-uuid")
        assert result == []

    @pytest.mark.asyncio
    async def test_database_error(self, service, mock_conn) -> None:
        """Database error returns empty list."""
        import asyncpg

        mock_conn.fetch.side_effect = asyncpg.PostgresError("Timeout")

        result = await service.get_mappings_for_user("user-uuid")
        assert result == []

    @pytest.mark.asyncio
    async def test_only_active_mappings(self, service, mock_conn) -> None:
        """Query filters for active=TRUE only."""
        mock_conn.fetch.return_value = []

        await service.get_mappings_for_user("user-uuid")

        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "active = TRUE" in query


# ============================================================================
# deactivate_mapping TESTS
# ============================================================================


class TestDeactivateMapping:
    """Tests for deactivate_mapping method."""

    @pytest.mark.asyncio
    async def test_deactivate_whatsapp(self, service, mock_conn) -> None:
        """Deactivate WhatsApp mapping."""
        result = await service.deactivate_mapping(phone="+628123456789")
        assert result is True

        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        assert "active = FALSE" in query
        assert "channel = 'whatsapp'" in query

    @pytest.mark.asyncio
    async def test_deactivate_telegram(self, service, mock_conn) -> None:
        """Deactivate Telegram mapping."""
        result = await service.deactivate_mapping(telegram_chat_id=98765)
        assert result is True

        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        assert "active = FALSE" in query
        assert "channel = 'telegram'" in query

    @pytest.mark.asyncio
    async def test_no_identifier(self, service) -> None:
        """No identifier returns False."""
        result = await service.deactivate_mapping()
        assert result is False

    @pytest.mark.asyncio
    async def test_database_error(self, service, mock_conn) -> None:
        """Database error returns False."""
        import asyncpg

        mock_conn.execute.side_effect = asyncpg.PostgresError("Error")

        result = await service.deactivate_mapping(phone="628123")
        assert result is False


# ============================================================================
# SINGLETON TESTS
# ============================================================================


class TestSingleton:
    """Tests for get_messaging_identity_service factory."""

    def test_creates_instance(self, mock_pool) -> None:
        """Factory creates a new instance."""
        import backend.services.integrations.messaging_identity_service as mod

        # Reset singleton
        mod._messaging_identity_service = None

        service = mod.get_messaging_identity_service(mock_pool)
        assert isinstance(service, mod.MessagingIdentityService)

    def test_returns_same_instance(self, mock_pool) -> None:
        """Factory returns cached singleton."""
        import backend.services.integrations.messaging_identity_service as mod

        # Reset singleton
        mod._messaging_identity_service = None

        service1 = mod.get_messaging_identity_service(mock_pool)
        service2 = mod.get_messaging_identity_service(mock_pool)
        assert service1 is service2

        # Cleanup
        mod._messaging_identity_service = None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestMessagingIdentityIntegration:
    """Integration-style tests combining multiple operations."""

    @pytest.mark.asyncio
    async def test_create_then_lookup_whatsapp(self, service, mock_conn, sample_user_row) -> None:
        """Create mapping, then look it up."""
        # Create
        await service.create_mapping(
            user_id="user-uuid-789",
            channel="whatsapp",
            phone="628111222333",
            display_name="New User",
        )

        # Lookup
        mock_conn.fetchrow.return_value = sample_user_row
        result = await service.get_user_by_phone("628111222333")
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_then_deactivate(self, service, mock_conn) -> None:
        """Create mapping, then deactivate it."""
        # Create
        await service.create_mapping(
            user_id="user-uuid-999",
            channel="whatsapp",
            phone="628444555666",
        )

        # Deactivate
        result = await service.deactivate_mapping(phone="628444555666")
        assert result is True

    @pytest.mark.asyncio
    async def test_multi_channel_user(self, service, mock_conn, sample_mapping_rows) -> None:
        """User with both WhatsApp and Telegram mappings."""
        # Create WhatsApp mapping
        await service.create_mapping(
            user_id="multi-user-uuid",
            channel="whatsapp",
            phone="628123456789",
        )

        # Create Telegram mapping
        await service.create_mapping(
            user_id="multi-user-uuid",
            channel="telegram",
            telegram_chat_id=98765432,
        )

        # Get all mappings
        mock_conn.fetch.return_value = sample_mapping_rows
        mappings = await service.get_mappings_for_user("multi-user-uuid")
        assert len(mappings) == 2
        channels = {m["channel"] for m in mappings}
        assert channels == {"whatsapp", "telegram"}
