"""Tests for OracleAnalyticsService — focus on the fire-and-forget task protection (S09)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.oracle.analytics import OracleAnalyticsService


class TestQueryHash:
    def test_hash_is_deterministic(self) -> None:
        svc = OracleAnalyticsService()
        assert svc.generate_query_hash("hello") == svc.generate_query_hash("hello")

    def test_different_inputs_produce_different_hashes(self) -> None:
        svc = OracleAnalyticsService()
        assert svc.generate_query_hash("a") != svc.generate_query_hash("b")


class TestStoreQueryAnalyticsFireAndForget:
    @pytest.mark.asyncio
    async def test_schedules_task_and_retains_strong_ref(self) -> None:
        svc = OracleAnalyticsService()
        OracleAnalyticsService._background_tasks.clear()

        # The DB write is slow — we verify the task is tracked while running,
        # and removed from the set after completion.
        async def _slow_store(data: dict) -> None:
            await asyncio.sleep(0.05)

        with patch(
            "backend.services.oracle.analytics.db_manager.store_query_analytics",
            new=AsyncMock(side_effect=_slow_store),
        ):
            await svc.store_query_analytics({"user_id": "u1"})
            # Task tracked while in flight
            assert len(OracleAnalyticsService._background_tasks) == 1
            task = next(iter(OracleAnalyticsService._background_tasks))
            await task
            # Drain the done_callback
            await asyncio.sleep(0)
            assert len(OracleAnalyticsService._background_tasks) == 0

    @pytest.mark.asyncio
    async def test_done_callback_logs_exceptions(self, caplog: pytest.LogCaptureFixture) -> None:
        svc = OracleAnalyticsService()
        OracleAnalyticsService._background_tasks.clear()
        caplog.set_level("ERROR", logger="backend.services.oracle.analytics")

        async def _boom(_: dict) -> None:
            raise RuntimeError("db dead")

        with patch(
            "backend.services.oracle.analytics.db_manager.store_query_analytics",
            new=AsyncMock(side_effect=_boom),
        ):
            await svc.store_query_analytics({})
            task = next(iter(OracleAnalyticsService._background_tasks))
            with contextlib_suppress_runtime_error():
                await task
            await asyncio.sleep(0)

        assert any("Oracle analytics task failed" in r.message for r in caplog.records)
        assert len(OracleAnalyticsService._background_tasks) == 0


def contextlib_suppress_runtime_error():
    """Return a context manager that swallows the task's exception on await."""
    import contextlib

    return contextlib.suppress(RuntimeError)


class TestBuildAnalyticsData:
    def test_builds_expected_keys(self) -> None:
        svc = OracleAnalyticsService()
        out = svc.build_analytics_data(
            query="q",
            answer="a",
            user_profile={"id": "user-1"},
            model_used="gemini-flash",
            execution_time_ms=100.0,
            document_count=3,
            session_id="s1",
            collection_used="bali_zero",
            routing_stats={"evidence_score": 0.42, "verification_status": "ok"},
            search_time_ms=20.0,
            reasoning_time_ms=30.0,
        )
        assert out["user_id"] == "user-1"
        assert out["query_text"] == "q"
        assert out["metadata"]["collection_used"] == "bali_zero"
        assert out["metadata"]["evidence_score"] == 0.42
        assert out["metadata"]["verification_status"] == "ok"

    def test_handles_missing_profile_and_stats(self) -> None:
        svc = OracleAnalyticsService()
        out = svc.build_analytics_data(
            query="q",
            answer="a",
            user_profile=None,
            model_used="m",
            execution_time_ms=1.0,
            document_count=0,
            session_id=None,
            collection_used="c",
            routing_stats={},
            search_time_ms=0.0,
            reasoning_time_ms=0.0,
        )
        assert out["user_id"] is None
        assert out["metadata"]["evidence_score"] == 0.0
        assert out["metadata"]["verification_status"] == "unchecked"
