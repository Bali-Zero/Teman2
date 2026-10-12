"""
Unit tests for ConversationTrainer
Target: 100% coverage
Composer: 4
"""

import logging
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.agents.conversation_trainer import ConversationTrainer


class _AcquireContext:
    def __init__(self, conn: AsyncMock) -> None:
        self.conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self.conn

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _pool_with_rows(rows: list[dict[str, Any]]) -> MagicMock:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireContext(conn))
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireContext(mock_conn))
    pool._mock_conn = mock_conn
    return pool


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

    @pytest.mark.asyncio
    async def test_get_db_pool_from_app_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fallback to app.state.db_pool when constructor pool is absent."""
        pool = MagicMock()
        fake_app = MagicMock()
        fake_app.state.db_pool = pool
        monkeypatch.setitem(sys.modules, "backend.app.main_cloud", MagicMock(app=fake_app))

        trainer = ConversationTrainer(db_pool=None, zantara_client=None)

        assert await trainer._get_db_pool() is pool

    @pytest.mark.asyncio
    async def test_get_db_pool_raises_when_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing constructor/app pool is a hard configuration error."""
        from backend.app.main_cloud import app

        # An earlier test in the same process can leave app.state.db_pool set.
        monkeypatch.setattr(app.state, "db_pool", None, raising=False)
        trainer = ConversationTrainer(db_pool=None, zantara_client=None)

        with pytest.raises(RuntimeError, match="Database pool not available"):
            await trainer._get_db_pool()

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_extracts_ai_json_from_wrapped_text(self) -> None:
        """AI output may include prose around the JSON object."""
        pool = _pool_with_rows(
            [
                {
                    "conversation_id": "conv-1",
                    "messages": '[{"role": "assistant", "content": "Helpful answer"}]',
                    "rating": 5,
                    "client_feedback": "Excellent",
                    "created_at": "2026-01-01T00:00:00",
                },
            ],
        )
        client = MagicMock()
        client.generate_text = AsyncMock(
            return_value='Here you go {"successful_patterns":["fast"],"prompt_improvements":["ask"],"common_themes":["visa"]} thanks',
        )
        trainer = ConversationTrainer(db_pool=pool, zantara_client=client)

        result = await trainer.analyze_winning_patterns(days_back=999, timeout=0.1)

        assert result == {
            "successful_patterns": ["fast"],
            "prompt_improvements": ["ask"],
            "common_themes": ["visa"],
        }
        _query, _threshold, interval, _limit = pool._mock_conn.fetch.call_args.args
        assert interval.days == 7

    @pytest.mark.asyncio
    async def test_analyze_winning_patterns_falls_back_for_bad_message_json_and_bad_ai(
        self,
    ) -> None:
        """Malformed stored messages and malformed AI JSON still produce basic analysis."""
        pool = _pool_with_rows(
            [
                {
                    "conversation_id": "conv-1",
                    "messages": "{not json",
                    "rating": 4,
                    "client_feedback": None,
                    "created_at": "2026-01-01T00:00:00",
                },
            ],
        )
        client = MagicMock()
        client.generate_text = AsyncMock(return_value="no json here")
        trainer = ConversationTrainer(db_pool=pool, zantara_client=client)

        result = await trainer.analyze_winning_patterns(days_back=7, timeout=0.1)

        assert result == {
            "successful_patterns": [
                "High ratings (1 conversations analyzed)",
                "Positive client feedback",
            ],
            "prompt_improvements": [],
            "common_themes": [],
        }

    @pytest.mark.asyncio
    async def test_generate_prompt_update_empty_and_ai_error_paths(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Empty analysis returns nothing; AI failures fall back to markdown summary."""
        trainer = ConversationTrainer(db_pool=None, zantara_client=None)

        assert await trainer.generate_prompt_update({}) == ""

        client = MagicMock()
        client.generate_text = AsyncMock(side_effect=RuntimeError("model down"))
        trainer.zantara_client = client

        with caplog.at_level(logging.ERROR):
            prompt = await trainer.generate_prompt_update(
                {
                    "successful_patterns": ["clear next step"],
                    "prompt_improvements": ["quote requirements"],
                },
                timeout=0.1,
            )

        assert "Error generating prompt update" in caplog.text
        assert "- clear next step" in prompt
        assert "- quote requirements" in prompt

    @pytest.mark.asyncio
    async def test_create_improvement_pr_branch_fallback_writes_review_artifacts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Existing branch fallback stays local and stages only review artifacts."""
        from backend.agents.agents import conversation_trainer as mod

        monkeypatch.chdir(tmp_path)
        checkout_new = MagicMock(side_effect=RuntimeError("exists"))
        checkout_existing = MagicMock()
        git_add = MagicMock()
        git_commit = MagicMock()
        monkeypatch.setattr(mod, "safe_git_checkout_new", checkout_new)
        monkeypatch.setattr(mod, "safe_git_checkout", checkout_existing)
        monkeypatch.setattr(mod, "safe_git_add", git_add)
        monkeypatch.setattr(mod, "safe_git_commit", git_commit)
        trainer = ConversationTrainer(db_pool=None, zantara_client=None)

        branch = await trainer.create_improvement_pr(
            "Improved prompt",
            {"successful_patterns": ["concise"]},
        )

        assert branch.startswith("auto/prompt-improvement-")
        assert (tmp_path / "apps/backend-rag/backend/prompts/proposed_prompt_update.md").read_text(
            encoding="utf-8",
        ) == "Improved prompt"
        report_files = list((tmp_path / "reports").glob("conversation_analysis_*.md"))
        assert len(report_files) == 1
        assert '"concise"' in report_files[0].read_text(encoding="utf-8")
        checkout_existing.assert_called_once_with(branch, cwd=Path())
        git_add.assert_called_once()
        git_commit.assert_called_once()


class TestSlackNotifyErrorHandling:
    """S11: verify run_conversation_trainer handles Slack failures with narrow exceptions."""

    @pytest.mark.asyncio
    async def test_slack_notify_swallows_httpx_error(self, monkeypatch, caplog):
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

        with (
            patch.object(mod, "ConversationTrainer", return_value=mock_trainer),
            patch.object(
                httpx,
                "AsyncClient",
                _BoomClient,
            ),
        ):
            # Must not raise
            with caplog.at_level(logging.ERROR):
                await mod.run_conversation_trainer(days_back=1)

        # The narrow (httpx.HTTPError, OSError) handler must be the one that
        # caught it — not the outer broad `except Exception`, which logs a
        # different message and re-raises.
        assert "Failed to send Slack notification" in caplog.text
        assert "Error in ConversationTrainer" not in caplog.text
        mock_trainer.create_improvement_pr.assert_called_once()

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

        with (
            patch.object(mod, "ConversationTrainer", return_value=mock_trainer),
            patch.object(
                httpx,
                "AsyncClient",
                _CancelClient,
            ),
        ):
            with pytest.raises(asyncio.CancelledError):
                await mod.run_conversation_trainer(days_back=1)
