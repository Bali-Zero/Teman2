"""Tests for cortex GoalGenerator — collect, dedup, pursue, archive, capacity."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from cell.cortex.goal_generator import (
    DEFAULT_MAX_ACTIVE,
    DEDUP_SIMILARITY_THRESHOLD,
    Goal,
    GoalGenerator,
    _SOURCE_PRIORITY,
    _jaccard,
    _trigrams,
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
    conn.execute = AsyncMock(return_value="UPDATE 0")
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
# TestTrigrams
# ---------------------------------------------------------------------------


class TestTrigrams:
    def test_normal_text(self):
        result = _trigrams("hello")
        assert "hel" in result
        assert "ell" in result
        assert "llo" in result

    def test_short_text(self):
        result = _trigrams("ab")
        assert result == {"ab"}

    def test_empty_text(self):
        result = _trigrams("")
        assert result == set()

    def test_case_insensitive(self):
        a = _trigrams("Hello")
        b = _trigrams("hello")
        assert a == b


# ---------------------------------------------------------------------------
# TestJaccard
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_strings(self):
        sim = _jaccard("same text here", "same text here")
        assert abs(sim - 1.0) < 1e-6

    def test_completely_different_strings(self):
        sim = _jaccard("aaa bbb ccc", "xyz 123 789")
        assert sim < 0.1

    def test_partial_overlap(self):
        sim = _jaccard("restart the service now", "restart the application now")
        assert 0.2 < sim < 0.9

    def test_empty_both(self):
        sim = _jaccard("", "")
        assert sim == 1.0

    def test_one_empty(self):
        sim = _jaccard("", "something")
        assert sim == 0.0

    def test_symmetry(self):
        a, b = "hello world", "world hello"
        assert abs(_jaccard(a, b) - _jaccard(b, a)) < 1e-6


# ---------------------------------------------------------------------------
# TestGoalDataclass
# ---------------------------------------------------------------------------


class TestGoalDataclass:
    def test_creation(self):
        g = Goal(
            id="abc123",
            source="curiosity",
            question="What pattern?",
            motivation="Found interesting data",
            priority=0.5,
            feasibility=0.9,
            novelty=1.0,
            score=0.45,
            status="pending",
            findings="",
            related_skill_id=None,
        )
        assert g.source == "curiosity"
        assert g.status == "pending"
        assert g.score == 0.45

    def test_default_timestamps(self):
        g = Goal(
            id="x", source="critic", question="Q?", motivation="M",
            priority=0.8, feasibility=0.9, novelty=1.0, score=0.72,
            status="pending", findings="", related_skill_id=None,
        )
        assert isinstance(g.created_at, datetime)
        assert g.completed_at is None


# ---------------------------------------------------------------------------
# TestSourcePriority
# ---------------------------------------------------------------------------


class TestSourcePriority:
    def test_all_sources_present(self):
        expected = {"curiosity", "critic", "dreamer_gap", "skill_decay", "maturity_gap"}
        assert set(_SOURCE_PRIORITY.keys()) == expected

    def test_values_in_range(self):
        for source, priority in _SOURCE_PRIORITY.items():
            assert 0.0 < priority <= 1.0, f"{source} priority out of range: {priority}"

    def test_critic_highest_among_standard(self):
        # maturity_gap is highest but reserved for AchievementGate
        standard = {k: v for k, v in _SOURCE_PRIORITY.items() if k != "maturity_gap"}
        assert max(standard.values()) == _SOURCE_PRIORITY["critic"]


# ---------------------------------------------------------------------------
# TestCollect
# ---------------------------------------------------------------------------


class TestCollect:
    @pytest.mark.asyncio
    async def test_empty_inputs(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        gen = GoalGenerator(mock_pool)
        result = await gen.collect()
        assert result == []

    @pytest.mark.asyncio
    async def test_collect_from_curiosity(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        # fetch calls: _get_active_questions (empty), _compute_novelty (empty), _enforce_capacity
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)

        finding = MagicMock()
        finding.question = "What does hour_of_day_rt reveal?"
        finding.finding = "Higher RT at night"

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(curiosity_findings=[finding])

        assert len(result) == 1
        assert result[0].source == "curiosity"
        assert result[0].priority == _SOURCE_PRIORITY["curiosity"]

    @pytest.mark.asyncio
    async def test_collect_from_critic(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)

        critique = MagicMock()
        critique.weakness_tag = "repeated_failure_restart_service"
        critique.self_critique_nl = "Expected success, got failure"

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(critic_signals=[critique])

        assert len(result) == 1
        assert result[0].source == "critic"
        assert "restart_service" in result[0].question

    @pytest.mark.asyncio
    async def test_collect_from_dreamer_gaps(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(dreamer_gaps=["no rule for OOM handling"])

        assert len(result) == 1
        assert result[0].source == "dreamer_gap"
        assert "OOM" in result[0].question

    @pytest.mark.asyncio
    async def test_collect_from_decayed_skills(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)

        skill = MagicMock()
        skill.name = "old_backup_skill"
        skill.id = 42

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(decayed_skills=[skill])

        assert len(result) == 1
        assert result[0].source == "skill_decay"
        assert result[0].related_skill_id == 42

    @pytest.mark.asyncio
    async def test_collect_dedup_by_similarity(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        # Existing active goal with very similar question
        conn.fetch = AsyncMock(return_value=[
            {"question": "How to address weakness: repeated_failure_restart?"},
        ])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=1)

        critique = MagicMock()
        critique.weakness_tag = "repeated_failure_restart"
        critique.self_critique_nl = "Failed again"

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(critic_signals=[critique])

        # The new goal question is very similar to the existing one, should be deduped
        # "How to address weakness: repeated_failure_restart?" vs
        # "How to address weakness: repeated_failure_restart?"
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_multiple_sources(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)

        finding = MagicMock()
        finding.question = "What about hourly patterns?"
        finding.finding = "Interesting data"

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(
            curiosity_findings=[finding],
            dreamer_gaps=["unknown error handling"],
        )

        assert len(result) == 2
        sources = {g.source for g in result}
        assert "curiosity" in sources
        assert "dreamer_gap" in sources

    @pytest.mark.asyncio
    async def test_score_computation(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)

        critique = MagicMock()
        critique.weakness_tag = "unique_weakness_xyz"
        critique.self_critique_nl = "calibration issue"

        gen = GoalGenerator(mock_pool)
        result = await gen.collect(critic_signals=[critique])

        assert len(result) == 1
        g = result[0]
        # score = priority * feasibility * novelty
        # critic priority = 0.8, feasibility = 0.9, novelty = 1.0 (no similar)
        expected_score = 0.8 * 0.9 * 1.0
        assert abs(g.score - expected_score) < 0.01


# ---------------------------------------------------------------------------
# TestPursueNext
# ---------------------------------------------------------------------------


class TestPursueNext:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_pending(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)

        gen = GoalGenerator(mock_pool)
        result = await gen.pursue_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_marks_resolved(self, mock_pool, now):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={
            "id": 1,
            "source": "curiosity",
            "question": "What is happening?",
            "motivation": "Curious about patterns",
            "priority": 0.5,
            "feasibility": 0.9,
            "novelty": 1.0,
            "score": 0.45,
            "status": "pending",
            "findings": "",
            "related_skill_id": None,
            "created_at": now,
            "completed_at": None,
        })
        conn.execute = AsyncMock()

        gen = GoalGenerator(mock_pool)
        result = await gen.pursue_next()

        assert result is not None
        assert result.status == "resolved"
        assert result.question == "What is happening?"

        # Verify status updates were called
        execute_calls = conn.execute.call_args_list
        sql_texts = [c[0][0] for c in execute_calls]
        assert any("investigating" in s for s in sql_texts)
        assert any("resolved" in s for s in sql_texts)

    @pytest.mark.asyncio
    async def test_uses_reasoner_if_provided(self, mock_pool, now):
        conn = _conn_from_pool(mock_pool)
        conn.fetchrow = AsyncMock(return_value={
            "id": 2,
            "source": "critic",
            "question": "How to fix weakness?",
            "motivation": "Repeated failures",
            "priority": 0.8,
            "feasibility": 0.9,
            "novelty": 1.0,
            "score": 0.72,
            "status": "pending",
            "findings": "",
            "related_skill_id": None,
            "created_at": now,
            "completed_at": None,
        })
        conn.execute = AsyncMock()

        mock_reasoner = AsyncMock(return_value="Implement retry logic with backoff.")

        gen = GoalGenerator(mock_pool)
        result = await gen.pursue_next(reasoner=mock_reasoner)

        assert result is not None
        assert result.findings == "Implement retry logic with backoff."
        mock_reasoner.assert_awaited_once_with("How to fix weakness?")


# ---------------------------------------------------------------------------
# TestListActive
# ---------------------------------------------------------------------------


class TestListActive:
    @pytest.mark.asyncio
    async def test_returns_goals(self, mock_pool, now):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": 1, "source": "curiosity", "question": "Q1?",
                "motivation": "M1", "priority": 0.5, "feasibility": 0.9,
                "novelty": 1.0, "score": 0.45, "status": "pending",
                "findings": "", "related_skill_id": None,
                "created_at": now, "completed_at": None,
            },
        ])

        gen = GoalGenerator(mock_pool)
        result = await gen.list_active()
        assert len(result) == 1
        assert result[0].question == "Q1?"

    @pytest.mark.asyncio
    async def test_returns_empty_when_none(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        gen = GoalGenerator(mock_pool)
        result = await gen.list_active()
        assert result == []


# ---------------------------------------------------------------------------
# TestArchiveOld
# ---------------------------------------------------------------------------


class TestArchiveOld:
    @pytest.mark.asyncio
    async def test_returns_count(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 3")

        gen = GoalGenerator(mock_pool)
        count = await gen.archive_old()
        assert count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_nothing_to_archive(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        gen = GoalGenerator(mock_pool)
        count = await gen.archive_old()
        assert count == 0

    @pytest.mark.asyncio
    async def test_sql_targets_resolved_older_than_30_days(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        gen = GoalGenerator(mock_pool)
        await gen.archive_old()

        sql = conn.execute.call_args[0][0]
        assert "resolved" in sql
        assert "30 days" in sql
        assert "archived" in sql


# ---------------------------------------------------------------------------
# TestEnforceCapacity
# ---------------------------------------------------------------------------


class TestEnforceCapacity:
    @pytest.mark.asyncio
    async def test_no_action_under_limit(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=5)  # well under 20

        gen = GoalGenerator(mock_pool, max_active=20)
        count = await gen._enforce_capacity()
        assert count == 0

    @pytest.mark.asyncio
    async def test_archives_excess(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=25)  # 5 over
        conn.execute = AsyncMock(return_value="UPDATE 5")

        gen = GoalGenerator(mock_pool, max_active=20)
        count = await gen._enforce_capacity()
        assert count == 5

    @pytest.mark.asyncio
    async def test_custom_max_active(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=8)
        conn.execute = AsyncMock(return_value="UPDATE 3")

        gen = GoalGenerator(mock_pool, max_active=5)
        count = await gen._enforce_capacity()
        assert count == 3


# ---------------------------------------------------------------------------
# TestComputeNovelty
# ---------------------------------------------------------------------------


class TestComputeNovelty:
    @pytest.mark.asyncio
    async def test_novel_when_no_similar(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        gen = GoalGenerator(mock_pool)
        novelty = await gen._compute_novelty("completely unique question?")
        assert novelty == 1.0

    @pytest.mark.asyncio
    async def test_not_novel_when_similar_exists(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[
            {"question": "completely unique question?"},
        ])

        gen = GoalGenerator(mock_pool)
        novelty = await gen._compute_novelty("completely unique question?")
        assert novelty == 0.3
