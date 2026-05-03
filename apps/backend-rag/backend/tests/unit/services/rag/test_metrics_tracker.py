"""Tests for backend.services.rag.evaluation.metrics_tracker"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from backend.services.rag.evaluation.metrics_tracker import (
    MetricsTracker,
    QueryMetric,
)


def _make_pool(mock_conn):
    """Create a mock pool that works with `async with pool.acquire() as conn:`."""
    mock_pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = ctx
    # conn.transaction() must return a sync context manager (not coroutine)
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)
    return mock_pool


@pytest.fixture
def mock_conn():
    return AsyncMock()


@pytest.fixture
def mock_pool(mock_conn):
    return _make_pool(mock_conn)


@pytest.fixture
def tracker(mock_pool):
    t = MetricsTracker(pool=mock_pool)
    t._initialized = True
    return t


# ── QueryMetric ─────────────────────────────────────────────────────────────


class TestQueryMetric:
    def test_to_dict(self):
        qm = QueryMetric(
            query_id="q1",
            user_id="u1",
            experiment="exp1",
            variant="A",
            metric="ctr",
            value=1.0,
            metadata={"source": "web"},
        )
        d = qm.to_dict()
        assert d["query_id"] == "q1"
        assert d["experiment"] == "exp1"
        assert json.loads(d["metadata"]) == {"source": "web"}

    def test_to_dict_no_metadata(self):
        qm = QueryMetric(
            query_id="q1", user_id="u1",
            experiment="exp1", variant="A",
            metric="ctr", value=1.0,
        )
        d = qm.to_dict()
        assert d["metadata"] is None


# ── MetricsTracker._get_pool ───────────────────────────────────────────────


class TestGetPool:
    @pytest.mark.asyncio
    async def test_returns_existing_pool(self, tracker, mock_pool):
        result = await tracker._get_pool()
        assert result is mock_pool

    @pytest.mark.asyncio
    async def test_creates_pool_if_none(self):
        tracker = MetricsTracker(pool=None)
        mock_pool = MagicMock()
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ):
            result = await tracker._get_pool()
            assert result is mock_pool

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        tracker = MetricsTracker(pool=None)
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            side_effect=Exception("conn fail"),
        ):
            result = await tracker._get_pool()
            assert result is None


# ── initialize ──────────────────────────────────────────────────────────────


class TestInitialize:
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)

        result = await tracker.initialize()
        assert result is True
        assert tracker._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_no_pool(self):
        tracker = MetricsTracker(pool=None)
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            side_effect=Exception("fail"),
        ):
            result = await tracker.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_initialize_sql_error(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("SQL error"))
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)

        result = await tracker.initialize()
        assert result is False


# ── record_metric ───────────────────────────────────────────────────────────


class TestRecordMetric:
    @pytest.mark.asyncio
    async def test_record_success(self, tracker, mock_conn):
        result = await tracker.record_metric(
            experiment="exp1", variant="A", metric="ctr",
            value=1.0, user_id="u1", query_id="q1",
        )
        assert result is True
        assert mock_conn.execute.await_count == 2  # metrics + summary

    @pytest.mark.asyncio
    async def test_record_no_pool(self):
        tracker = MetricsTracker(pool=None)
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            side_effect=Exception("fail"),
        ):
            result = await tracker.record_metric(
                experiment="exp1", variant="A", metric="ctr", value=1.0,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_record_with_metadata(self, tracker):
        result = await tracker.record_metric(
            experiment="exp1", variant="A", metric="ctr",
            value=1.0, metadata={"source": "telegram"},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_record_db_error(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("insert fail"))
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.record_metric(
            experiment="exp1", variant="A", metric="ctr", value=1.0,
        )
        assert result is False


# ── record_query_metrics ────────────────────────────────────────────────────


class TestRecordQueryMetrics:
    @pytest.mark.asyncio
    async def test_record_multiple(self, tracker):
        result = await tracker.record_query_metrics(
            query_id="q1", user_id="u1",
            experiment="exp1", variant="A",
            metrics={"ctr": 1.0, "latency": 200.0},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_record_db_error(self):
        mock_conn = AsyncMock()
        pool = _make_pool(mock_conn)
        # Override transaction to raise on enter
        tx = MagicMock()
        tx.__aenter__ = AsyncMock(side_effect=Exception("fail"))
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.record_query_metrics(
            query_id="q1", user_id="u1",
            experiment="exp1", variant="A",
            metrics={"ctr": 1.0},
        )
        assert result is False


# ── get_experiment_aggregates ───────────────────────────────────────────────


class TestGetExperimentAggregates:
    @pytest.mark.asyncio
    async def test_returns_empty_no_pool(self):
        tracker = MetricsTracker(pool=None)
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            side_effect=Exception("fail"),
        ):
            result = await tracker.get_experiment_aggregates("exp1")
            assert result == {}

    @pytest.mark.asyncio
    async def test_returns_aggregates(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [
                {"variant": "A", "metric": "ctr", "count": 10,
                 "sum_values": 8.0, "sum_squares": 7.0,
                 "min_value": 0.0, "max_value": 1.0},
            ],
            [
                {"metric": "ctr", "value": 0.8},
                {"metric": "ctr", "value": 1.0},
            ],
        ])
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.get_experiment_aggregates("exp1", variants=["A"])
        assert "A" in result
        assert result["A"]["metrics"]["ctr"]["count"] == 10


# ── get_metrics_by_query ────────────────────────────────────────────────────


class TestGetMetricsByQuery:
    @pytest.mark.asyncio
    async def test_returns_metrics(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "query_id": "q1", "user_id": "u1",
                "experiment": "exp1", "variant": "A",
                "metric": "ctr", "value": 1.0,
                "timestamp": datetime.now(timezone.utc),
                "metadata": '{"source": "web"}',
            },
        ])
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.get_metrics_by_query("q1")
        assert len(result) == 1
        assert isinstance(result[0], QueryMetric)

    @pytest.mark.asyncio
    async def test_no_pool(self):
        tracker = MetricsTracker(pool=None)
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            side_effect=Exception("fail"),
        ):
            result = await tracker.get_metrics_by_query("q1")
            assert result == []


# ── get_user_exposure ───────────────────────────────────────────────────────


class TestGetUserExposure:
    @pytest.mark.asyncio
    async def test_with_experiment(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"experiment": "exp1", "variant": "A",
             "first_exposure": datetime.now(timezone.utc), "query_count": 5},
        ])
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.get_user_exposure("u1", experiment="exp1")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_without_experiment(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.get_user_exposure("u1")
        assert result == []


# ── export_experiment_data ──────────────────────────────────────────────────


class TestExportExperimentData:
    @pytest.mark.asyncio
    async def test_export(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "query_id": "q1", "user_id": "u1",
                "experiment": "exp1", "variant": "A",
                "metric": "ctr", "value": 1.0,
                "timestamp": datetime.now(timezone.utc),
                "metadata": None,
            },
        ])
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.export_experiment_data("exp1")
        assert len(result) == 1
        assert result[0]["metadata"] is None


# ── get_active_experiments ──────────────────────────────────────────────────


class TestGetActiveExperiments:
    @pytest.mark.asyncio
    async def test_returns_active(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "experiment": "exp1", "variant": "A",
                "query_count": 50, "unique_users": 10,
                "first_query": datetime.now(timezone.utc),
                "last_query": datetime.now(timezone.utc),
            },
        ])
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.get_active_experiments(hours=24)
        assert len(result) == 1


# ── cleanup_old_metrics ─────────────────────────────────────────────────────


class TestCleanupOldMetrics:
    @pytest.mark.asyncio
    async def test_cleanup(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 42")
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.cleanup_old_metrics(days=90)
        assert result == 42

    @pytest.mark.asyncio
    async def test_cleanup_error(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("delete fail"))
        pool = _make_pool(mock_conn)
        tracker = MetricsTracker(pool=pool)
        tracker._initialized = True

        result = await tracker.cleanup_old_metrics()
        assert result == 0

    @pytest.mark.asyncio
    async def test_cleanup_no_pool(self):
        tracker = MetricsTracker(pool=None)
        with patch(
            "backend.services.rag.evaluation.metrics_tracker.asyncpg.create_pool",
            side_effect=Exception("fail"),
        ):
            result = await tracker.cleanup_old_metrics()
            assert result == 0
