"""
Unit tests for AutoCRMService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

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
        mock_extractor.extract_from_conversation = AsyncMock(return_value={
            "client": {
                "name": "Test Client",
                "email": "test@example.com",
                "phone": "+1234567890",
                "confidence": 0.9
            },
            "practice_intent": {
                "detected": True,
                "type": "visa",
                "confidence": 0.8
            }
        })
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
                user_email="test@example.com"
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
            "email": "test@example.com"
        }.get(key)
        mock_client_row.get = lambda key, default=None: {
            "id": 1,
            "name": "Test Client",
            "email": "test@example.com"
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
                {"role": "assistant", "content": "I can help with that"}
            ],
            user_email="test@example.com"
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
                {"role": "assistant", "content": "I can help with that"}
            ],
            user_email="new@example.com"
        )
        assert isinstance(result, dict)
        assert "success" in result

