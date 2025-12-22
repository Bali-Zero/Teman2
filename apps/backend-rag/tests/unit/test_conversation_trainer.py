"""
Tests for agents/agents/conversation_trainer.py

Target: Autonomous conversation trainer
File: backend/agents/agents/conversation_trainer.py
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the class to test
from agents.agents.conversation_trainer import ConversationTrainer


class TestConversationTrainer:
    """Test ConversationTrainer agent"""

    def test_init(self):
        """Test: ConversationTrainer initializes with settings"""
        with patch("app.core.config.settings") as mock_settings:
            # GitHub token removed - platform agnostic
            # mock_settings.github_token = "test_token"

            mock_pool = MagicMock()
            trainer = ConversationTrainer(db_pool=mock_pool)

            assert trainer.db_pool == mock_pool
            # GitHub token removed - platform agnostic
        # assert trainer.github_token == "test_token"
        # db_url is no longer stored on the instance

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_conversations(self):
        """Test: Returns None when no high-rated conversations found"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.github_token = "token"

            # Mock asyncpg pool and connection
            mock_pool = MagicMock()
            mock_conn = AsyncMock()

            # Setup pool context manager
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Setup fetch return value (empty list)
            mock_conn.fetch.return_value = []

            trainer = ConversationTrainer(db_pool=mock_pool)
            result = await trainer.analyze_winning_patterns(days_back=7)

            assert result is None
            mock_pool.acquire.assert_called_once()
            mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_with_conversations(self):
        """Test: Analyzes patterns from high-rated conversations"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.github_token = "token"

            # Mock asyncpg pool and connection
            mock_pool = MagicMock()
            mock_conn = AsyncMock()

            # Setup pool context manager
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Mock conversation data
            # Rows behave like dictionaries in asyncpg
            row1 = {
                "conversation_id": "conv1",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"},
                ],
                "rating": 5,
                "client_feedback": "Great",
                "created_at": datetime.now(),
            }
            row2 = {
                "conversation_id": "conv2",
                "messages": [
                    {"role": "user", "content": "Help"},
                    {"role": "assistant", "content": "Sure"},
                ],
                "rating": 4,
                "client_feedback": "Good",
                "created_at": datetime.now(),
            }
            mock_conn.fetch.return_value = [row1, row2]

            trainer = ConversationTrainer(db_pool=mock_pool)

            # Mock ZantaraAIClient to avoid API calls
            trainer.zantara_client = MagicMock()
            trainer.zantara_client.generate_text = AsyncMock(
                return_value='{"successful_patterns": ["p1"], "prompt_improvements": ["i1"], "common_themes": ["t1"]}'
            )

            result = await trainer.analyze_winning_patterns(days_back=7)

            # Verify DB was queried correctly (should use v_rated_conversations view)
            mock_conn.fetch.assert_called_once()
            args = mock_conn.fetch.call_args
            assert "v_rated_conversations" in args[0][0] or "FROM v_rated_conversations" in args[0][0]
            assert "rating >=" in args[0][0]

            # Verify result
            assert result is not None
            assert "successful_patterns" in result
            assert result["successful_patterns"] == ["p1"]
