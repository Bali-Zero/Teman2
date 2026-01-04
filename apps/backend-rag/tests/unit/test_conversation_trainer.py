"""
Tests for agents/agents/conversation_trainer.py

Target: Autonomous conversation trainer
File: backend/agents/agents/conversation_trainer.py
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

# Import the class to test
from agents.agents.conversation_trainer import ConversationTrainer


class TestConversationTrainer:
    """Test ConversationTrainer agent"""

    def test_init(self):
        """Test: ConversationTrainer initializes with settings"""
        mock_pool = MagicMock()
        trainer = ConversationTrainer(db_pool=mock_pool)

        assert trainer.db_pool == mock_pool

    def test_init_with_zantara_client(self):
        """Test: ConversationTrainer initializes with zantara_client"""
        mock_pool = MagicMock()
        mock_client = MagicMock()
        trainer = ConversationTrainer(db_pool=mock_pool, zantara_client=mock_client)

        assert trainer.db_pool == mock_pool
        assert trainer.zantara_client == mock_client

    @pytest.mark.asyncio
    async def test_get_db_pool_from_instance(self):
        """Test: _get_db_pool returns instance db_pool"""
        mock_pool = MagicMock()
        trainer = ConversationTrainer(db_pool=mock_pool)

        result = await trainer._get_db_pool()

        assert result == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_from_app_state(self):
        """Test: _get_db_pool gets pool from app.state when instance pool is None"""
        mock_pool = MagicMock()
        mock_app = MagicMock()
        mock_app.state.db_pool = mock_pool

        trainer = ConversationTrainer(db_pool=None)

        with patch("app.main_cloud.app", mock_app):
            result = await trainer._get_db_pool()

        assert result == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_error_when_not_available(self):
        """Test: _get_db_pool raises RuntimeError when pool not available"""
        trainer = ConversationTrainer(db_pool=None)

        mock_app = MagicMock()
        mock_app.state.db_pool = None

        with patch("app.main_cloud.app", mock_app):
            with pytest.raises(RuntimeError) as exc_info:
                await trainer._get_db_pool()

        assert "Database pool not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_conversations(self):
        """Test: Returns None when no high-rated conversations found"""
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

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_invalid_days_back(self):
        """Test: analyze_winning_patterns corrects invalid days_back"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        trainer = ConversationTrainer(db_pool=mock_pool)

        # Test days_back < 1
        await trainer.analyze_winning_patterns(days_back=0)
        # Should use default 7, verify by checking query was called
        mock_conn.fetch.assert_called()

        # Reset
        mock_conn.fetch.reset_mock()

        # Test days_back > 365
        await trainer.analyze_winning_patterns(days_back=500)
        # Should use default 7
        mock_conn.fetch.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_messages_as_json_string(self):
        """Test: analyze_winning_patterns parses messages JSON string"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        messages_json = json.dumps([{"role": "user", "content": "Hello"}])
        row = {
            "conversation_id": "conv1",
            "messages": messages_json,
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = None  # Use fallback

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_messages_invalid_json(self):
        """Test: analyze_winning_patterns handles invalid JSON in messages"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        row = {
            "conversation_id": "conv1",
            "messages": "invalid json {",  # Invalid JSON
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = None  # Use fallback

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_messages_not_list(self):
        """Test: analyze_winning_patterns handles messages that are not list"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        row = {
            "conversation_id": "conv1",
            "messages": {"some": "dict"},  # Not a list
            "rating": 5,
            "client_feedback": "Great",
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = None  # Use fallback

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_zantara_client(self):
        """Test: analyze_winning_patterns uses fallback when zantara_client is None"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": "Great",
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = None  # No AI client

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        assert "successful_patterns" in result
        assert "prompt_improvements" in result
        assert "common_themes" in result
        # Should have fallback patterns
        assert len(result["successful_patterns"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_ai_timeout(self):
        """Test: analyze_winning_patterns handles AI timeout"""
        import asyncio

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": "Great",
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await trainer.analyze_winning_patterns(days_back=7, timeout=0.1)

        assert result is not None
        # Should return fallback
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_ai_error(self):
        """Test: analyze_winning_patterns handles AI errors"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": "Great",
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=Exception("AI error"))

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        # Should return fallback
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_json_extraction(self):
        """Test: analyze_winning_patterns extracts JSON from AI response"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": "Great",
            "created_at": datetime.now(),
        }
        mock_conn.fetch.return_value = [row]

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = MagicMock()

        # Response with extra text before/after JSON
        ai_response = (
            "Some text before\n"
            + '{"successful_patterns": ["p1"], "prompt_improvements": ["i1"], "common_themes": ["t1"]}'
            + "\nSome text after"
        )
        trainer.zantara_client.generate_text = AsyncMock(return_value=ai_response)

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        assert result["successful_patterns"] == ["p1"]
        assert result["prompt_improvements"] == ["i1"]
        assert result["common_themes"] == ["t1"]

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_postgres_error(self):
        """Test: analyze_winning_patterns handles PostgresError"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_conn.fetch.side_effect = asyncpg.PostgresError("Database error")

        trainer = ConversationTrainer(db_pool=mock_pool)

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_generic_exception(self):
        """Test: analyze_winning_patterns handles generic exceptions"""
        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("Unexpected error")

        trainer = ConversationTrainer(db_pool=mock_pool)

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_prompt_update_empty_analysis(self):
        """Test: generate_prompt_update returns empty string for empty analysis"""
        trainer = ConversationTrainer()

        result = await trainer.generate_prompt_update({})

        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_prompt_update_no_zantara_client(self):
        """Test: generate_prompt_update uses fallback when zantara_client is None"""
        analysis = {
            "successful_patterns": ["pattern1", "pattern2"],
            "prompt_improvements": ["improvement1"],
            "common_themes": ["theme1"],
        }

        trainer = ConversationTrainer()
        trainer.zantara_client = None

        result = await trainer.generate_prompt_update(analysis)

        assert result != ""
        assert "pattern1" in result or "Successful Patterns" in result
        assert "improvement1" in result or "Prompt Improvements" in result

    @pytest.mark.asyncio
    async def test_generate_prompt_update_with_zantara_client(self):
        """Test: generate_prompt_update uses AI when zantara_client is available"""
        analysis = {
            "successful_patterns": ["pattern1"],
            "prompt_improvements": ["improvement1"],
            "common_themes": ["theme1"],
        }

        trainer = ConversationTrainer()
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(return_value="Improved prompt text")

        result = await trainer.generate_prompt_update(analysis)

        assert result == "Improved prompt text"
        trainer.zantara_client.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_prompt_update_ai_timeout(self):
        """Test: generate_prompt_update handles AI timeout"""
        import asyncio

        analysis = {
            "successful_patterns": ["pattern1"],
            "prompt_improvements": ["improvement1"],
            "common_themes": ["theme1"],
        }

        trainer = ConversationTrainer()
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await trainer.generate_prompt_update(analysis, timeout=0.1)

        # Should return fallback
        assert result != ""
        assert "pattern1" in result or "Successful Patterns" in result

    @pytest.mark.asyncio
    async def test_generate_prompt_update_ai_error(self):
        """Test: generate_prompt_update handles AI errors"""
        analysis = {
            "successful_patterns": ["pattern1"],
            "prompt_improvements": ["improvement1"],
            "common_themes": ["theme1"],
        }

        trainer = ConversationTrainer()
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=Exception("AI error"))

        result = await trainer.generate_prompt_update(analysis)

        # Should return fallback
        assert result != ""
        assert "pattern1" in result or "Successful Patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_many_conversations(self):
        """Test: analyze_winning_patterns limits to ANALYSIS_CONVERSATIONS_LIMIT"""
        from agents.agents.conversation_trainer import ANALYSIS_CONVERSATIONS_LIMIT

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Create more conversations than ANALYSIS_CONVERSATIONS_LIMIT
        rows = []
        for i in range(ANALYSIS_CONVERSATIONS_LIMIT + 5):
            rows.append(
                {
                    "conversation_id": f"conv{i}",
                    "messages": [{"role": "user", "content": f"Message {i}"}],
                    "rating": 5,
                    "client_feedback": None,
                    "created_at": datetime.now(),
                }
            )

        mock_conn.fetch.return_value = rows

        trainer = ConversationTrainer(db_pool=mock_pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(
            return_value='{"successful_patterns": ["p1"], "prompt_improvements": [], "common_themes": []}'
        )

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        # Verify only ANALYSIS_CONVERSATIONS_LIMIT conversations were used
        call_args = trainer.zantara_client.generate_text.call_args
        prompt_text = call_args[1]["prompt"]
        # Should only have ANALYSIS_CONVERSATIONS_LIMIT conversation blocks
        assert prompt_text.count("Rating:") == ANALYSIS_CONVERSATIONS_LIMIT
