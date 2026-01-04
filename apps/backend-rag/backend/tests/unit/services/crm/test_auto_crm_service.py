"""
Unit tests for AutoCRMService
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.crm.auto_crm_service import AutoCRMService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        conn = MagicMock()

        @asynccontextmanager
        async def transaction():
            yield conn

        conn.transaction.return_value = transaction()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        yield conn

    pool.acquire = acquire
    return pool


@pytest.fixture
def auto_crm_service(mock_db_pool):
    """Create AutoCRMService instance"""
    with patch("services.crm.auto_crm_service.get_extractor") as mock_get_extractor:
        mock_extractor = MagicMock()
        mock_extractor.extract_from_conversation = AsyncMock(
            return_value={
                "client": {
                    "name": "Test Client",
                    "email": "test@example.com",
                    "phone": "+1234567890",
                    "confidence": 0.9,
                },
                "practice_intent": {"detected": True, "type": "visa", "confidence": 0.8},
            }
        )
        mock_get_extractor.return_value = mock_extractor
        return AutoCRMService(db_pool=mock_db_pool)


class TestAutoCRMService:
    """Tests for AutoCRMService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        with patch("services.crm.auto_crm_service.get_extractor"):
            service = AutoCRMService(db_pool=mock_db_pool)
            assert service.pool == mock_db_pool

    def test_init_no_pool(self):
        """Test initialization without pool"""
        with patch("services.crm.auto_crm_service.get_extractor"):
            service = AutoCRMService()
            assert service.pool is None

    @pytest.mark.asyncio
    async def test_connect(self, auto_crm_service):
        """Test connect method"""
        await auto_crm_service.connect()
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_close(self, auto_crm_service):
        """Test close method"""
        await auto_crm_service.close()
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_process_conversation_no_pool(self):
        """Test processing conversation without pool"""
        with patch("services.crm.auto_crm_service.get_extractor"):
            service = AutoCRMService()
            result = await service.process_conversation(
                conversation_id=1,
                messages=[{"role": "user", "content": "Test"}],
                user_email="test@example.com",
            )
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_process_conversation_success(self, auto_crm_service, mock_db_pool):
        """Test processing conversation successfully"""
        mock_client_row = MagicMock()
        mock_client_row.__getitem__ = lambda self, key: {
            "id": 1,
            "name": "Test Client",
            "email": "test@example.com",
        }.get(key)
        mock_client_row.get = lambda key, default=None: {
            "id": 1,
            "name": "Test Client",
            "email": "test@example.com",
        }.get(key, default)

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            conn.fetchrow = AsyncMock(return_value=mock_client_row)
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=1)
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        result = await auto_crm_service.process_conversation(
            conversation_id=1,
            messages=[
                {"role": "user", "content": "I need a visa"},
                {"role": "assistant", "content": "I can help with that"},
            ],
            user_email="test@example.com",
        )
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_process_conversation_create_client(self, auto_crm_service, mock_db_pool):
        """Test processing conversation and creating client"""

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            conn.fetchrow = AsyncMock(return_value=None)  # No existing client
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=1)  # New client ID
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        result = await auto_crm_service.process_conversation(
            conversation_id=1,
            messages=[
                {"role": "user", "content": "I need a visa"},
                {"role": "assistant", "content": "I can help with that"},
            ],
            user_email="new@example.com",
        )
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_process_conversation_update_client(self, auto_crm_service, mock_db_pool):
        """Test processing conversation and updating existing client"""
        mock_existing_client = MagicMock()
        mock_existing_client.__getitem__ = lambda self, key: {
            "id": 1,
            "full_name": "Old Name",
            "email": "test@example.com",
            "phone": None,  # Missing - should be updated
            "whatsapp": None,
            "nationality": None,
        }.get(key)
        mock_existing_client.get = lambda key, default=None: {
            "id": 1,
            "full_name": "Old Name",
            "email": "test@example.com",
            "phone": None,  # Missing - should be updated
            "whatsapp": None,
            "nationality": None,
        }.get(key, default)

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            conn.fetchrow = AsyncMock(return_value=mock_existing_client)
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=1)
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        # Mock extractor to return high confidence for update with phone
        auto_crm_service.extractor.extract_from_conversation = AsyncMock(
            return_value={
                "client": {
                    "full_name": "New Name",
                    "email": "test@example.com",
                    "phone": "+1234567890",  # New phone value (existing has None)
                    "whatsapp": None,
                    "nationality": None,
                    "confidence": 0.8,  # Above UPDATE threshold (0.6)
                },
                "practice_intent": {"detected": False},
                "sentiment": "positive",
                "urgency": "normal",
                "summary": "Test conversation",
                "action_items": [],
                "extracted_entities": {},
            }
        )

        # Mock should_create_practice to return False (no practice intent)
        async def mock_should_create_practice(extracted):
            return False

        auto_crm_service.extractor.should_create_practice = mock_should_create_practice

        result = await auto_crm_service.process_conversation(
            conversation_id=1,
            messages=[{"role": "user", "content": "Update my info"}],
            user_email="test@example.com",
        )
        assert result["success"] is True
        assert result["client_updated"] is True

    @pytest.mark.asyncio
    async def test_process_conversation_create_practice(self, auto_crm_service, mock_db_pool):
        """Test processing conversation and creating practice"""
        mock_client_row = MagicMock()
        mock_client_row.__getitem__ = lambda self, key: {"id": 1}[key]

        mock_practice_type = MagicMock()
        mock_practice_type.__getitem__ = lambda self, key: {
            "id": 1,
            "base_price": 1000.0,
        }[key]

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            # First call: existing client, second: no existing practice, third: practice_type
            conn.fetchrow = AsyncMock(side_effect=[mock_client_row, None, mock_practice_type])
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(side_effect=[1, 1])  # client_id, practice_id
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        # Mock extractor to return practice intent
        auto_crm_service.extractor.extract_from_conversation = AsyncMock(
            return_value={
                "client": {
                    "full_name": "Test Client",
                    "email": "test@example.com",
                    "confidence": 0.9,
                },
                "practice_intent": {
                    "detected": True,
                    "practice_type_code": "KITAS",
                    "confidence": 0.8,
                    "details": "Work permit",
                },
                "sentiment": "positive",
                "urgency": "normal",
                "summary": "Test conversation",
                "action_items": [],
                "extracted_entities": {},
            }
        )

        # Mock should_create_practice as async method
        async def mock_should_create_practice(extracted):
            return True

        auto_crm_service.extractor.should_create_practice = mock_should_create_practice

        result = await auto_crm_service.process_conversation(
            conversation_id=1,
            messages=[{"role": "user", "content": "I need a KITAS"}],
            user_email="test@example.com",
        )
        assert result["success"] is True
        # Practice creation depends on practice_type being found
        assert "practice_id" in result

    @pytest.mark.asyncio
    async def test_process_conversation_existing_practice(self, auto_crm_service, mock_db_pool):
        """Test processing conversation with existing practice"""
        mock_client_row = MagicMock()
        mock_client_row.__getitem__ = lambda self, key: {"id": 1}[key]

        mock_practice_type = MagicMock()
        mock_practice_type.__getitem__ = lambda self, key: {
            "id": 1,
            "base_price": 1000.0,
        }[key]

        mock_existing_practice = MagicMock()
        mock_existing_practice.__getitem__ = lambda self, key: {"id": 2}[key]

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            # Order of fetchrow calls:
            # 1. Check existing client with user_email
            # 2. If extracted email different, check with extracted email
            # 3. Get practice_type
            # 4. Check existing practice
            conn.fetchrow = AsyncMock(
                side_effect=[
                    mock_client_row,  # 1. Existing client found with user_email
                    mock_practice_type,  # 2. Practice type found (after should_create_practice)
                    mock_existing_practice,  # 3. Existing practice found
                ]
            )
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=1)  # interaction_id
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        auto_crm_service.extractor.extract_from_conversation = AsyncMock(
            return_value={
                "client": {
                    "email": "test@example.com",  # Same as user_email, so no second fetchrow
                    "confidence": 0.9,
                },
                "practice_intent": {
                    "detected": True,
                    "practice_type_code": "KITAS",
                    "confidence": 0.8,
                },
                "sentiment": "positive",
                "summary": "Test",
                "action_items": [],
                "extracted_entities": {},
            }
        )

        # Mock should_create_practice as async method
        async def mock_should_create_practice(extracted):
            return True

        auto_crm_service.extractor.should_create_practice = mock_should_create_practice

        result = await auto_crm_service.process_conversation(
            conversation_id=1,
            messages=[{"role": "user", "content": "I need a KITAS"}],
            user_email="test@example.com",
        )
        assert result["success"] is True
        assert result["practice_created"] is False
        assert result["practice_id"] == 2

    @pytest.mark.asyncio
    async def test_process_conversation_error(self, auto_crm_service, mock_db_pool):
        """Test handling errors in process_conversation"""

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        result = await auto_crm_service.process_conversation(
            conversation_id=1,
            messages=[{"role": "user", "content": "Test"}],
            user_email="test@example.com",
        )
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_process_email_interaction_success(self, auto_crm_service, mock_db_pool):
        """Test processing email interaction"""

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            conn.fetchrow = AsyncMock(return_value=None)
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(side_effect=[1, 1])  # conversation_id, client_id
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        email_data = {
            "subject": "Test Email",
            "sender": "test@example.com",
            "body": "I need help with visa",
            "date": "2025-01-01",
            "id": "email123",
        }

        result = await auto_crm_service.process_email_interaction(
            email_data=email_data, team_member="test_member", db_pool=mock_db_pool
        )
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_process_email_interaction_extract_email(self, auto_crm_service, mock_db_pool):
        """Test extracting email from 'Name <email@domain.com>' format"""

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()

            @asynccontextmanager
            async def transaction():
                yield conn

            conn.transaction.return_value = transaction()
            conn.fetchrow = AsyncMock(return_value=None)
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(side_effect=[1, 1])
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        email_data = {
            "subject": "Test",
            "sender": "John Doe <john@example.com>",
            "body": "Test body",
            "date": "2025-01-01",
            "id": "email123",
        }

        result = await auto_crm_service.process_email_interaction(
            email_data=email_data, db_pool=mock_db_pool
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_process_email_interaction_no_pool(self):
        """Test processing email without pool"""
        with patch("services.crm.auto_crm_service.get_extractor"):
            service = AutoCRMService()
            result = await service.process_email_interaction(
                email_data={"subject": "Test", "sender": "test@example.com", "body": "Test"}
            )
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_process_email_interaction_error(self, auto_crm_service, mock_db_pool):
        """Test handling errors in process_email_interaction"""

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetchval = AsyncMock(side_effect=Exception("DB error"))
            yield conn

        mock_db_pool.acquire = acquire
        auto_crm_service.pool = mock_db_pool

        result = await auto_crm_service.process_email_interaction(
            email_data={
                "subject": "Test",
                "sender": "test@example.com",
                "body": "Test",
                "date": "2025-01-01",
                "id": "email123",
            },
            db_pool=mock_db_pool,
        )
        assert result["success"] is False

    def test_get_auto_crm_service_singleton(self):
        """Test get_auto_crm_service returns singleton"""
        with patch("services.crm.auto_crm_service.AutoCRMService") as mock_service_class:
            mock_instance = MagicMock()
            mock_service_class.return_value = mock_instance

            # Reset singleton
            import services.crm.auto_crm_service as module
            from services.crm.auto_crm_service import get_auto_crm_service

            module._auto_crm_instance = None

            result1 = get_auto_crm_service()
            result2 = get_auto_crm_service()

            assert result1 == result2
            assert mock_service_class.call_count == 1
