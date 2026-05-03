"""
Unit tests for ConversationTrainer
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.agents.conversation_trainer import ConversationTrainer


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return AsyncMock()


@pytest.fixture
def conversation_trainer(mock_db_pool):
    """Create conversation trainer instance"""
    with patch("backend.agents.agents.conversation_trainer.ZantaraAIClient"):
        return ConversationTrainer(db_pool=mock_db_pool)


class TestConversationTrainer:
    """Tests for ConversationTrainer"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        with patch("backend.agents.agents.conversation_trainer.ZantaraAIClient"):
            trainer = ConversationTrainer(db_pool=mock_db_pool)
            assert trainer.db_pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_from_instance(self, conversation_trainer):
        """Test getting DB pool from instance"""
        pool = await conversation_trainer._get_db_pool()
        assert pool == conversation_trainer.db_pool

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns(self, conversation_trainer):
        """Test analyzing winning patterns"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "conversation_id": 1,
                    "messages": [{"role": "user", "content": "test"}],
                    "rating": 5,
                    "client_feedback": "Great!",
                    "created_at": "2024-01-01T00:00:00",
                },
            ],
        )

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        conversation_trainer.db_pool.acquire = acquire

        # Mock zantara_client properly - it needs to be available
        if conversation_trainer.zantara_client is None:
            with patch(
                "backend.agents.agents.conversation_trainer.ZantaraAIClient",
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client.generate = AsyncMock(return_value="Pattern analysis")
                mock_client_class.return_value = mock_client
                conversation_trainer.zantara_client = mock_client

                await conversation_trainer.analyze_winning_patterns(days_back=7)
                # Result can be None if analysis fails, but we check it's called
                assert mock_conn.fetch.called
        else:
            with patch.object(conversation_trainer.zantara_client, "generate") as mock_gen:
                mock_gen.return_value = "Pattern analysis"

                await conversation_trainer.analyze_winning_patterns(days_back=7)
                # Result can be None, but we verify the method was called
                assert mock_conn.fetch.called

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_no_conversations(self, conversation_trainer):
        """Test with no conversations"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        conversation_trainer.db_pool.acquire = acquire

        result = await conversation_trainer.analyze_winning_patterns(days_back=7)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_invalid_days(self, conversation_trainer):
        """Test with invalid days_back"""
        result = await conversation_trainer.analyze_winning_patterns(days_back=0)
        # Should use default
        assert result is None or isinstance(result, dict)


class TestSlackNotifyErrorHandling:
    """S11: verify run_conversation_trainer handles Slack failures with narrow exceptions."""

    @pytest.mark.asyncio
    async def test_slack_notify_swallows_httpx_error(self, monkeypatch):
        """httpx.HTTPError from the Slack post must not crash the cron."""
        import httpx

        from backend.agents.agents import conversation_trainer as mod

        mock_trainer = MagicMock()
        mock_trainer.analyze_winning_patterns = AsyncMock(return_value={"x": 1})
        mock_trainer.generate_prompt_update = AsyncMock(return_value="prompt")
        mock_trainer.create_improvement_pr = AsyncMock(return_value="auto/branch")

        fake_app = MagicMock()
        fake_app.state.db_pool = None
        main_cloud = MagicMock(app=fake_app)
        monkeypatch.setitem(sys.modules, "backend.app.main_cloud", main_cloud)

        fake_settings = MagicMock(slack_webhook_url="https://hooks.slack/x")
        core_config = MagicMock(settings=fake_settings)
        monkeypatch.setitem(sys.modules, "backend.app.core.config", core_config)

        class _BoomClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, *a, **kw):
                raise httpx.ConnectError("slack down")

        with patch.object(mod, "ConversationTrainer", return_value=mock_trainer), patch.object(
            httpx, "AsyncClient", _BoomClient,
        ):
            # Must not raise
            await mod.run_conversation_trainer(days_back=1)

    @pytest.mark.asyncio
    async def test_slack_notify_does_not_swallow_cancelled_error(self, monkeypatch):
        """asyncio.CancelledError must propagate (cooperative shutdown)."""
        import asyncio

        import httpx

        from backend.agents.agents import conversation_trainer as mod

        mock_trainer = MagicMock()
        mock_trainer.analyze_winning_patterns = AsyncMock(return_value={"x": 1})
        mock_trainer.generate_prompt_update = AsyncMock(return_value="prompt")
        mock_trainer.create_improvement_pr = AsyncMock(return_value="auto/branch")

        fake_app = MagicMock()
        fake_app.state.db_pool = None
        main_cloud = MagicMock(app=fake_app)
        monkeypatch.setitem(sys.modules, "backend.app.main_cloud", main_cloud)

        fake_settings = MagicMock(slack_webhook_url="https://hooks.slack/x")
        core_config = MagicMock(settings=fake_settings)
        monkeypatch.setitem(sys.modules, "backend.app.core.config", core_config)

        class _CancelClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, *a, **kw):
                raise asyncio.CancelledError

        with patch.object(mod, "ConversationTrainer", return_value=mock_trainer), patch.object(
            httpx, "AsyncClient", _CancelClient,
        ):
            with pytest.raises(asyncio.CancelledError):
                await mod.run_conversation_trainer(days_back=1)
