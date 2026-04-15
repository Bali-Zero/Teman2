"""Tests for Deep Research Dispatcher — background research queue.

# Organo: backend-rag/rag → produce research job → consuma da worker + API
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from backend.services.rag.deep_research_dispatcher import (
    QUEUE_KEY,
    RESULT_PREFIX,
    DeepResearchDispatcher,
    ResearchJob,
)


class TestDeepResearchDispatcher:
    """Deep Research Dispatcher queues background research jobs."""

    def setup_method(self) -> None:
        self.mock_redis = AsyncMock()
        self.dispatcher = DeepResearchDispatcher(redis_client=self.mock_redis)

    # ── Dispatch ──

    @pytest.mark.asyncio
    async def test_dispatch_returns_job_id(self) -> None:
        job_id = await self.dispatcher.dispatch("What is KITAS?", domain="visa")

        assert job_id is not None
        assert len(job_id) == 36  # UUID format
        self.mock_redis.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_stores_pending_status(self) -> None:
        job_id = await self.dispatcher.dispatch("test query")

        # Check that initial status is stored
        self.mock_redis.set.assert_called_once()
        call_args = self.mock_redis.set.call_args
        stored = json.loads(call_args[0][1])
        assert stored["status"] == "pending"
        assert stored["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_dispatch_pushes_to_queue(self) -> None:
        await self.dispatcher.dispatch("test query", domain="visa", context={"key": "val"})

        call_args = self.mock_redis.rpush.call_args
        assert call_args[0][0] == QUEUE_KEY
        payload = json.loads(call_args[0][1])
        assert payload["query"] == "test query"
        assert payload["domain"] == "visa"
        assert payload["context"] == {"key": "val"}

    @pytest.mark.asyncio
    async def test_dispatch_no_redis_returns_none(self) -> None:
        dispatcher = DeepResearchDispatcher()
        result = await dispatcher.dispatch("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_redis_failure_returns_none(self) -> None:
        self.mock_redis.rpush.side_effect = Exception("Redis down")
        result = await self.dispatcher.dispatch("test")
        assert result is None

    # ── Check result ──

    @pytest.mark.asyncio
    async def test_check_pending_result(self) -> None:
        self.mock_redis.get.return_value = json.dumps({
            "status": "pending", "job_id": "abc-123"
        })

        result = await self.dispatcher.check_result("abc-123")

        assert result is not None
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_check_completed_result(self) -> None:
        self.mock_redis.get.return_value = json.dumps({
            "status": "completed",
            "job_id": "abc-123",
            "result": "Detailed research findings about KITAS...",
        })

        result = await self.dispatcher.check_result("abc-123")

        assert result is not None
        assert result["status"] == "completed"
        assert "KITAS" in result["result"]

    @pytest.mark.asyncio
    async def test_check_nonexistent_result(self) -> None:
        self.mock_redis.get.return_value = None
        result = await self.dispatcher.check_result("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_no_redis_returns_none(self) -> None:
        dispatcher = DeepResearchDispatcher()
        result = await dispatcher.check_result("abc-123")
        assert result is None

    # ── Complete job ──

    @pytest.mark.asyncio
    async def test_complete_job_stores_result(self) -> None:
        success = await self.dispatcher.complete_job(
            "abc-123", "Research complete: KITAS requires RPTKA"
        )

        assert success is True
        call_args = self.mock_redis.set.call_args
        stored = json.loads(call_args[0][1])
        assert stored["status"] == "completed"
        assert "RPTKA" in stored["result"]

    @pytest.mark.asyncio
    async def test_complete_job_failure_status(self) -> None:
        success = await self.dispatcher.complete_job(
            "abc-123", "Error occurred", status="failed"
        )

        assert success is True
        stored = json.loads(self.mock_redis.set.call_args[0][1])
        assert stored["status"] == "failed"

    # ── Queue stats ──

    @pytest.mark.asyncio
    async def test_pending_count(self) -> None:
        self.mock_redis.llen.return_value = 5
        count = await self.dispatcher.pending_count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_pending_count_no_redis(self) -> None:
        dispatcher = DeepResearchDispatcher()
        count = await dispatcher.pending_count()
        assert count == 0

    # ── ResearchJob dataclass ──

    def test_research_job_generates_uuid(self) -> None:
        job = ResearchJob(query="test")
        assert len(job.job_id) == 36
        assert job.status == "pending"

    def test_research_job_custom_id(self) -> None:
        job = ResearchJob(job_id="custom-id", query="test")
        assert job.job_id == "custom-id"
