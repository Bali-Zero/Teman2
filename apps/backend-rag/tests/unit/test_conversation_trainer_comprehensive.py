"""
Comprehensive tests for agents/agents/conversation_trainer.py
Target: 99%+ coverage
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Create mock app module before importing conversation_trainer
mock_app_module = MagicMock()
mock_app_module.app = MagicMock()
mock_app_module.app.state = MagicMock()
sys.modules["app.main_cloud"] = mock_app_module

from agents.agents.conversation_trainer import (
    ConversationTrainer,
    run_conversation_trainer,
)


class TestConversationTrainerComprehensive:
    """Comprehensive test suite for ConversationTrainer"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        return pool, conn

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch("app.core.config.settings") as mock:
            # GitHub token removed - platform agnostic
            # mock.github_token = "test_token"
            mock.slack_webhook_url = None
            yield mock

    def test_init_with_db_pool(self, mock_settings):
        """Test initialization with db_pool"""
        mock_pool = MagicMock()
        trainer = ConversationTrainer(db_pool=mock_pool)
        assert trainer.db_pool == mock_pool
        # GitHub token removed - platform agnostic
        # assert trainer.github_token == "test_token"

    def test_init_without_db_pool(self, mock_settings):
        """Test initialization without db_pool"""
        trainer = ConversationTrainer()
        assert trainer.db_pool is None

    def test_init_with_zantara_client(self, mock_settings):
        """Test initialization with zantara_client"""
        mock_client = MagicMock()
        trainer = ConversationTrainer(zantara_client=mock_client)
        assert trainer.zantara_client == mock_client

    @pytest.mark.asyncio
    async def test_get_db_pool_from_instance(self, mock_settings):
        """Test _get_db_pool returns instance pool"""
        mock_pool = MagicMock()
        trainer = ConversationTrainer(db_pool=mock_pool)
        pool = await trainer._get_db_pool()
        assert pool == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_from_app_state(self, mock_settings):
        """Test _get_db_pool gets pool from app.state"""
        mock_pool = MagicMock()
        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.db_pool = mock_pool
            trainer = ConversationTrainer()
            pool = await trainer._get_db_pool()
            assert pool == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_error(self, mock_settings):
        """Test _get_db_pool raises error when no pool available"""
        trainer = ConversationTrainer()
        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.db_pool = None
            with pytest.raises(RuntimeError, match="Database pool not available"):
                await trainer._get_db_pool()

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_invalid_days_back(self, mock_settings, mock_db_pool):
        """Test analyze_winning_patterns with invalid days_back"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        conn.fetch.return_value = []
        result = await trainer.analyze_winning_patterns(days_back=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_too_many_days(self, mock_settings, mock_db_pool):
        """Test analyze_winning_patterns with days_back > 365"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        conn.fetch.return_value = []
        result = await trainer.analyze_winning_patterns(days_back=400)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_with_json_string_messages(
        self, mock_settings, mock_db_pool
    ):
        """Test analyze_winning_patterns with JSON string messages"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(
            return_value='{"successful_patterns": ["p1"], "prompt_improvements": ["i1"], "common_themes": ["t1"]}'
        )

        row = {
            "conversation_id": "conv1",
            "messages": json.dumps([{"role": "user", "content": "Hello"}]),
            "rating": 5,
            "client_feedback": "Great",
            "created_at": datetime.now(),
        }
        conn.fetch.return_value = [row]

        result = await trainer.analyze_winning_patterns()
        assert result is not None
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_with_invalid_json(self, mock_settings, mock_db_pool):
        """Test analyze_winning_patterns with invalid JSON in messages"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(
            return_value='{"successful_patterns": ["p1"], "prompt_improvements": ["i1"], "common_themes": ["t1"]}'
        )

        row = {
            "conversation_id": "conv1",
            "messages": "invalid json {",
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        conn.fetch.return_value = [row]

        result = await trainer.analyze_winning_patterns()
        assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_with_non_list_messages(
        self, mock_settings, mock_db_pool
    ):
        """Test analyze_winning_patterns with non-list messages"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(
            return_value='{"successful_patterns": ["p1"], "prompt_improvements": ["i1"], "common_themes": ["t1"]}'
        )

        row = {
            "conversation_id": "conv1",
            "messages": {"role": "user", "content": "Hello"},
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        conn.fetch.return_value = [row]

        result = await trainer.analyze_winning_patterns()
        assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_ai_timeout(self, mock_settings, mock_db_pool):
        """Test analyze_winning_patterns with AI timeout"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        conn.fetch.return_value = [row]

        result = await trainer.analyze_winning_patterns()
        assert result is not None
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_ai_error(self, mock_settings, mock_db_pool):
        """Test analyze_winning_patterns with AI error"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=Exception("AI error"))

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        conn.fetch.return_value = [row]

        result = await trainer.analyze_winning_patterns()
        assert result is not None
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_zantara_client(self, mock_settings, mock_db_pool):
        """Test analyze_winning_patterns without zantara_client"""
        pool, conn = mock_db_pool
        trainer = ConversationTrainer(db_pool=pool)
        trainer.zantara_client = None

        row = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
            "rating": 5,
            "client_feedback": None,
            "created_at": datetime.now(),
        }
        conn.fetch.return_value = [row]

        result = await trainer.analyze_winning_patterns()
        assert result is not None
        assert "successful_patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_database_error(self, mock_settings):
        """Test analyze_winning_patterns with database error"""
        pool = MagicMock()
        pool.acquire.side_effect = Exception("DB error")
        trainer = ConversationTrainer(db_pool=pool)

        result = await trainer.analyze_winning_patterns()
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_prompt_update_empty_analysis(self, mock_settings):
        """Test generate_prompt_update with empty analysis"""
        trainer = ConversationTrainer()
        result = await trainer.generate_prompt_update({})
        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_prompt_update_with_zantara_client(self, mock_settings):
        """Test generate_prompt_update with zantara_client"""
        trainer = ConversationTrainer()
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(return_value="Improved prompt")

        analysis = {
            "successful_patterns": ["p1"],
            "prompt_improvements": ["i1"],
            "common_themes": ["t1"],
        }
        result = await trainer.generate_prompt_update(analysis)
        assert result == "Improved prompt"

    @pytest.mark.asyncio
    async def test_generate_prompt_update_timeout(self, mock_settings):
        """Test generate_prompt_update with timeout"""
        trainer = ConversationTrainer()
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        analysis = {
            "successful_patterns": ["p1"],
            "prompt_improvements": ["i1"],
        }
        result = await trainer.generate_prompt_update(analysis)
        assert "Improved System Prompt" in result

    @pytest.mark.asyncio
    async def test_generate_prompt_update_error(self, mock_settings):
        """Test generate_prompt_update with error"""
        trainer = ConversationTrainer()
        trainer.zantara_client = MagicMock()
        trainer.zantara_client.generate_text = AsyncMock(side_effect=Exception("Error"))

        analysis = {
            "successful_patterns": ["p1"],
            "prompt_improvements": ["i1"],
        }
        result = await trainer.generate_prompt_update(analysis)
        assert "Improved System Prompt" in result

    @pytest.mark.asyncio
    async def test_generate_prompt_update_no_zantara_client(self, mock_settings):
        """Test generate_prompt_update without zantara_client"""
        trainer = ConversationTrainer()
        trainer.zantara_client = None

        analysis = {
            "successful_patterns": ["p1"],
            "prompt_improvements": ["i1"],
        }
        result = await trainer.generate_prompt_update(analysis)
        assert "Improved System Prompt" in result
        assert "p1" in result

    @pytest.mark.asyncio
    async def test_create_improvement_pr_empty_prompt(self, mock_settings):
        """Test create_improvement_pr with empty prompt"""
        trainer = ConversationTrainer()
        with pytest.raises(ValueError, match="Improved prompt cannot be empty"):
            await trainer.create_improvement_pr("", {})

    @pytest.mark.asyncio
    async def test_create_improvement_pr_success(self, mock_settings):
        """Test create_improvement_pr success"""
        trainer = ConversationTrainer()
        analysis = {"successful_patterns": ["p1"]}

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)
            with patch("pathlib.Path.write_text") as mock_write:
                with patch("pathlib.Path.mkdir"):
                    result = await trainer.create_improvement_pr("Improved prompt", analysis)
                    assert result is not None
                    assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_create_improvement_pr_branch_exists(self, mock_settings):
        """Test create_improvement_pr when branch already exists"""
        trainer = ConversationTrainer()
        analysis = {"successful_patterns": ["p1"]}

        def mock_subprocess_run(*args, **kwargs):
            if args[0][1] == "checkout":
                if args[0][2] == "-b":
                    raise subprocess.CalledProcessError(1, "git")
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            with patch("pathlib.Path.write_text"):
                with patch("pathlib.Path.mkdir"):
                    result = await trainer.create_improvement_pr("Improved prompt", analysis)
                    assert result is not None

    @pytest.mark.asyncio
    async def test_create_improvement_pr_timeout(self, mock_settings):
        """Test create_improvement_pr with timeout"""
        trainer = ConversationTrainer()
        analysis = {"successful_patterns": ["p1"]}

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            with pytest.raises(RuntimeError, match="Timeout creating PR"):
                await trainer.create_improvement_pr("Improved prompt", analysis)

    @pytest.mark.asyncio
    async def test_create_improvement_pr_subprocess_error(self, mock_settings):
        """Test create_improvement_pr with subprocess error"""
        trainer = ConversationTrainer()
        analysis = {"successful_patterns": ["p1"]}

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            with pytest.raises(RuntimeError, match="Failed to create PR"):
                await trainer.create_improvement_pr("Improved prompt", analysis)

    @pytest.mark.asyncio
    async def test_run_conversation_trainer_no_analysis(self, mock_settings):
        """Test run_conversation_trainer with no analysis"""
        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.db_pool = MagicMock()
            trainer = ConversationTrainer(db_pool=mock_app.state.db_pool)
            trainer.analyze_winning_patterns = AsyncMock(return_value=None)

            with patch(
                "agents.agents.conversation_trainer.ConversationTrainer", return_value=trainer
            ):
                await run_conversation_trainer()

    @pytest.mark.asyncio
    async def test_run_conversation_trainer_success(self, mock_settings):
        """Test run_conversation_trainer success"""
        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.db_pool = MagicMock()
            trainer = ConversationTrainer(db_pool=mock_app.state.db_pool)
            trainer.analyze_winning_patterns = AsyncMock(
                return_value={"successful_patterns": ["p1"]}
            )
            trainer.generate_prompt_update = AsyncMock(return_value="Improved prompt")
            trainer.create_improvement_pr = AsyncMock(return_value="branch_name")

            with patch(
                "agents.agents.conversation_trainer.ConversationTrainer", return_value=trainer
            ):
                await run_conversation_trainer()

    @pytest.mark.asyncio
    async def test_run_conversation_trainer_with_slack(self, mock_settings):
        """Test run_conversation_trainer with Slack notification"""
        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.db_pool = MagicMock()
            trainer = ConversationTrainer(db_pool=mock_app.state.db_pool)
            trainer.analyze_winning_patterns = AsyncMock(
                return_value={"successful_patterns": ["p1"]}
            )
            trainer.generate_prompt_update = AsyncMock(return_value="Improved prompt")
            trainer.create_improvement_pr = AsyncMock(return_value="branch_name")

            with patch(
                "agents.agents.conversation_trainer.ConversationTrainer", return_value=trainer
            ):
                mock_settings.slack_webhook_url = "https://slack.com/webhook"
                with patch("httpx.AsyncClient") as mock_client:
                    mock_client.return_value.__aenter__.return_value.post = AsyncMock()
                    await run_conversation_trainer()

    @pytest.mark.asyncio
    async def test_run_conversation_trainer_error(self, mock_settings):
        """Test run_conversation_trainer with error"""
        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.db_pool = MagicMock()
            trainer = ConversationTrainer(db_pool=mock_app.state.db_pool)
            trainer.analyze_winning_patterns = AsyncMock(side_effect=Exception("Error"))

            with patch(
                "agents.agents.conversation_trainer.ConversationTrainer", return_value=trainer
            ):
                with pytest.raises(Exception):
                    await run_conversation_trainer()
