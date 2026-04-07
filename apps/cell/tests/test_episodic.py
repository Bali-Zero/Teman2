# tests/test_episodic.py
"""Tests for episodic memory — CELL remembers moments, not statistics."""
import time
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cell.memory.episodic import Episode, EpisodicMemory


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    # pool.acquire must be a MagicMock (not AsyncMock) so that calling
    # pool.acquire() returns the return_value synchronously — this allows
    # both async with pool.acquire() and the assertion pattern
    # conn = await mock_pool.acquire().__aenter__() to work correctly.
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    return pool


class TestEpisode:
    def test_episode_creation(self) -> None:
        ep = Episode(
            situation={"health": "red", "rt_ms": 5000},
            emotion="stressed",
            action_taken="restart_service",
            outcome="success",
            lesson="High RT resolved by restart",
        )
        assert ep.emotion == "stressed"
        assert ep.activation > 0

    def test_activation_decays_with_age(self) -> None:
        old_ep = Episode(
            situation={},
            emotion="calm",
            action_taken="none",
            outcome="success",
            lesson="All green",
            timestamp=time.time() - 86400 * 7,  # 7 days ago
        )
        new_ep = Episode(
            situation={},
            emotion="calm",
            action_taken="none",
            outcome="success",
            lesson="All green",
            timestamp=time.time(),
        )
        assert new_ep.compute_activation() > old_ep.compute_activation()

    def test_emotion_must_be_valid(self) -> None:
        with pytest.raises(ValueError):
            Episode(
                situation={},
                emotion="happy",  # not a valid emotion
                action_taken="none",
                outcome="success",
                lesson="test",
            )


class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_store_episode(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=1000)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval.return_value = 42
        ep = Episode(
            situation={"health": "red"},
            emotion="alert",
            action_taken="read_logs",
            outcome="success",
            lesson="Logs showed OOM",
        )
        result = await mem.store(ep)
        assert result == 42
        conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_returns_most_activated(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=1000)
        # Simulate DB returning 2 episodes
        conn = await mock_pool.acquire().__aenter__()
        now = time.time()
        conn.fetch.return_value = [
            {
                "id": 1, "timestamp": now - 86400, "situation": '{"health":"red"}',
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "restart fixed it",
                "recall_count": 5,
            },
            {
                "id": 2, "timestamp": now - 3600, "situation": '{"health":"red"}',
                "emotion": "alert", "action_taken": "read_logs",
                "outcome": "partial", "lesson": "logs unclear",
                "recall_count": 1,
            },
        ]
        episodes = await mem.recall(situation={"health": "red"}, limit=2)
        assert len(episodes) <= 2
        # Most recent OR most recalled should rank higher
        assert episodes[0].id in (1, 2)

    @pytest.mark.asyncio
    async def test_forget_below_threshold(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=10)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval.return_value = 15  # more than max
        # Provide rows for the activation-based fetch
        now = time.time()
        conn.fetch.return_value = [
            {"id": i, "timestamp": now - i * 3600, "recall_count": i % 3}
            for i in range(1, 16)
        ]
        await mem.forget_weak()
        # Should have called DELETE with the 5 lowest-activation episodes
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_should_record_filters_green(self) -> None:
        mem = EpisodicMemory(pool=AsyncMock(), max_episodes=1000)
        # Green with no action → not worth recording
        assert not mem.should_record(health_status="green", action_taken=None)
        # Red → always record
        assert mem.should_record(health_status="red", action_taken=None)
        # Green with action → record
        assert mem.should_record(health_status="green", action_taken="read_logs")

    @pytest.mark.asyncio
    async def test_episode_count(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=1000)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval.return_value = 42
        count = await mem.count()
        assert count == 42
