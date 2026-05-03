"""Tests for cortex SkillLibrary — CRUD, recall, decay, embedding, capacity."""

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from cell.cortex.skill_library import (
    DECAY_DAYS_THRESHOLD,
    DECAY_FITNESS_THRESHOLD,
    DEFAULT_MAX_ACTIVE,
    EMBEDDING_DIM,
    VALID_STATUSES,
    Skill,
    SkillLibrary,
    compute_embedding,
    cosine_similarity,
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


def _make_skill(**overrides) -> Skill:
    """Create a Skill with sensible defaults, overridable by kwargs."""
    defaults = dict(
        id=1,
        name="test_skill",
        trigger_nl="when something happens",
        action_sequence=["step1", "step2"],
        rationale_nl="because it helps",
        fitness=0.8,
        success_count=8,
        failure_count=2,
        use_count=10,
        generation=0,
        parent_id=None,
        embedding=compute_embedding("test"),
        status="active",
        created_at=datetime.now(timezone.utc),
        last_used_at=datetime.now(timezone.utc),
        last_decay_check=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Skill(**defaults)


# ---------------------------------------------------------------------------
# TestSkillDataclass
# ---------------------------------------------------------------------------


class TestSkillDataclass:
    def test_valid_creation(self):
        skill = _make_skill()
        assert skill.name == "test_skill"
        assert skill.status == "active"
        assert isinstance(skill.action_sequence, list)

    def test_all_valid_statuses(self):
        for status in VALID_STATUSES:
            skill = _make_skill(status=status)
            assert skill.status == status

    def test_invalid_status_raises_value_error(self):
        with pytest.raises(ValueError, match="status must be one of"):
            _make_skill(status="deleted")

    def test_invalid_action_sequence_raises_type_error(self):
        with pytest.raises(TypeError, match="action_sequence must be a list"):
            _make_skill(action_sequence="not a list")


# ---------------------------------------------------------------------------
# TestEmbedding
# ---------------------------------------------------------------------------


class TestEmbedding:
    def test_output_size(self):
        emb = compute_embedding("hello world")
        assert len(emb) == EMBEDDING_DIM * 4  # 384 float32 = 1536 bytes

    def test_deterministic(self):
        a = compute_embedding("same input")
        b = compute_embedding("same input")
        assert a == b

    def test_different_for_different_text(self):
        a = compute_embedding("visa application process")
        b = compute_embedding("company registration steps")
        assert a != b

    def test_normalized_to_unit_length(self):
        emb = compute_embedding("some text for embedding")
        vec = np.frombuffer(emb, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-5

    def test_cosine_similarity_identical(self):
        emb = compute_embedding("identical text")
        sim = cosine_similarity(emb, emb)
        assert abs(sim - 1.0) < 1e-5

    def test_cosine_similarity_different(self):
        a = compute_embedding("visa renewal Bali")
        b = compute_embedding("tax registration Jakarta")
        sim = cosine_similarity(a, b)
        assert -1.0 <= sim <= 1.0
        # Not identical
        assert sim < 0.99

    def test_cosine_similarity_zero_vector(self):
        zero = np.zeros(EMBEDDING_DIM, dtype=np.float32).tobytes()
        emb = compute_embedding("test")
        assert cosine_similarity(zero, emb) == 0.0


# ---------------------------------------------------------------------------
# TestSkillLibraryCRUD
# ---------------------------------------------------------------------------


class TestSkillLibraryCRUD:
    @pytest.mark.asyncio
    async def test_add_candidate_inserts(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=42)

        lib = SkillLibrary(mock_pool)
        new_id = await lib.add_candidate(
            name="greet_user",
            trigger_nl="when user says hello",
            action_sequence=["respond", "log"],
            rationale_nl="politeness matters",
        )
        assert new_id == 42
        # fetchval called for the INSERT RETURNING
        assert conn.fetchval.await_count >= 1

    @pytest.mark.asyncio
    async def test_add_candidate_with_parent(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        # First fetchval returns parent generation, second returns new id
        conn.fetchval = AsyncMock(side_effect=[3, 99])

        lib = SkillLibrary(mock_pool)
        new_id = await lib.add_candidate(
            name="greet_v2",
            trigger_nl="when user greets",
            action_sequence=["respond_v2"],
            rationale_nl="improved greeting",
            parent_id=10,
        )
        assert new_id == 99
        # Two acquire calls: one for parent lookup, one for insert
        assert mock_pool.acquire.call_count == 2

    @pytest.mark.asyncio
    async def test_promote_updates_status(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        lib = SkillLibrary(mock_pool)
        await lib.promote(skill_id=42)
        conn.execute.assert_awaited_once()
        call_sql = conn.execute.call_args[0][0]
        assert "active" in call_sql
        assert "candidate" in call_sql

    @pytest.mark.asyncio
    async def test_record_use_success(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        lib = SkillLibrary(mock_pool)
        await lib.record_use(skill_id=1, success=True)
        call_sql = conn.execute.call_args[0][0]
        assert "success_count" in call_sql

    @pytest.mark.asyncio
    async def test_record_use_failure(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        lib = SkillLibrary(mock_pool)
        await lib.record_use(skill_id=1, success=False)
        call_sql = conn.execute.call_args[0][0]
        assert "failure_count" in call_sql


# ---------------------------------------------------------------------------
# TestSkillLibraryRecall
# ---------------------------------------------------------------------------


class TestSkillLibraryRecall:
    @pytest.mark.asyncio
    async def test_empty_library_returns_empty(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])

        lib = SkillLibrary(mock_pool)
        result = await lib.recall({"event": "test"})
        assert result == []

    @pytest.mark.asyncio
    async def test_top_k_sorted_by_score(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        emb_a = compute_embedding("visa application help")
        emb_b = compute_embedding("completely unrelated task")
        now = datetime.now(timezone.utc)

        rows = [
            {
                "id": 1, "name": "visa_help", "trigger_nl": "visa application help",
                "action_sequence": json.dumps(["lookup_visa"]),
                "rationale_nl": "helps with visa", "fitness": 0.9,
                "success_count": 9, "failure_count": 1, "use_count": 10,
                "generation": 0, "parent_id": None, "embedding": emb_a,
                "status": "active", "created_at": now,
                "last_used_at": now, "last_decay_check": now,
            },
            {
                "id": 2, "name": "unrelated", "trigger_nl": "completely unrelated task",
                "action_sequence": json.dumps(["do_nothing"]),
                "rationale_nl": "not relevant", "fitness": 0.1,
                "success_count": 1, "failure_count": 9, "use_count": 10,
                "generation": 0, "parent_id": None, "embedding": emb_b,
                "status": "active", "created_at": now,
                "last_used_at": now, "last_decay_check": now,
            },
        ]
        conn.fetch = AsyncMock(return_value=rows)

        lib = SkillLibrary(mock_pool)
        result = await lib.recall({"event": "visa application help"}, k=2)
        assert len(result) == 2
        # Higher fitness + better cosine match should be first
        assert result[0].name == "visa_help"

    @pytest.mark.asyncio
    async def test_recall_excludes_non_active(self, mock_pool):
        """The SQL query already filters by status='active', so non-active
        skills should never appear in recall results."""
        conn = _conn_from_pool(mock_pool)
        conn.fetch = AsyncMock(return_value=[])  # DB returns nothing

        lib = SkillLibrary(mock_pool)
        result = await lib.recall({"event": "anything"})
        assert result == []
        # Verify the query contains the status filter
        call_sql = conn.fetch.call_args[0][0]
        assert "status = 'active'" in call_sql


# ---------------------------------------------------------------------------
# TestSkillLibraryDecay
# ---------------------------------------------------------------------------


class TestSkillLibraryDecay:
    @pytest.mark.asyncio
    async def test_decay_returns_count(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 5")

        lib = SkillLibrary(mock_pool)
        count = await lib.decay()
        assert count == 5

    @pytest.mark.asyncio
    async def test_decay_zero_when_nothing_apoptosed(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        lib = SkillLibrary(mock_pool)
        count = await lib.decay()
        assert count == 0

    @pytest.mark.asyncio
    async def test_decay_sql_contains_thresholds(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        lib = SkillLibrary(mock_pool)
        await lib.decay()
        call_sql = conn.execute.call_args[0][0]
        assert str(DECAY_FITNESS_THRESHOLD) in call_sql
        assert str(DECAY_DAYS_THRESHOLD) in call_sql


# ---------------------------------------------------------------------------
# TestSkillLibraryCapacity
# ---------------------------------------------------------------------------


class TestSkillLibraryCapacity:
    @pytest.mark.asyncio
    async def test_skips_when_under_limit(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=10)  # well under 50

        lib = SkillLibrary(mock_pool, max_active=50)
        count = await lib.enforce_capacity()
        assert count == 0
        # execute should NOT have been called (no UPDATE needed)
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_apoptoses_excess(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=55)  # 5 over limit
        conn.execute = AsyncMock(return_value="UPDATE 5")

        lib = SkillLibrary(mock_pool, max_active=50)
        count = await lib.enforce_capacity()
        assert count == 5
        # Verify the LIMIT in the UPDATE subquery
        call_args = conn.execute.call_args[0]
        assert 5 == call_args[1]  # $1 parameter = excess

    @pytest.mark.asyncio
    async def test_custom_max_active(self, mock_pool):
        conn = _conn_from_pool(mock_pool)
        conn.fetchval = AsyncMock(return_value=12)
        conn.execute = AsyncMock(return_value="UPDATE 2")

        lib = SkillLibrary(mock_pool, max_active=10)
        count = await lib.enforce_capacity()
        assert count == 2


# ---------------------------------------------------------------------------
# TestFormatForPrompt
# ---------------------------------------------------------------------------


class TestFormatForPrompt:
    def test_empty_returns_empty_string(self):
        assert SkillLibrary.format_for_prompt([]) == ""

    def test_includes_skill_info(self):
        skill = _make_skill(name="visa_check", trigger_nl="check visa status",
                            fitness=0.75, use_count=15, generation=2)
        result = SkillLibrary.format_for_prompt([skill])
        assert "visa_check" in result
        assert "check visa status" in result
        assert "0.75" in result
        assert "15" in result
        assert "gen=2" in result

    def test_multiple_skills(self):
        skills = [
            _make_skill(name="skill_a", trigger_nl="trigger a"),
            _make_skill(name="skill_b", trigger_nl="trigger b"),
            _make_skill(name="skill_c", trigger_nl="trigger c"),
        ]
        result = SkillLibrary.format_for_prompt(skills)
        assert result.count("\n") == 2  # 3 lines, 2 newlines
        assert "skill_a" in result
        assert "skill_b" in result
        assert "skill_c" in result

    def test_output_under_500_chars_for_three_skills(self):
        skills = [
            _make_skill(name=f"s{i}", trigger_nl=f"trigger {i}",
                        fitness=0.5 + i * 0.1, use_count=i * 5,
                        generation=i)
            for i in range(3)
        ]
        result = SkillLibrary.format_for_prompt(skills)
        assert len(result) < 500


# ---------------------------------------------------------------------------
# TestSituationToText
# ---------------------------------------------------------------------------


class TestSituationToText:
    def test_flattens_dict(self):
        text = SkillLibrary._situation_to_text({"event": "login", "user": "zero"})
        assert "event: login" in text
        assert "user: zero" in text

    def test_sorted_keys(self):
        text = SkillLibrary._situation_to_text({"z_key": "last", "a_key": "first"})
        assert text.index("a_key") < text.index("z_key")

    def test_empty_dict(self):
        assert SkillLibrary._situation_to_text({}) == ""
