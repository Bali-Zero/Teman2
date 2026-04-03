# apps/cell/tests/test_dreamer.py
"""Tests for Dreamer nocturnal consolidation."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from cell.memory.dreamer import Dreamer, DreamResult


class TestDreamResult:
    def test_dataclass_fields(self):
        dr = DreamResult(
            dream_date=date(2026, 4, 3),
            episodes_count=5,
            rules_extracted=["When RT > 2000ms after yellow, restart_service"],
            merged_count=1,
            gaps_identified=["Never seen Qdrant red — unclear what to do"],
            summary="Quiet day with one restart.",
        )
        assert dr.episodes_count == 5
        assert len(dr.rules_extracted) == 1
        assert len(dr.gaps_identified) == 1


class TestDreamerFetchEpisodes:
    @pytest.fixture
    def pool_with_episodes(self):
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red", "response_time_ms": 3000}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart worked when RT > 3000ms",
                "recall_count": 2,
            },
            {
                "id": 2, "timestamp": 1743710000.0,
                "situation": json.dumps({"health_status": "yellow", "response_time_ms": 1200}),
                "emotion": "alert", "action_taken": "observe",
                "outcome": "partial", "lesson": "Yellow resolved on its own",
                "recall_count": 0,
            },
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.mark.asyncio
    async def test_fetch_todays_episodes(self, pool_with_episodes):
        db_pool, conn = pool_with_episodes
        dreamer = Dreamer(pool=db_pool, ollama_url="http://localhost:11434")
        episodes = await dreamer._fetch_todays_episodes()
        assert len(episodes) == 2
        assert episodes[0]["action_taken"] == "restart_service"


class TestDreamerRun:
    @pytest.fixture
    def pool_empty(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool

    @pytest.mark.asyncio
    async def test_dream_no_episodes_returns_empty_result(self, pool_empty):
        dreamer = Dreamer(pool=pool_empty, ollama_url="http://localhost:11434")
        result = await dreamer.dream()
        assert result is not None
        assert result.episodes_count == 0
        assert result.rules_extracted == []
        assert result.gaps_identified == []

    @pytest.mark.asyncio
    async def test_dream_with_episodes_calls_llm(self):
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red"}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart fixed it",
                "recall_count": 1,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")

        with patch.object(dreamer, "_extract_rules_with_llm", new_callable=AsyncMock) as mock_rules:
            mock_rules.return_value = (
                ["When RED + restart -> success, trust restart for future RED"],
                ["Have not seen Qdrant failure yet"]
            )
            result = await dreamer.dream()

        assert result.episodes_count == 1
        assert len(result.rules_extracted) == 1
        assert len(result.gaps_identified) == 1

    @pytest.mark.asyncio
    async def test_dream_llm_failure_still_returns_result(self):
        """When LLM fails, dream() returns result with empty rules/gaps (graceful degradation)."""
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "yellow"}),
                "emotion": "alert", "action_taken": "observe",
                "outcome": "partial", "lesson": "Watched and waited",
                "recall_count": 0,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")

        with patch.object(dreamer, "_extract_rules_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = ([], [])  # LLM returned nothing
            result = await dreamer.dream()

        assert result.episodes_count == 1
        assert result.rules_extracted == []
        assert result.gaps_identified == []
        assert "episode" in result.summary.lower() or "rule" in result.summary.lower()
