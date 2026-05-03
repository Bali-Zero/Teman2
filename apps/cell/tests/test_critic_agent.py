"""Tests for cortex CriticAgent — expectations, evaluation, weakness detection."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cell.cortex.critic import (
    VALID_EXPECTED_OUTCOMES,
    VALID_HEALTH,
    WEAKNESS_PATTERN_THRESHOLD,
    CriticAgent,
    Critique,
    Expectation,
    _DEFAULT_HEURISTIC,
    _HEURISTIC_EXPECTATIONS,
    _OUTCOME_SCORE,
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
def mock_skill_library() -> MagicMock:
    lib = MagicMock()
    lib.record_use = AsyncMock()
    return lib


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# TestHeuristicsMap
# ---------------------------------------------------------------------------


class TestHeuristicsMap:
    """All 9 allowlisted actions must have heuristic entries."""

    ALLOWLISTED_ACTIONS = [
        "check_health",
        "read_logs",
        "restart_service",
        "scale_up",
        "scale_down",
        "alert_human",
        "alert_silent",
        "ollama_restart",
        "run_backup",
    ]

    def test_all_actions_have_entries(self):
        for action in self.ALLOWLISTED_ACTIONS:
            assert action in _HEURISTIC_EXPECTATIONS, (
                f"Missing heuristic for allowlisted action: {action}"
            )

    def test_all_entries_have_valid_outcome(self):
        for action, entry in _HEURISTIC_EXPECTATIONS.items():
            assert entry["expected_outcome"] in VALID_EXPECTED_OUTCOMES, (
                f"Invalid outcome for {action}: {entry['expected_outcome']}"
            )

    def test_all_entries_have_valid_health(self):
        for action, entry in _HEURISTIC_EXPECTATIONS.items():
            assert entry["expected_health_in_n"] in VALID_HEALTH, (
                f"Invalid health for {action}: {entry['expected_health_in_n']}"
            )

    def test_heuristic_count_matches_allowlist(self):
        assert len(_HEURISTIC_EXPECTATIONS) == len(self.ALLOWLISTED_ACTIONS)

    def test_default_heuristic_has_valid_fields(self):
        assert _DEFAULT_HEURISTIC["expected_outcome"] in VALID_EXPECTED_OUTCOMES
        assert _DEFAULT_HEURISTIC["expected_health_in_n"] in VALID_HEALTH


# ---------------------------------------------------------------------------
# TestRegisterExpectation
# ---------------------------------------------------------------------------


class TestRegisterExpectation:
    @pytest.mark.asyncio
    async def test_skip_none_action(self, mock_pool):
        agent = CriticAgent(mock_pool)
        result = await agent.register_expectation(
            action=None, proposal={"confidence": 0.8}, episode_id=1,
            current_pulse=10,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_none_string_action(self, mock_pool):
        agent = CriticAgent(mock_pool)
        result = await agent.register_expectation(
            action="none", proposal={"confidence": 0.8}, episode_id=1,
            current_pulse=10,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_heuristic_for_known_action(self, mock_pool, now):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})

        agent = CriticAgent(mock_pool)
        result = await agent.register_expectation(
            action="restart_service",
            proposal={"confidence": 0.9, "reason": "high latency"},
            episode_id=5,
            current_pulse=100,
        )

        assert isinstance(result, Expectation)
        assert result.id == 1
        assert result.action == "restart_service"
        assert result.expected_outcome == "success"
        assert result.expected_health_in_n == "green"
        assert result.confidence_at_proposal == 0.9
        assert result.n_pulses_horizon == 5

    @pytest.mark.asyncio
    async def test_heuristic_fallback_for_unknown_action(self, mock_pool, now):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={"id": 2, "created_at": now})

        agent = CriticAgent(mock_pool)
        result = await agent.register_expectation(
            action="unknown_future_action",
            proposal={"confidence": 0.5},
            episode_id=None,
            current_pulse=200,
        )

        assert isinstance(result, Expectation)
        assert result.expected_outcome == "partial"
        assert result.expected_health_in_n == "yellow"

    @pytest.mark.asyncio
    async def test_confidence_from_dataclass_proposal(self, mock_pool, now):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={"id": 3, "created_at": now})

        # Simulate a dataclass-like proposal with .confidence attribute.
        proposal = MagicMock()
        proposal.confidence = 0.77

        agent = CriticAgent(mock_pool)
        result = await agent.register_expectation(
            action="check_health", proposal=proposal,
            episode_id=None, current_pulse=50,
        )

        assert result is not None
        assert result.confidence_at_proposal == 0.77

    @pytest.mark.asyncio
    async def test_llm_parses_json(self, mock_pool, now):
        """When use_llm=True and Ollama responds with valid JSON, use it."""
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={"id": 4, "created_at": now})

        llm_response = json.dumps({
            "expected_outcome": "success",
            "expected_rt_delta_ms": -150,
            "expected_health_in_n": "green",
            "rationale_nl": "restart fixes most latency issues",
        })

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": llm_response},
        }
        mock_http.post = AsyncMock(return_value=mock_resp)

        agent = CriticAgent(mock_pool, http_client=mock_http)
        result = await agent.register_expectation(
            action="restart_service",
            proposal={"confidence": 0.85, "reason": "high latency"},
            episode_id=10,
            current_pulse=300,
            use_llm=True,
        )

        assert result is not None
        assert result.expected_outcome == "success"
        assert result.expected_rt_delta_ms == -150
        assert result.expected_health_in_n == "green"
        assert "restart" in result.rationale_nl

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_heuristics(self, mock_pool, now):
        """When LLM call fails, fall back to heuristics."""
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={"id": 5, "created_at": now})

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("offline"))

        agent = CriticAgent(mock_pool, http_client=mock_http)
        result = await agent.register_expectation(
            action="scale_up",
            proposal={"confidence": 0.7, "reason": "traffic spike"},
            episode_id=None,
            current_pulse=400,
            use_llm=True,
        )

        assert result is not None
        # Should get heuristic values for scale_up.
        assert result.expected_outcome == "success"
        assert result.expected_health_in_n == "green"


# ---------------------------------------------------------------------------
# TestEvaluatePending
# ---------------------------------------------------------------------------


class TestEvaluatePending:
    @pytest.mark.asyncio
    async def test_empty_returns_empty(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        agent = CriticAgent(mock_pool)
        result = await agent.evaluate_pending(current_pulse=100)
        assert result == []

    @pytest.mark.asyncio
    async def test_skips_recent_expectations(self, mock_pool):
        """Expectations whose horizon has NOT elapsed should not be fetched."""
        conn = _conn_from_pool(mock_pool)
        # Return nothing — the SQL WHERE clause filters them out.
        conn.fetch = AsyncMock(return_value=[])

        agent = CriticAgent(mock_pool)
        result = await agent.evaluate_pending(current_pulse=3)
        assert result == []

        # Verify the SQL uses the correct filter.
        call_args = conn.fetch.call_args
        sql = call_args[0][0]
        assert "pulse_number + n_pulses_horizon <= $1" in sql

    @pytest.mark.asyncio
    async def test_computes_miscalibration_correctly(self, mock_pool, now):
        """Full evaluation: expected success, actual failure => miscal 1.0."""
        conn = _conn_from_pool(mock_pool)

        # First fetch: pending expectations.
        exp_row = {
            "id": 10,
            "pulse_number": 50,
            "episode_id": 7,
            "action": "restart_service",
            "skill_id": None,
            "expected_outcome": "success",
            "expected_rt_delta_ms": -200,
            "expected_health_in_n": "green",
            "n_pulses_horizon": 5,
            "confidence_at_proposal": 0.9,
            "rationale_nl": "heuristic default for restart_service",
            "critique_id": None,
            "created_at": now,
        }

        # Pulse log data showing failure (red health).
        pulse_data = [
            {"health_status": "red", "response_time_ms": 500},
            {"health_status": "red", "response_time_ms": 600},
        ]

        # Critique INSERT returns id and created_at.
        crit_return = {"id": 20, "created_at": now}

        # We need multiple conn.fetch calls:
        # 1st: pending expectations
        # 2nd: pulse_log data
        # And multiple conn.fetchrow, conn.fetchval calls.
        fetch_results = [
            [exp_row],    # evaluate_pending: fetch pending expectations
            pulse_data,   # _evaluate_single: fetch pulse_log
        ]
        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.fetchval = AsyncMock(return_value=0)  # failure count = 0
        conn.fetchrow = AsyncMock(return_value=crit_return)
        conn.execute = AsyncMock()

        agent = CriticAgent(mock_pool)
        critiques = await agent.evaluate_pending(current_pulse=60)

        assert len(critiques) == 1
        c = critiques[0]
        assert c.actual_outcome == "failure"
        # success=1.0, failure=0.0 => |1.0-0.0| = 1.0
        assert c.miscalibration == 1.0
        assert c.expectation_id == 10

    @pytest.mark.asyncio
    async def test_success_outcome_when_green_low_rt(self, mock_pool, now):
        """Green health + avg RT < 50 => success."""
        conn = _conn_from_pool(mock_pool)

        exp_row = {
            "id": 11,
            "pulse_number": 20,
            "episode_id": None,
            "action": "check_health",
            "skill_id": None,
            "expected_outcome": "partial",
            "expected_rt_delta_ms": 0,
            "expected_health_in_n": "green",
            "n_pulses_horizon": 5,
            "confidence_at_proposal": 0.6,
            "rationale_nl": "heuristic",
            "critique_id": None,
            "created_at": now,
        }

        pulse_data = [
            {"health_status": "green", "response_time_ms": 30},
            {"health_status": "green", "response_time_ms": 40},
        ]

        crit_return = {"id": 21, "created_at": now}

        fetch_results = [[exp_row], pulse_data]
        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetchrow = AsyncMock(return_value=crit_return)
        conn.execute = AsyncMock()

        agent = CriticAgent(mock_pool)
        critiques = await agent.evaluate_pending(current_pulse=30)

        assert len(critiques) == 1
        c = critiques[0]
        assert c.actual_outcome == "success"
        # partial=0.5, success=1.0 => |0.5-1.0| = 0.5
        assert abs(c.miscalibration - 0.5) < 1e-6

    @pytest.mark.asyncio
    async def test_updates_episode_outcome(self, mock_pool, now):
        """Verify that cell_episodes.outcome is updated."""
        conn = _conn_from_pool(mock_pool)

        exp_row = {
            "id": 12,
            "pulse_number": 10,
            "episode_id": 99,
            "action": "scale_up",
            "skill_id": None,
            "expected_outcome": "success",
            "expected_rt_delta_ms": -100,
            "expected_health_in_n": "green",
            "n_pulses_horizon": 5,
            "confidence_at_proposal": 0.8,
            "rationale_nl": "heuristic",
            "critique_id": None,
            "created_at": now,
        }

        pulse_data = [
            {"health_status": "yellow", "response_time_ms": 100},
        ]

        crit_return = {"id": 22, "created_at": now}

        fetch_results = [[exp_row], pulse_data]
        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetchrow = AsyncMock(return_value=crit_return)
        conn.execute = AsyncMock()

        agent = CriticAgent(mock_pool)
        await agent.evaluate_pending(current_pulse=20)

        # Check that cell_episodes was updated.
        execute_calls = conn.execute.call_args_list
        episode_update_found = False
        for call in execute_calls:
            sql = call[0][0]
            if "UPDATE cell_episodes" in sql and "outcome" in sql:
                episode_update_found = True
                # The episode_id should be 99.
                assert call[0][2] == 99
                break
        assert episode_update_found, "cell_episodes.outcome was not updated"

    @pytest.mark.asyncio
    async def test_calls_skill_library_record_use(self, mock_pool, mock_skill_library, now):
        """When skill_id is set, record_use should be called on the library."""
        conn = _conn_from_pool(mock_pool)

        exp_row = {
            "id": 13,
            "pulse_number": 30,
            "episode_id": None,
            "action": "restart_service",
            "skill_id": 42,
            "expected_outcome": "success",
            "expected_rt_delta_ms": -200,
            "expected_health_in_n": "green",
            "n_pulses_horizon": 5,
            "confidence_at_proposal": 0.9,
            "rationale_nl": "heuristic",
            "critique_id": None,
            "created_at": now,
        }

        pulse_data = [
            {"health_status": "green", "response_time_ms": 20},
        ]

        crit_return = {"id": 23, "created_at": now}

        fetch_results = [[exp_row], pulse_data]
        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx < len(fetch_results):
                return fetch_results[idx]
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetchrow = AsyncMock(return_value=crit_return)
        conn.execute = AsyncMock()

        agent = CriticAgent(mock_pool, skill_library=mock_skill_library)
        critiques = await agent.evaluate_pending(current_pulse=40)

        assert len(critiques) == 1
        mock_skill_library.record_use.assert_awaited_once_with(42, success=True)


# ---------------------------------------------------------------------------
# TestWeaknessDetection
# ---------------------------------------------------------------------------


class TestWeaknessDetection:
    @pytest.mark.asyncio
    async def test_returns_tags(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[
            {"weakness_tag": "repeated_failure_restart_service"},
            {"weakness_tag": "repeated_failure_scale_up"},
        ])

        mock_self_model = MagicMock()

        agent = CriticAgent(mock_pool)
        tags = await agent.detect_weaknesses_for(mock_self_model)

        assert len(tags) == 2
        assert "repeated_failure_restart_service" in tags
        assert "repeated_failure_scale_up" in tags

    @pytest.mark.asyncio
    async def test_pushes_to_self_model(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[
            {"weakness_tag": "repeated_failure_read_logs"},
        ])

        mock_self_model = MagicMock()

        agent = CriticAgent(mock_pool)
        await agent.detect_weaknesses_for(mock_self_model)

        mock_self_model.add_weakness.assert_called_once_with(
            "repeated_failure_read_logs"
        )

    @pytest.mark.asyncio
    async def test_empty_when_no_weaknesses(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        mock_self_model = MagicMock()

        agent = CriticAgent(mock_pool)
        tags = await agent.detect_weaknesses_for(mock_self_model)

        assert tags == []
        mock_self_model.add_weakness.assert_not_called()


# ---------------------------------------------------------------------------
# TestOutcomeScore
# ---------------------------------------------------------------------------


class TestOutcomeScore:
    def test_score_values(self):
        assert _OUTCOME_SCORE["success"] == 1.0
        assert _OUTCOME_SCORE["partial"] == 0.5
        assert _OUTCOME_SCORE["failure"] == 0.0

    def test_all_valid_outcomes_have_scores(self):
        for outcome in VALID_EXPECTED_OUTCOMES:
            assert outcome in _OUTCOME_SCORE


# ---------------------------------------------------------------------------
# TestClientLifecycle
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        agent = CriticAgent(AsyncMock(), http_client=mock_http)
        await agent.close()
        mock_http.aclose.assert_awaited_once()

    def test_get_client_creates_if_none(self):
        agent = CriticAgent(AsyncMock())
        client = agent._get_client()
        assert isinstance(client, httpx.AsyncClient)
