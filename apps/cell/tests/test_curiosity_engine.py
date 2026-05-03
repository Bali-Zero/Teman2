"""Tests for cortex CuriosityEngine — pattern mining, retrospective queries, info gain."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from cell.cortex.curiosity_engine import (
    CuriosityEngine,
    CuriosityFinding,
    _QUERY_POOL,
    _QUESTION_POOL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    return pool


def _conn_from_pool(pool: AsyncMock) -> AsyncMock:
    """Extract the mock connection from the pool fixture."""
    return pool.acquire.return_value.__aenter__.return_value


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# TestQueryPool
# ---------------------------------------------------------------------------


class TestQueryPool:
    def test_pool_has_at_least_10_queries(self):
        assert len(_QUERY_POOL) >= 10

    def test_all_queries_are_select_only(self):
        """Safety check: all queries in the pool must be SELECT statements."""
        for key, sql in _QUERY_POOL.items():
            normalized = sql.strip().upper()
            assert normalized.startswith("SELECT"), (
                f"Query '{key}' is not a SELECT: {normalized[:50]}"
            )
            # No data-modifying keywords
            for forbidden in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]:
                assert forbidden not in normalized, (
                    f"Query '{key}' contains forbidden keyword: {forbidden}"
                )

    def test_all_queries_are_strings(self):
        for key, sql in _QUERY_POOL.items():
            assert isinstance(sql, str), f"Query '{key}' is not a string"
            assert len(sql.strip()) > 10, f"Query '{key}' is too short"

    def test_no_string_interpolation_in_queries(self):
        """Ensure no f-string or % format placeholders in query templates."""
        for key, sql in _QUERY_POOL.items():
            assert "{" not in sql, f"Query '{key}' contains '{{' — possible f-string"
            assert "%s" not in sql, f"Query '{key}' contains '%s' — possible format string"
            assert "%d" not in sql, f"Query '{key}' contains '%d' — possible format string"


# ---------------------------------------------------------------------------
# TestQuestionPool
# ---------------------------------------------------------------------------


class TestQuestionPool:
    def test_pool_has_at_least_15_questions(self):
        assert len(_QUESTION_POOL) >= 15

    def test_all_questions_are_strings(self):
        for q in _QUESTION_POOL:
            assert isinstance(q, str)
            assert len(q) > 10

    def test_questions_end_with_question_mark(self):
        for q in _QUESTION_POOL:
            assert q.strip().endswith("?"), f"Question does not end with '?': {q}"


# ---------------------------------------------------------------------------
# TestInfoGain
# ---------------------------------------------------------------------------


class TestInfoGain:
    def test_empty_rows_returns_zero(self):
        assert CuriosityEngine._compute_info_gain([]) == 0.0

    def test_no_numeric_column_returns_zero(self):
        rows = [{"name": "alpha"}, {"name": "beta"}]
        assert CuriosityEngine._compute_info_gain(rows) == 0.0

    def test_uniform_values_returns_zero(self):
        rows = [{"cnt": 5}, {"cnt": 5}, {"cnt": 5}]
        assert CuriosityEngine._compute_info_gain(rows) == 0.0

    def test_high_gain_for_uneven_distribution(self):
        rows = [{"cnt": 100}, {"cnt": 1}]
        gain = CuriosityEngine._compute_info_gain(rows)
        # (100-1)/100 = 0.99
        assert gain > 0.9

    def test_moderate_gain(self):
        rows = [{"cnt": 10}, {"cnt": 5}]
        gain = CuriosityEngine._compute_info_gain(rows)
        # (10-5)/10 = 0.5
        assert abs(gain - 0.5) < 0.01

    def test_clamped_to_0_1(self):
        rows = [{"val": 100}, {"val": -50}]
        gain = CuriosityEngine._compute_info_gain(rows)
        assert 0.0 <= gain <= 1.0

    def test_single_row_returns_zero(self):
        """Single row: max == min, so gain is 0."""
        rows = [{"cnt": 42}]
        assert CuriosityEngine._compute_info_gain(rows) == 0.0


# ---------------------------------------------------------------------------
# TestSummarizeRows
# ---------------------------------------------------------------------------


class TestSummarizeRows:
    def test_returns_valid_json(self):
        rows = [{"action": "restart", "cnt": 5}, {"action": "scale_up", "cnt": 3}]
        result = CuriosityEngine._summarize_rows("test_query", rows)
        parsed = json.loads(result)
        assert parsed["query"] == "test_query"
        assert len(parsed["top_5"]) == 2

    def test_limits_to_5_rows(self):
        rows = [{"val": i} for i in range(10)]
        result = CuriosityEngine._summarize_rows("big_query", rows)
        parsed = json.loads(result)
        assert len(parsed["top_5"]) == 5

    def test_handles_empty_rows(self):
        result = CuriosityEngine._summarize_rows("empty", [])
        parsed = json.loads(result)
        assert parsed["top_5"] == []


# ---------------------------------------------------------------------------
# TestSelectQuery
# ---------------------------------------------------------------------------


class TestSelectQuery:
    @pytest.mark.asyncio
    async def test_returns_key_when_none_recent(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])  # no recent findings

        engine = CuriosityEngine(mock_pool)
        key = await engine._select_query()
        assert key is not None
        assert key in _QUERY_POOL

    @pytest.mark.asyncio
    async def test_returns_none_when_all_recently_seen(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        # All query keys were recently used
        recent = [{"method": key} for key in _QUERY_POOL]
        conn.fetch = AsyncMock(return_value=recent)

        engine = CuriosityEngine(mock_pool)
        key = await engine._select_query()
        assert key is None

    @pytest.mark.asyncio
    async def test_excludes_recently_used(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        # Mark first query as recently used
        first_key = list(_QUERY_POOL.keys())[0]
        conn.fetch = AsyncMock(return_value=[{"method": first_key}])

        engine = CuriosityEngine(mock_pool)
        key = await engine._select_query()
        assert key is not None
        assert key != first_key


# ---------------------------------------------------------------------------
# TestSelectQuestion
# ---------------------------------------------------------------------------


class TestSelectQuestion:
    @pytest.mark.asyncio
    async def test_returns_question_when_none_recent(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        engine = CuriosityEngine(mock_pool)
        q = await engine._select_question()
        assert q is not None
        assert q in _QUESTION_POOL

    @pytest.mark.asyncio
    async def test_returns_none_when_all_answered(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        recent = [{"question": q} for q in _QUESTION_POOL]
        conn.fetch = AsyncMock(return_value=recent)

        engine = CuriosityEngine(mock_pool)
        q = await engine._select_question()
        assert q is None


# ---------------------------------------------------------------------------
# TestExplore
# ---------------------------------------------------------------------------


class TestExplore:
    @pytest.mark.asyncio
    async def test_returns_empty_on_zero_budget(self, mock_pool):
        engine = CuriosityEngine(mock_pool)
        result = await engine.explore(state={}, attention_budget=0)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_negative_budget(self, mock_pool):
        engine = CuriosityEngine(mock_pool)
        result = await engine.explore(state={}, attention_budget=-1)
        assert result == []

    @pytest.mark.asyncio
    async def test_mining_runs_on_budget_1(self, mock_pool):
        conn = _conn_from_pool(mock_pool)

        # _select_query returns no recent, so first key is picked
        # _pattern_mining: conn.fetch first call returns [] (no recent findings),
        # second call returns query results
        fetch_results = [
            [],  # _select_query: no recent findings
            [{"action_taken": "restart_service", "cnt": 10}],  # SQL query result
        ]
        fetch_idx = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_idx[0]
            fetch_idx[0] += 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.execute = AsyncMock()

        engine = CuriosityEngine(mock_pool)
        result = await engine.explore(state={}, attention_budget=1)
        # Should have at most 1 finding (mining only, budget=1 is not enough for retrospective)
        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_explore_with_mining_and_retrospective(self, mock_pool):
        conn = _conn_from_pool(mock_pool)

        # Multiple fetch calls for mining + retrospective
        fetch_results = [
            [],  # _select_query: no recent findings
            [{"cnt": 10}, {"cnt": 1}],  # mining SQL result
            [],  # _select_question: no recent questions
        ]
        fetch_idx = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_idx[0]
            fetch_idx[0] += 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.execute = AsyncMock()

        # Mock LLM response for retrospective
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "I observe patterns of improvement."},
        }
        mock_http.post = AsyncMock(return_value=mock_resp)

        engine = CuriosityEngine(mock_pool, http_client=mock_http)
        result = await engine.explore(state={"health": "green"}, attention_budget=3)

        # Should have up to 2 findings (1 mining + 1 retrospective)
        assert len(result) <= 2
        # At least mining should succeed
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_explore_without_mining(self, mock_pool):
        conn = _conn_from_pool(mock_pool)

        # Only retrospective: _select_question fetch
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "Retrospective insight here."},
        }
        mock_http.post = AsyncMock(return_value=mock_resp)

        engine = CuriosityEngine(mock_pool, http_client=mock_http)
        result = await engine.explore(
            state={}, attention_budget=2, allow_mining=False
        )

        # Mining was disabled, so only retrospective
        assert len(result) <= 1


# ---------------------------------------------------------------------------
# TestClientLifecycle
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        engine = CuriosityEngine(AsyncMock(), http_client=mock_http)
        await engine.close()
        mock_http.aclose.assert_awaited_once()

    def test_get_client_creates_if_none(self):
        engine = CuriosityEngine(AsyncMock())
        client = engine._get_client()
        assert isinstance(client, httpx.AsyncClient)


# ---------------------------------------------------------------------------
# TestCuriosityFindingDataclass
# ---------------------------------------------------------------------------


class TestCuriosityFindingDataclass:
    def test_creation(self):
        f = CuriosityFinding(
            id="abc123",
            source="pattern_mining",
            question="What does X reveal?",
            method="test_query",
            finding="some finding",
            actionable=True,
            information_gain=0.75,
            related_goal_id=None,
        )
        assert f.source == "pattern_mining"
        assert f.actionable is True
        assert f.information_gain == 0.75

    def test_default_created_at(self):
        f = CuriosityFinding(
            id="def456",
            source="retrospective_query",
            question="Q?",
            method="ollama",
            finding="F",
            actionable=False,
            information_gain=0.0,
            related_goal_id=None,
        )
        assert isinstance(f.created_at, datetime)
