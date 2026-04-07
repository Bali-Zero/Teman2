"""Tests for Cortex orchestrator integration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cell.cortex.cortex import Cortex
from cell.lifecycle.maturation import LifecyclePhase, Maturation


def _make_mock_pool() -> MagicMock:
    """Create a mock asyncpg pool with acquire() context manager."""
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


def _make_cortex(phase: LifecyclePhase) -> Cortex:
    """Build a Cortex with mocked dependencies at the given lifecycle phase."""
    age_map = {
        LifecyclePhase.EMBRIONE: 1,
        LifecyclePhase.NEONATO: 5,
        LifecyclePhase.GIOVANE: 20,
        LifecyclePhase.ADULTO: 50,
        LifecyclePhase.ANZIANO: 200,
    }
    maturation = Maturation(age_days=age_map[phase])
    pool = _make_mock_pool()
    return Cortex(
        pool=pool,
        reasoner=MagicMock(),
        episodic=MagicMock(),
        self_model=MagicMock(),
        journal=MagicMock(),
        attention=MagicMock(),
        maturation=maturation,
    )


class TestCortexInit:
    def test_cortex_initializes(self) -> None:
        """Cortex creates all 6 sub-components."""
        cortex = _make_cortex(LifecyclePhase.ADULTO)
        assert cortex.skills is not None
        assert cortex.critic is not None
        assert cortex.curiosity is not None
        assert cortex.goals is not None
        assert cortex.mutator is not None
        assert cortex.gate is not None


class TestBeforeReasoning:
    @pytest.mark.asyncio
    async def test_before_reasoning_empty_in_embrione(self) -> None:
        """Embrione phase returns empty string (skills not active)."""
        cortex = _make_cortex(LifecyclePhase.EMBRIONE)
        result = await cortex.before_reasoning({"health_status": "green"})
        assert result == ""

    @pytest.mark.asyncio
    async def test_before_reasoning_returns_string(self) -> None:
        """Neonato phase calls skill recall and returns a string."""
        cortex = _make_cortex(LifecyclePhase.NEONATO)
        # Mock the skills.recall to return empty list (no skills yet)
        cortex.skills.recall = AsyncMock(return_value=[])
        result = await cortex.before_reasoning({"health_status": "yellow"})
        assert isinstance(result, str)
        cortex.skills.recall.assert_awaited_once()


class TestAfterAction:
    @pytest.mark.asyncio
    async def test_after_action_skipped_in_embrione(self) -> None:
        """Embrione phase: after_action does nothing, no error."""
        cortex = _make_cortex(LifecyclePhase.EMBRIONE)
        cortex.critic.register_expectation = AsyncMock()
        cortex.critic.evaluate_pending = AsyncMock(return_value=[])
        await cortex.after_action(
            episode_data=None, proposal=None, action="restart_service",
            episode_id=1, current_pulse=10,
        )
        # Critic should NOT be called in embrione
        cortex.critic.register_expectation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_after_action_registers_in_neonato(self) -> None:
        """Neonato phase: critic registers expectation (no LLM)."""
        cortex = _make_cortex(LifecyclePhase.NEONATO)
        cortex.critic.register_expectation = AsyncMock(return_value=None)
        cortex.critic.evaluate_pending = AsyncMock(return_value=[])
        await cortex.after_action(
            episode_data=None,
            proposal=MagicMock(confidence=0.9),
            action="restart_service",
            episode_id=1,
            current_pulse=10,
        )
        cortex.critic.register_expectation.assert_awaited_once()
        # Verify use_llm=False for neonato
        call_kwargs = cortex.critic.register_expectation.call_args[1]
        assert call_kwargs["use_llm"] is False


class TestDuringIdle:
    @pytest.mark.asyncio
    async def test_during_idle_skipped_high_stress(self) -> None:
        """High stress (>0.3) skips idle exploration."""
        cortex = _make_cortex(LifecyclePhase.GIOVANE)
        cortex.curiosity.explore = AsyncMock(return_value=[])
        await cortex.during_idle({"stress": 0.5, "attention_remaining": 50})
        cortex.curiosity.explore.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_during_idle_skipped_in_neonato(self) -> None:
        """Neonato phase: idle exploration not available."""
        cortex = _make_cortex(LifecyclePhase.NEONATO)
        cortex.curiosity.explore = AsyncMock(return_value=[])
        await cortex.during_idle({"stress": 0.1, "attention_remaining": 50})
        cortex.curiosity.explore.assert_not_awaited()


class TestDuringSleep:
    @pytest.mark.asyncio
    async def test_during_sleep_returns_summary_dict(self) -> None:
        """Sleep hook returns a dict with expected keys."""
        cortex = _make_cortex(LifecyclePhase.NEONATO)
        # Mock all async methods called during sleep
        cortex.skills.decay = AsyncMock(return_value=0)
        cortex.skills.enforce_capacity = AsyncMock(return_value=0)
        cortex.gate.effective_phase = AsyncMock(
            return_value=(LifecyclePhase.NEONATO, {"missing_for_next": ["episodes_recorded: 0/10"]})
        )
        cortex.mutator.check_rollbacks = AsyncMock(return_value=[])
        cortex.critic.detect_weaknesses_for = AsyncMock(return_value=[])
        cortex.goals.collect = AsyncMock(return_value=[])
        cortex.goals.archive_old = AsyncMock(return_value=0)

        summary = await cortex.during_sleep()
        assert isinstance(summary, dict)
        assert "decayed" in summary
        assert "effective_phase" in summary
        assert "rollbacks" in summary
        assert "mutations_proposed" in summary
        assert "promoted" in summary
        assert "missing_for_next" in summary
        assert summary["effective_phase"] == "neonato"
