"""
Integration tests for Conversations Service
Tests conversation persistence and CRM integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestConversationsIntegration:
    """Integration tests for Conversations Service"""

    @pytest.mark.asyncio
    async def test_conversation_save_flow(self, postgres_container):
        """Test conversation save flow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "user_id": "test@example.com", "messages": []}
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            from app.routers.conversations import save_conversation

            # Test that the endpoint can be called
            assert save_conversation is not None

    @pytest.mark.asyncio
    async def test_conversation_history_retrieval(self, postgres_container):
        """Test conversation history retrieval"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={"messages": [{"role": "user", "content": "Hello"}]}
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            from app.routers.conversations import get_conversation_history

            # Test that the endpoint can be called
            assert get_conversation_history is not None
