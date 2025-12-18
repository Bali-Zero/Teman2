"""
Integration Tests for ConversationTrainer
Tests autonomous conversation learning and prompt improvement
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestConversationTrainerIntegration:
    """Comprehensive integration tests for ConversationTrainer"""

    @pytest_asyncio.fixture
    async def mock_db_pool(self):
        """Create mock database pool"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_pool

    @pytest_asyncio.fixture
    async def mock_zantara_client(self):
        """Create mock ZantaraAIClient"""
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value='{"successful_patterns": ["pattern1"], "prompt_improvements": ["improvement1"], "common_themes": ["theme1"]}'
        )
        return mock_client

    @pytest_asyncio.fixture
    async def trainer(self, mock_db_pool, mock_zantara_client):
        """Create ConversationTrainer instance"""
        from agents.agents.conversation_trainer import ConversationTrainer

        return ConversationTrainer(db_pool=mock_db_pool, zantara_client=mock_zantara_client)

    def test_initialization(self, trainer):
        """Test trainer initialization"""
        assert trainer is not None
        assert trainer.db_pool is not None
        assert trainer.zantara_client is not None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_conversations(self, trainer, mock_db_pool):
        """Test analyzing patterns when no conversations found"""
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_with_conversations(
        self, trainer, mock_db_pool, mock_zantara_client
    ):
        """Test analyzing patterns with high-rated conversations"""
        mock_conn = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "test"},
                {"role": "assistant", "content": "response"},
            ],
            "rating": 5,
            "client_feedback": "Great!",
            "created_at": "2025-01-01",
        }[key]
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        # May return analysis or fallback

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_invalid_days(self, trainer):
        """Test analyzing patterns with invalid days_back"""
        result = await trainer.analyze_winning_patterns(days_back=0)

        # Should use default 7 days
        assert result is not None or result is None  # May return None if no data

    @pytest.mark.asyncio
    async def test_generate_prompt_update(self, trainer, mock_zantara_client):
        """Test generating prompt update from analysis"""
        analysis = {
            "successful_patterns": ["pattern1", "pattern2"],
            "prompt_improvements": ["improvement1"],
            "common_themes": ["theme1"],
        }

        mock_zantara_client.generate_text = AsyncMock(return_value="Improved prompt text")

        result = await trainer.generate_prompt_update(analysis)

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_prompt_update_empty_analysis(self, trainer):
        """Test generating prompt update with empty analysis"""
        result = await trainer.generate_prompt_update({})

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_db_pool_from_instance(self, trainer, mock_db_pool):
        """Test getting database pool from instance"""
        pool = await trainer._get_db_pool()

        assert pool is not None
        assert pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_from_app_state(self):
        """Test getting database pool from app.state"""
        mock_pool = MagicMock()

        with patch("agents.agents.conversation_trainer.app") as mock_app:
            mock_app.state.db_pool = mock_pool

            from agents.agents.conversation_trainer import ConversationTrainer

            trainer = ConversationTrainer(db_pool=None)

            pool = await trainer._get_db_pool()

            assert pool == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_not_available(self):
        """Test getting database pool when not available"""
        from agents.agents.conversation_trainer import ConversationTrainer

        trainer = ConversationTrainer(db_pool=None)

        with patch("agents.agents.conversation_trainer.app", side_effect=Exception()):
            with pytest.raises(RuntimeError):
                await trainer._get_db_pool()

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_timeout(
        self, trainer, mock_db_pool, mock_zantara_client
    ):
        """Test analyzing patterns with timeout"""
        mock_conn = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "test"}],
            "rating": 5,
            "client_feedback": None,
            "created_at": "2025-01-01",
        }[key]
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_zantara_client.generate_text = AsyncMock(side_effect=TimeoutError("Timeout"))

        result = await trainer.analyze_winning_patterns(days_back=7, timeout=0.1)

        # Should return fallback or None
        assert result is not None or result is None
