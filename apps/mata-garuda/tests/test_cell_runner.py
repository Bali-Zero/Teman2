"""Tests for mata_garuda.cell.runner — builds and runs PulseLoop."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from cell_core.types import PulseResult, Phase


class TestBuildPulseLoop:
    def test_builds_pulse_loop(self, tmp_path):
        from mata_garuda.cell.runner import build_pulse_loop

        with patch("mata_garuda.cell.runner.KnowledgeBase") as MockKB:
            MockKB.return_value = MagicMock()
            pl = build_pulse_loop(
                dna_path=str(tmp_path / "nonexistent.json"),
                kb_path=str(tmp_path / "test.db"),
            )

        from cell_core.pulse import PulseLoop
        assert isinstance(pl, PulseLoop)

    def test_lifecycle_phase(self):
        from mata_garuda.cell.runner import MG_BIRTH_DATE
        from cell_core.lifecycle import Maturation

        m = Maturation(birth_date=MG_BIRTH_DATE)
        # MG born 2026-04-01, should be past embrione
        assert m.age_days >= 9
        assert m.can_act() is True


class TestSinglePulse:
    @pytest.mark.asyncio
    async def test_single_pulse_runs(self, tmp_path):
        """Verify a single pulse completes with fake sensors."""
        from mata_garuda.cell.runner import build_pulse_loop
        from cell_core.types import SensorReading, SafetyCheckResult

        # Build with fakes
        from mata_garuda.cell.memory_bridge import BridgeSTM, KnowledgeBridgeLTM, ReflectionEpisodicStore
        from mata_garuda.cell.thinker import PassthroughThinker
        from cell_core.pulse import PulseLoop
        from cell_core.lifecycle import Maturation
        from cell_core.homeostasis import HomeostaticController

        class FakeSensor:
            name = "fake"
            async def read(self, **ctx):
                return SensorReading(sensor_name="fake", status="green")

        class FakeActor:
            async def act(self, proposal):
                return "done"
            def can_execute(self, action_name):
                return True

        class FakeSafety:
            async def check(self):
                return SafetyCheckResult(can_proceed=True)

        from mata_garuda.runtime.knowledge import KnowledgeBase
        kb = KnowledgeBase(db_path=tmp_path / "test.db")

        pl = PulseLoop(
            config=MagicMock(name="test", dna_path="x", sleep_hours=(2, 6)),
            sensors=[FakeSensor()],
            thinker=PassthroughThinker(),
            actor=FakeActor(),
            stm=BridgeSTM(),
            ltm=KnowledgeBridgeLTM(kb),
            episodic=ReflectionEpisodicStore(kb),
            lifecycle=Maturation(birth_date=datetime(2026, 4, 1, tzinfo=timezone.utc)),
            safety=FakeSafety(),
            homeostasis=HomeostaticController(),
        )

        result = await pl.single_pulse()
        assert isinstance(result, PulseResult)
        assert result.halted is False
        assert result.pulse_number == 1

        kb.close()
