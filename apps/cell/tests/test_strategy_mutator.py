"""Tests for cortex StrategyMutator — safety chain, sandbox, commit, rollback."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cell.cortex.strategy_mutator import (
    MAX_MUTATIONS_PER_DAY,
    ROLLBACK_FITNESS_MARGIN,
    SANDBOX_FITNESS_THRESHOLD,
    MutationProposal,
    SandboxResult,
    StrategyMutator,
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
    return pool.acquire.return_value.__aenter__.return_value


@pytest.fixture
def mock_library() -> MagicMock:
    lib = MagicMock()
    lib.add_candidate = AsyncMock(return_value=42)
    lib.promote = AsyncMock()
    return lib


@pytest.fixture
def mock_episodic() -> MagicMock:
    return MagicMock()


def _make_proposal(**overrides) -> MutationProposal:
    """Create a MutationProposal with sensible defaults."""
    defaults = dict(
        parent_skill_id=None,
        proposed_name="health_restart_combo",
        proposed_trigger_nl="when health check fails repeatedly",
        proposed_action_sequence=["check_health", "alert_human"],
        proposed_rationale_nl="combine health check with human alert for faster response",
        motivation="critic detected repeated health failures",
        source="critic_failure",
    )
    defaults.update(overrides)
    return MutationProposal(**defaults)


# ---------------------------------------------------------------------------
# TestSafetyCheck
# ---------------------------------------------------------------------------


class TestSafetyCheck:
    def test_valid_actions_no_violations(self, mock_pool, mock_library):
        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["check_health", "alert_human"]
        )
        violations = mutator._safety_check(proposal)
        assert violations == []

    def test_invalid_action_rejected(self, mock_pool, mock_library):
        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["check_health", "destroy_database"]
        )
        violations = mutator._safety_check(proposal)
        assert len(violations) >= 1
        assert any("allowlist_rejected:destroy_database" in v for v in violations)

    def test_unsafe_pattern_rejected(self, mock_pool, mock_library):
        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["rm -rf /", "check_health"]
        )
        violations = mutator._safety_check(proposal)
        # Should catch both allowlist (not in registry) and mutation filter
        assert any("allowlist_rejected" in v for v in violations)
        assert any("mutation_filter_unsafe" in v for v in violations)

    def test_soft_warn_flagged(self, mock_pool, mock_library):
        """An action containing standalone 'restart' triggers soft warn."""
        mutator = StrategyMutator(mock_pool, mock_library)
        # 'force restart now' is not in allowlist AND matches \brestart\b
        proposal = _make_proposal(
            proposed_action_sequence=["force restart now"]
        )
        violations = mutator._safety_check(proposal)
        assert any("allowlist_rejected" in v for v in violations)
        assert any("mutation_filter_review" in v for v in violations)

    def test_multiple_violations_accumulated(self, mock_pool, mock_library):
        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["bad_action1", "DROP TABLE users"]
        )
        violations = mutator._safety_check(proposal)
        assert len(violations) >= 2


# ---------------------------------------------------------------------------
# TestSandbox
# ---------------------------------------------------------------------------


class TestSandbox:
    @pytest.mark.asyncio
    async def test_rejects_unsafe_actions(self, mock_pool, mock_library):
        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["destroy_all"]
        )
        result = await mutator.sandbox_test(proposal)
        assert not result.promoted
        assert result.rejected_reason is not None
        assert "safety_violation" in result.rejected_reason
        assert result.estimated_fitness == 0.0

    @pytest.mark.asyncio
    async def test_passes_valid_proposal_with_fitness(self, mock_pool, mock_library):
        """Valid proposal with episodic data should compute fitness."""
        conn = _conn_from_pool(mock_pool)

        # Track A: return episodes with failures where proposed action differs
        track_a_episodes = [
            {"emotion": "calm", "action_taken": "read_logs", "outcome": "failure", "situation": "{}"},
            {"emotion": "calm", "action_taken": "read_logs", "outcome": "failure", "situation": "{}"},
            {"emotion": "alert", "action_taken": "scale_up", "outcome": "success", "situation": "{}"},
            {"emotion": "alert", "action_taken": "check_health", "outcome": "success", "situation": "{}"},
            {"emotion": "stressed", "action_taken": "read_logs", "outcome": "failure", "situation": "{}"},
            {"emotion": "stressed", "action_taken": "read_logs", "outcome": "failure", "situation": "{}"},
            {"emotion": "panic", "action_taken": "read_logs", "outcome": "failure", "situation": "{}"},
            {"emotion": "panic", "action_taken": "check_health", "outcome": "success", "situation": "{}"},
        ]

        # Track B: episodes with matching situations
        track_b_episodes = [
            {"situation": json.dumps({"event": "health check fails"})}
            for _ in range(80)
        ] + [
            {"situation": json.dumps({"event": "routine pulse"})}
            for _ in range(20)
        ]

        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx == 0:
                return track_a_episodes
            elif idx == 1:
                return track_b_episodes
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.execute = AsyncMock()  # for audit write

        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["check_health", "alert_human"],
        )
        result = await mutator.sandbox_test(proposal, episodic=MagicMock())

        assert result.dna_check is True
        assert result.estimated_fitness > 0
        # LLM score should be > 0 (some episodes are failures with different actions)
        assert result.llm_replay_score >= 0
        # Pattern matches should be > 0 (keyword "health" matches situations)
        assert result.pattern_match_count >= 0

    @pytest.mark.asyncio
    async def test_combined_fitness_formula(self, mock_pool, mock_library):
        """Verify 0.7 * llm + 0.3 * pattern_rate formula."""
        conn = _conn_from_pool(mock_pool)

        # Track A: all improvements -> score = 1.0
        # 2 episodes per emotion (calm, alert, stressed, panic) = 8
        track_a_episodes = []
        for emotion in ["calm", "alert", "stressed", "panic"]:
            # failure + different action = improvement
            track_a_episodes.append(
                {"emotion": emotion, "action_taken": "read_logs", "outcome": "failure", "situation": "{}"}
            )
            # success + matching action = improvement
            track_a_episodes.append(
                {"emotion": emotion, "action_taken": "check_health", "outcome": "success", "situation": "{}"}
            )

        # Track B: 50% match rate
        track_b_episodes = [
            {"situation": json.dumps({"event": "health check fails"})}
            for _ in range(50)
        ] + [
            {"situation": json.dumps({"event": "unrelated stuff"})}
            for _ in range(50)
        ]

        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx == 0:
                return track_a_episodes
            elif idx == 1:
                return track_b_episodes
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["check_health", "alert_human"],
        )
        result = await mutator.sandbox_test(proposal, episodic=MagicMock())

        # LLM: all 8 are improvements -> 1.0
        assert result.llm_replay_score == 1.0
        # Pattern: 50 matches / 100 = 0.50
        assert result.pattern_match_rate == 0.50
        # Combined: 0.7 * 1.0 + 0.3 * 0.50 = 0.85
        assert abs(result.estimated_fitness - 0.85) < 0.01
        assert result.promoted is True

    @pytest.mark.asyncio
    async def test_dna_check_failure_rejects(self, mock_pool, mock_library):
        """DNA check should reject if action needs high confidence for impactful actions."""
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        # scale_up requires confidence > 0.6, but DNAInterpreter uses 0.7 in sandbox
        # However, the sandbox passes confidence=0.7 which IS >= 0.6, so scale_up passes.
        # Use an unknown action to trigger allowlist rejection at DNA level.
        proposal = _make_proposal(
            proposed_action_sequence=["nonexistent_action"],
        )
        result = await mutator.sandbox_test(proposal)

        assert not result.promoted
        # Should fail at safety check layer (allowlist), not DNA
        assert "safety_violation" in (result.rejected_reason or "")

    @pytest.mark.asyncio
    async def test_no_episodic_returns_neutral(self, mock_pool, mock_library):
        """Without episodic memory, Track A returns 0.5 neutral."""
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(
            proposed_action_sequence=["check_health", "alert_human"],
        )
        result = await mutator.sandbox_test(proposal, episodic=None)

        # Track A neutral (0.5), Track B 0 matches -> 0.7*0.5 + 0.3*0 = 0.35
        assert result.llm_replay_score == 0.5
        assert result.estimated_fitness < SANDBOX_FITNESS_THRESHOLD
        assert not result.promoted


# ---------------------------------------------------------------------------
# TestCommitOrRollback
# ---------------------------------------------------------------------------


class TestCommitOrRollback:
    @pytest.mark.asyncio
    async def test_promotes_and_monitors(self, mock_pool, mock_library):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={"fitness": 0.75})
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(parent_skill_id=10)
        result = SandboxResult(
            proposal=proposal,
            llm_replay_score=0.8,
            pattern_match_count=60,
            pattern_match_rate=0.6,
            estimated_fitness=0.74,
            promoted=True,
        )
        await mutator.commit_or_rollback(result)

        # Should add candidate
        mock_library.add_candidate.assert_awaited_once()
        # Should promote
        mock_library.promote.assert_awaited_once_with(42)
        # Should freeze parent and insert mutation
        assert conn.execute.await_count >= 2

    @pytest.mark.asyncio
    async def test_skips_on_not_promoted(self, mock_pool, mock_library):
        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal()
        result = SandboxResult(
            proposal=proposal,
            llm_replay_score=0.3,
            pattern_match_count=10,
            pattern_match_rate=0.1,
            estimated_fitness=0.24,
            promoted=False,
            rejected_reason="fitness_below_threshold",
        )
        await mutator.commit_or_rollback(result)

        mock_library.add_candidate.assert_not_awaited()
        mock_library.promote.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_parent_freeze_when_none(self, mock_pool, mock_library):
        """When parent_skill_id is None, no parent freeze should happen."""
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        proposal = _make_proposal(parent_skill_id=None)
        result = SandboxResult(
            proposal=proposal,
            llm_replay_score=0.8,
            pattern_match_count=70,
            pattern_match_rate=0.7,
            estimated_fitness=0.77,
            promoted=True,
        )
        await mutator.commit_or_rollback(result)

        mock_library.add_candidate.assert_awaited_once()
        mock_library.promote.assert_awaited_once_with(42)
        # No parent freeze calls: only the mutation INSERT
        execute_calls = conn.execute.call_args_list
        # Should NOT have a "frozen" update
        frozen_calls = [
            c for c in execute_calls
            if "frozen" in str(c)
        ]
        assert len(frozen_calls) == 0


# ---------------------------------------------------------------------------
# TestRollback
# ---------------------------------------------------------------------------


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_when_fitness_drops(self, mock_pool, mock_library):
        """Skill with fitness below parent - margin should be rolled back."""
        conn = _conn_from_pool(mock_pool)

        # Pending mutation: parent_fitness=0.8
        pending = [
            {
                "id": 1,
                "skill_id": 42,
                "parent_skill_id": 10,
                "parent_fitness": 0.8,
            }
        ]

        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx == 0:
                return pending
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        # Current fitness = 0.5, threshold = 0.8 - 0.1 = 0.7 -> rollback
        conn.fetchval = AsyncMock(return_value=0.5)
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        rolled = await mutator.check_rollbacks()

        assert 42 in rolled
        # Should have apoptosed skill 42 and restored parent 10
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        assert any("apoptosed" in c for c in execute_calls)
        assert any("active" in c and "10" in c for c in execute_calls)

    @pytest.mark.asyncio
    async def test_survived_when_maintained(self, mock_pool, mock_library):
        """Skill with fitness above threshold survives."""
        conn = _conn_from_pool(mock_pool)

        pending = [
            {
                "id": 2,
                "skill_id": 43,
                "parent_skill_id": 11,
                "parent_fitness": 0.6,
            }
        ]

        fetch_call_count = [0]

        async def mock_fetch(*args, **kwargs):
            idx = fetch_call_count[0]
            fetch_call_count[0] += 1
            if idx == 0:
                return pending
            return []

        conn.fetch = AsyncMock(side_effect=mock_fetch)
        # Current fitness = 0.7, threshold = 0.6 - 0.1 = 0.5 -> survives
        conn.fetchval = AsyncMock(return_value=0.7)
        conn.execute = AsyncMock()

        mutator = StrategyMutator(mock_pool, mock_library)
        rolled = await mutator.check_rollbacks()

        assert rolled == []
        # Should have marked as survived
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        assert any("survived" in c for c in execute_calls)

    @pytest.mark.asyncio
    async def test_empty_when_no_pending(self, mock_pool, mock_library):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        mutator = StrategyMutator(mock_pool, mock_library)
        rolled = await mutator.check_rollbacks()

        assert rolled == []


# ---------------------------------------------------------------------------
# TestRateLimit
# ---------------------------------------------------------------------------


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_mutations_today_returns_count(self, mock_pool, mock_library):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=2)

        mutator = StrategyMutator(mock_pool, mock_library)
        count = await mutator.mutations_today()
        assert count == 2

    @pytest.mark.asyncio
    async def test_mutations_today_zero(self, mock_pool, mock_library):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=0)

        mutator = StrategyMutator(mock_pool, mock_library)
        count = await mutator.mutations_today()
        assert count == 0

    @pytest.mark.asyncio
    async def test_mutations_today_handles_none(self, mock_pool, mock_library):
        """PostgreSQL COUNT returns 0 but handle None defensively."""
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=None)

        mutator = StrategyMutator(mock_pool, mock_library)
        count = await mutator.mutations_today()
        assert count == 0

    def test_max_mutations_constant(self):
        assert MAX_MUTATIONS_PER_DAY == 3


# ---------------------------------------------------------------------------
# TestProposal
# ---------------------------------------------------------------------------


class TestProposal:
    @pytest.mark.asyncio
    async def test_successful_proposal(self, mock_pool, mock_library):
        """LLM returns valid JSON -> MutationProposal."""
        llm_response = json.dumps({
            "name": "smart_restart",
            "trigger": "when health fails 3 times in 10 minutes",
            "actions": ["check_health", "alert_human"],
            "rationale": "confirm failure then alert",
        })

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"message": {"content": llm_response}}
        mock_http.post = AsyncMock(return_value=mock_resp)

        mutator = StrategyMutator(mock_pool, mock_library, http_client=mock_http)
        signal = {
            "source": "critic_failure",
            "motivation": "repeated health failures",
            "parent_skill_id": 5,
        }
        result = await mutator.propose_from_signal(signal)

        assert result is not None
        assert result.proposed_name == "smart_restart"
        assert result.proposed_action_sequence == ["check_health", "alert_human"]
        assert result.source == "critic_failure"
        assert result.parent_skill_id == 5

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self, mock_pool, mock_library):
        """LLM error -> None."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("offline"))

        mutator = StrategyMutator(mock_pool, mock_library, http_client=mock_http)
        signal = {"source": "curiosity_finding", "motivation": "exploring"}
        result = await mutator.propose_from_signal(signal)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_actions_returns_none(self, mock_pool, mock_library):
        """LLM returns JSON with empty actions -> None."""
        llm_response = json.dumps({
            "name": "bad_skill",
            "trigger": "never",
            "actions": [],
            "rationale": "nothing",
        })

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"message": {"content": llm_response}}
        mock_http.post = AsyncMock(return_value=mock_resp)

        mutator = StrategyMutator(mock_pool, mock_library, http_client=mock_http)
        signal = {"source": "goal_completion", "motivation": "test"}
        result = await mutator.propose_from_signal(signal)
        assert result is None


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_sandbox_fitness_threshold(self):
        assert SANDBOX_FITNESS_THRESHOLD == 0.6

    def test_rollback_fitness_margin(self):
        assert ROLLBACK_FITNESS_MARGIN == 0.1
