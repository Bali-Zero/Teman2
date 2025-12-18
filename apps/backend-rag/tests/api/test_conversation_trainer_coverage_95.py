"""
API Tests for ConversationTrainer - Coverage 95% Target
Tests ConversationTrainer via API endpoints

Coverage:
- POST /api/autonomous-agents/conversation-trainer/run
- analyze_winning_patterns method
- generate_prompt_update method
- create_improvement_pr method
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
# GitHub token removed - platform agnostic
# os.environ.setdefault("GITHUB_TOKEN", "test_github_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestConversationTrainerAPI:
    """Test ConversationTrainer via API endpoints"""

    @pytest.mark.asyncio
    async def test_run_conversation_trainer_endpoint(self, authenticated_client):
        """Test POST /api/autonomous-agents/conversation-trainer/run endpoint"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=7"
        )

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "agent_name" in data
        assert data["agent_name"] == "conversation_trainer"
        assert "status" in data
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_run_conversation_trainer_days_back_validation(self, authenticated_client):
        """Test days_back parameter validation"""
        # Test with invalid days_back (too low)
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=0"
        )

        assert response.status_code == 422  # Validation error

        # Test with invalid days_back (too high)
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=400"
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_success(self):
        """Test analyze_winning_patterns with successful analysis"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire = AsyncMock(return_value=mock_cm)

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "conversation_id": "conv1",
                "messages": '[{"role": "user", "content": "test"}]',
                "rating": 5,
                "client_feedback": "Great!",
                "created_at": "2024-01-01",
            }.get(k)
        )

        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        mock_zantara = MagicMock()
        mock_zantara.generate_text = AsyncMock(
            return_value='{"successful_patterns": ["pattern1"], "prompt_improvements": ["improve1"], "common_themes": ["theme1"]}'
        )

        trainer = ConversationTrainer(db_pool=mock_pool, zantara_client=mock_zantara)

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is not None
        assert "successful_patterns" in result
        assert "prompt_improvements" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_conversations(self):
        """Test analyze_winning_patterns with no conversations found"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire = AsyncMock(return_value=mock_cm)

        mock_conn.fetch = AsyncMock(return_value=[])

        trainer = ConversationTrainer(db_pool=mock_pool)

        result = await trainer.analyze_winning_patterns(days_back=7)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_invalid_days(self):
        """Test analyze_winning_patterns with invalid days_back"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        trainer = ConversationTrainer()

        # Should use default 7 for invalid values
        result = await trainer.analyze_winning_patterns(days_back=0)

        # Should handle gracefully
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_json_messages(self):
        """Test analyze_winning_patterns with JSON string messages"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire = AsyncMock(return_value=mock_cm)

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "conversation_id": "conv1",
                "messages": '[{"role": "user", "content": "test"}]',
                "rating": 5,
                "client_feedback": None,
                "created_at": "2024-01-01",
            }.get(k)
        )

        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        trainer = ConversationTrainer(db_pool=mock_pool)

        result = await trainer.analyze_winning_patterns(days_back=7)

        # Should return fallback analysis
        assert result is not None
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_generate_prompt_update_success(self):
        """Test generate_prompt_update with successful generation"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        analysis = {
            "successful_patterns": ["pattern1"],
            "prompt_improvements": ["improve1"],
            "common_themes": ["theme1"],
        }

        mock_zantara = MagicMock()
        mock_zantara.generate_text = AsyncMock(return_value="Improved prompt text")

        trainer = ConversationTrainer(zantara_client=mock_zantara)

        result = await trainer.generate_prompt_update(analysis)

        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_prompt_update_empty_analysis(self):
        """Test generate_prompt_update with empty analysis"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        trainer = ConversationTrainer()

        result = await trainer.generate_prompt_update({})

        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_prompt_update_no_client(self):
        """Test generate_prompt_update without zantara_client"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        analysis = {
            "successful_patterns": ["pattern1"],
            "prompt_improvements": ["improve1"],
        }

        trainer = ConversationTrainer(zantara_client=None)

        result = await trainer.generate_prompt_update(analysis)

        # Should return fallback summary
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_improvement_pr_success(self):
        """Test create_improvement_pr with successful PR creation"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        improved_prompt = "New improved prompt"
        analysis = {"successful_patterns": ["pattern1"]}

        with patch("backend.agents.agents.conversation_trainer.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)

            trainer = ConversationTrainer()
            # GitHub token removed - platform agnostic
            # trainer.github_token = "test_token"

            result = await trainer.create_improvement_pr(improved_prompt, analysis)

            assert result is not None
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_create_improvement_pr_no_token(self):
        """Test create_improvement_pr (platform agnostic)"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        improved_prompt = "New improved prompt"
        analysis = {"successful_patterns": ["pattern1"]}

        trainer = ConversationTrainer()
        # GitHub token removed - platform agnostic
        # trainer.github_token = None

        result = await trainer.create_improvement_pr(improved_prompt, analysis)

        # Should return None or handle gracefully
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_db_pool_from_instance(self):
        """Test _get_db_pool returns instance pool"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        mock_pool = MagicMock()
        trainer = ConversationTrainer(db_pool=mock_pool)

        result = await trainer._get_db_pool()

        assert result == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_from_app_state(self):
        """Test _get_db_pool gets pool from app.state"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        mock_pool = MagicMock()

        with patch("backend.agents.agents.conversation_trainer.app") as mock_app:
            mock_app.state.db_pool = mock_pool

            trainer = ConversationTrainer(db_pool=None)

            result = await trainer._get_db_pool()

            assert result == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_error(self):
        """Test _get_db_pool raises error when pool not available"""
        from backend.agents.agents.conversation_trainer import ConversationTrainer

        with patch("backend.agents.agents.conversation_trainer.app") as mock_app:
            mock_app.state.db_pool = None

            trainer = ConversationTrainer(db_pool=None)

            with pytest.raises(RuntimeError):
                await trainer._get_db_pool()
