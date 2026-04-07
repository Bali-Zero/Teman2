# apps/cell/tests/test_achievement_gate.py
"""Tests for AchievementGate — achievement-based lifecycle gating."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from cell.lifecycle.maturation import LifecyclePhase, Maturation
from cell.lifecycle.achievement_gate import (
    AchievementGate,
    _PHASE_RANK,
    _AGE_FLOORS,
    _ESCAPE_HATCH_DAYS,
    _REQUIREMENTS,
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


def _set_achievements(pool: AsyncMock, values: list) -> None:
    """Configure fetchval side_effect so each SQL call returns the next value.

    Order of calls in achievements():
      0: episodes_recorded
      1: episodes_with_outcome
      2: skills_in_library
      3: goals_completed
      4: skills_stable_30d
      5: skills_fitness_above_06
      6: journal_continuity_days
    """
    conn = _conn_from_pool(pool)
    conn.fetchval = AsyncMock(side_effect=values)


# ---------------------------------------------------------------------------
# Phase rank ordering (sanity)
# ---------------------------------------------------------------------------


class TestPhaseRank:
    def test_phase_rank_ordering(self):
        """_PHASE_RANK must be monotonically increasing from embrione to anziano."""
        ordered = [
            LifecyclePhase.EMBRIONE,
            LifecyclePhase.NEONATO,
            LifecyclePhase.GIOVANE,
            LifecyclePhase.ADULTO,
            LifecyclePhase.ANZIANO,
        ]
        for i in range(len(ordered) - 1):
            assert _PHASE_RANK[ordered[i]] < _PHASE_RANK[ordered[i + 1]]

    def test_str_enum_alphabetical_trap(self):
        """Demonstrate WHY we need _PHASE_RANK: str(Enum) compares alphabetically."""
        # Alphabetically: adulto < anziano < embrione < giovane < neonato
        # This is WRONG for lifecycle ordering.
        assert LifecyclePhase.EMBRIONE > LifecyclePhase.ADULTO  # alphabetical!
        # But our rank map is correct:
        assert _PHASE_RANK[LifecyclePhase.EMBRIONE] < _PHASE_RANK[LifecyclePhase.ADULTO]


# ---------------------------------------------------------------------------
# Delegation (backward compatibility)
# ---------------------------------------------------------------------------


class TestDelegation:
    def test_phase_property_delegates_to_base(self, mock_pool: AsyncMock):
        m = Maturation(age_days=20)
        gate = AchievementGate(m, mock_pool)
        assert gate.phase == LifecyclePhase.GIOVANE

    def test_age_days_property_delegates(self, mock_pool: AsyncMock):
        m = Maturation(age_days=42)
        gate = AchievementGate(m, mock_pool)
        assert gate.age_days == 42

    def test_can_act_delegates(self, mock_pool: AsyncMock):
        m = Maturation(age_days=1)
        gate = AchievementGate(m, mock_pool)
        assert gate.can_act() is False

        m2 = Maturation(age_days=5)
        gate2 = AchievementGate(m2, mock_pool)
        assert gate2.can_act() is True

    def test_can_dream_delegates(self, mock_pool: AsyncMock):
        m = Maturation(age_days=20)
        gate = AchievementGate(m, mock_pool)
        assert gate.can_dream() is True

    def test_action_confidence_threshold_delegates(self, mock_pool: AsyncMock):
        m = Maturation(age_days=7)
        gate = AchievementGate(m, mock_pool)
        assert gate.action_confidence_threshold() == 0.8


# ---------------------------------------------------------------------------
# Embrione — not gated by achievements
# ---------------------------------------------------------------------------


class TestEmbrione:
    @pytest.mark.asyncio
    async def test_embrione_not_affected_by_achievements(self, mock_pool: AsyncMock):
        """Embrione has no achievement requirements — always stays embrione."""
        # Even with amazing achievements, day 2 is still embrione (age floor).
        _set_achievements(mock_pool, [999, 999, 999, 999, 999, 1.0, 999])
        m = Maturation(age_days=2)
        gate = AchievementGate(m, mock_pool)
        phase, info = await gate.effective_phase()
        assert phase == LifecyclePhase.EMBRIONE

    @pytest.mark.asyncio
    async def test_age_floor_inviolable_day3_with_999_skills(self, mock_pool: AsyncMock):
        """Day 3 with 999 skills is still embrione — age floor is absolute."""
        _set_achievements(mock_pool, [999, 999, 999, 999, 999, 1.0, 999])
        m = Maturation(age_days=3)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.EMBRIONE


# ---------------------------------------------------------------------------
# Neonato → Giovane gating
# ---------------------------------------------------------------------------


class TestNeonatoToGiovane:
    @pytest.mark.asyncio
    async def test_neonato_stays_if_episodes_below_10(self, mock_pool: AsyncMock):
        """Age 16 (giovane by age) but only 5 episodes → demoted to neonato."""
        _set_achievements(mock_pool, [5, 3, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=16)
        gate = AchievementGate(m, mock_pool)
        phase, info = await gate.effective_phase()
        assert phase == LifecyclePhase.NEONATO
        assert "episodes_recorded: 5/10" in info["missing_for_next"]

    @pytest.mark.asyncio
    async def test_giovane_with_enough_episodes(self, mock_pool: AsyncMock):
        """Age 16 with 15 episodes → giovane holds."""
        _set_achievements(mock_pool, [15, 10, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=16)
        gate = AchievementGate(m, mock_pool)
        phase, info = await gate.effective_phase()
        assert phase == LifecyclePhase.GIOVANE


# ---------------------------------------------------------------------------
# Giovane → Adulto gating
# ---------------------------------------------------------------------------


class TestGiovaneToAdulto:
    @pytest.mark.asyncio
    async def test_giovane_blocked_from_adulto_missing_skills(self, mock_pool: AsyncMock):
        """Age 35 (adulto by age) but insufficient skills/goals → stays giovane."""
        # episodes_recorded=20, episodes_with_outcome=60, skills=3, goals=2
        _set_achievements(mock_pool, [20, 60, 3, 2, 0, 0.0, 0])
        m = Maturation(age_days=35)
        gate = AchievementGate(m, mock_pool)
        phase, info = await gate.effective_phase()
        assert phase == LifecyclePhase.GIOVANE
        missing = info["missing_for_next"]
        assert any("skills_in_library" in m for m in missing)
        assert any("goals_completed" in m for m in missing)

    @pytest.mark.asyncio
    async def test_adulto_when_all_requirements_met(self, mock_pool: AsyncMock):
        """Age 35 with all adulto achievements → adulto."""
        _set_achievements(mock_pool, [100, 60, 15, 8, 0, 0.0, 0])
        m = Maturation(age_days=35)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.ADULTO

    @pytest.mark.asyncio
    async def test_adulto_blocked_cascades_to_neonato(self, mock_pool: AsyncMock):
        """Age 31, adulto and giovane requirements unmet → cascades to neonato.

        age 31: adulto by age, adulto escape hatch at 45 (not reached),
        giovane escape hatch at 29 (reached! 31 >= 29), so we need an age
        where giovane escape hatch also does NOT fire. Use age 15+13=28 — but
        that's neonato by age. So instead, use the earliest adulto age (31),
        which is past the giovane escape hatch. Therefore a full cascade to
        neonato is impossible without triggering the giovane escape hatch.
        We verify cascade stops at giovane (escape hatch).
        """
        _set_achievements(mock_pool, [3, 1, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=31)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        # Adulto reqs unmet → demote to giovane.
        # Giovane reqs unmet (episodes < 10) BUT escape hatch fires (31 >= 15+14=29).
        assert phase == LifecyclePhase.GIOVANE


# ---------------------------------------------------------------------------
# Anziano gating
# ---------------------------------------------------------------------------


class TestAnziano:
    @pytest.mark.asyncio
    async def test_anziano_requires_stability_metrics(self, mock_pool: AsyncMock):
        """Age 185 but skills unstable → blocked from anziano (escape hatch at 194)."""
        # All lower gates met but anziano reqs not.
        # age 185 < 180 + 14 = 194 → escape hatch does NOT fire.
        _set_achievements(mock_pool, [200, 100, 25, 15, 5, 0.3, 30])
        m = Maturation(age_days=185)
        gate = AchievementGate(m, mock_pool)
        phase, info = await gate.effective_phase()
        assert phase == LifecyclePhase.ADULTO
        missing = info["missing_for_next"]
        assert any("skills_stable_30d" in m for m in missing)
        assert any("skills_fitness_above_06" in m for m in missing)
        assert any("journal_continuity_days" in m for m in missing)

    @pytest.mark.asyncio
    async def test_anziano_when_fully_mature(self, mock_pool: AsyncMock):
        """Age 200 with all achievements → anziano."""
        _set_achievements(mock_pool, [500, 300, 30, 20, 25, 0.85, 90])
        m = Maturation(age_days=200)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.ANZIANO


# ---------------------------------------------------------------------------
# Escape hatch
# ---------------------------------------------------------------------------


class TestEscapeHatch:
    @pytest.mark.asyncio
    async def test_escape_hatch_promotes_after_age_plus_14(self, mock_pool: AsyncMock):
        """Age 29 (giovane floor=15, +14=29) with 0 episodes → escape hatch promotes."""
        _set_achievements(mock_pool, [0, 0, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=29)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        # Age 29 >= 15 + 14 → escape hatch for giovane fires.
        assert phase == LifecyclePhase.GIOVANE

    @pytest.mark.asyncio
    async def test_no_escape_hatch_before_threshold(self, mock_pool: AsyncMock):
        """Age 28 (giovane floor=15, +14=29, not reached) with 0 episodes → neonato."""
        _set_achievements(mock_pool, [0, 0, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=28)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.NEONATO

    @pytest.mark.asyncio
    async def test_escape_hatch_adulto(self, mock_pool: AsyncMock):
        """Age 45 (adulto floor=31, +14=45) with few achievements → escape hatch."""
        # Giovane reqs met (episodes=15) but adulto reqs not met.
        _set_achievements(mock_pool, [15, 10, 2, 1, 0, 0.0, 0])
        m = Maturation(age_days=45)
        gate = AchievementGate(m, mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.ADULTO


# ---------------------------------------------------------------------------
# Achievements query
# ---------------------------------------------------------------------------


class TestAchievementsQuery:
    @pytest.mark.asyncio
    async def test_achievements_returns_all_seven_keys(self, mock_pool: AsyncMock):
        _set_achievements(mock_pool, [10, 5, 3, 2, 1, 0.5, 7])
        m = Maturation(age_days=10)
        gate = AchievementGate(m, mock_pool)
        achv = await gate.achievements()
        assert achv == {
            "episodes_recorded": 10,
            "episodes_with_outcome": 5,
            "skills_in_library": 3,
            "goals_completed": 2,
            "skills_stable_30d": 1,
            "skills_fitness_above_06": 0.5,
            "journal_continuity_days": 7,
        }

    @pytest.mark.asyncio
    async def test_achievements_makes_seven_queries(self, mock_pool: AsyncMock):
        _set_achievements(mock_pool, [0, 0, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=10)
        gate = AchievementGate(m, mock_pool)
        await gate.achievements()
        conn = _conn_from_pool(mock_pool)
        assert conn.fetchval.call_count == 7


# ---------------------------------------------------------------------------
# missing_for_next_phase
# ---------------------------------------------------------------------------


class TestMissingForNextPhase:
    @pytest.mark.asyncio
    async def test_missing_for_next_at_embrione(self, mock_pool: AsyncMock):
        """Embrione → neonato has no achievement gate, so missing is empty."""
        _set_achievements(mock_pool, [0, 0, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=1)
        gate = AchievementGate(m, mock_pool)
        missing = await gate.missing_for_next_phase()
        # neonato has no requirements entry, so nothing missing.
        assert missing == []

    @pytest.mark.asyncio
    async def test_missing_for_next_at_neonato(self, mock_pool: AsyncMock):
        """Neonato with 0 episodes → next phase (giovane) needs 10 episodes."""
        _set_achievements(mock_pool, [0, 0, 0, 0, 0, 0.0, 0])
        m = Maturation(age_days=5)
        gate = AchievementGate(m, mock_pool)
        missing = await gate.missing_for_next_phase()
        assert "episodes_recorded: 0/10" in missing

    @pytest.mark.asyncio
    async def test_missing_empty_at_anziano(self, mock_pool: AsyncMock):
        """Anziano is max phase — no next phase, missing is empty."""
        _set_achievements(mock_pool, [500, 300, 30, 20, 25, 0.85, 90])
        m = Maturation(age_days=200)
        gate = AchievementGate(m, mock_pool)
        missing = await gate.missing_for_next_phase()
        assert missing == []
