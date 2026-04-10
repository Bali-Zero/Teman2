"""Tests for cell_core.pulse — the lifecycle runner."""
import pytest
from datetime import datetime, timedelta, timezone

from cell_core.types import CellConfig, PulseResult, SafetyCheckResult

from conftest import (
    FakeSensor, FakeThinker, FakeActor, FakeSTM, FakeLTM, FakeEpisodic,
)


def _make_pulse_loop(
    config=None,
    sensors=None,
    thinker=None,
    actor=None,
    safety_proceeds=True,
    **kwargs,
):
    from cell_core.pulse import PulseLoop
    from cell_core.lifecycle import Maturation
    from cell_core.safety import SafetyGate
    from cell_core.homeostasis import HomeostaticController

    if config is None:
        config = CellConfig(
            name="test", dna_path="test.json",
            birth_date=datetime.now(timezone.utc) - timedelta(days=50),
        )

    class FakeSafetyGate:
        async def check(self):
            return SafetyCheckResult(can_proceed=safety_proceeds)

    return PulseLoop(
        config=config,
        sensors=sensors or [FakeSensor()],
        thinker=thinker or FakeThinker(),
        actor=actor or FakeActor(),
        stm=kwargs.get("stm", FakeSTM()),
        ltm=kwargs.get("ltm", FakeLTM()),
        episodic=kwargs.get("episodic", FakeEpisodic()),
        lifecycle=Maturation(config.birth_date),
        safety=FakeSafetyGate(),
        homeostasis=HomeostaticController(config.sleep_hours),
    )


class TestPulseLoopLifecycle:
    @pytest.mark.asyncio
    async def test_single_pulse_returns_result(self):
        pl = _make_pulse_loop()
        result = await pl.single_pulse()
        assert isinstance(result, PulseResult)
        assert result.pulse_number == 1
        assert result.halted is False

    @pytest.mark.asyncio
    async def test_pulse_increments_count(self):
        pl = _make_pulse_loop()
        await pl.single_pulse()
        await pl.single_pulse()
        assert pl.pulse_count == 2

    @pytest.mark.asyncio
    async def test_halts_when_safety_fails(self):
        pl = _make_pulse_loop(safety_proceeds=False)
        result = await pl.single_pulse()
        assert result.halted is True

    @pytest.mark.asyncio
    async def test_sense_collects_all_sensors(self):
        sensors = [FakeSensor("a"), FakeSensor("b"), FakeSensor("c")]
        stm = FakeSTM()
        pl = _make_pulse_loop(sensors=sensors, stm=stm)
        await pl.single_pulse()
        event_types = {et for et, _ in stm.stored}
        assert event_types == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_sensor_error_produces_red_reading(self):
        class BrokenSensor:
            name = "broken"
            async def read(self, **ctx):
                raise ConnectionError("down")

        pl = _make_pulse_loop(sensors=[BrokenSensor()])
        result = await pl.single_pulse()
        assert result.health_status == "red"

    @pytest.mark.asyncio
    async def test_think_not_called_when_green(self):
        thinker = FakeThinker()
        pl = _make_pulse_loop(thinker=thinker)
        await pl.single_pulse()
        assert thinker.call_count == 0

    @pytest.mark.asyncio
    async def test_think_called_when_red(self):
        thinker = FakeThinker(action="restart_service", confidence=0.9)
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=thinker,
        )
        await pl.single_pulse()
        assert thinker.call_count == 1

    @pytest.mark.asyncio
    async def test_act_executed_when_proposed(self):
        actor = FakeActor()
        thinker = FakeThinker(action="restart_service", confidence=0.9)
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=thinker,
            actor=actor,
        )
        result = await pl.single_pulse()
        assert "restart_service" in actor.executed
        assert result.action_taken is not None

    @pytest.mark.asyncio
    async def test_act_blocked_by_confidence_threshold(self):
        """Embrione phase (day 0) blocks all actions (threshold 1.1)."""
        actor = FakeActor()
        config = CellConfig(
            name="test", dna_path="test.json",
            birth_date=datetime.now(timezone.utc),  # age = 0 = embrione
        )
        pl = _make_pulse_loop(
            config=config,
            sensors=[FakeSensor(status="red")],
            thinker=FakeThinker(action="restart_service", confidence=0.9),
            actor=actor,
        )
        result = await pl.single_pulse()
        assert len(actor.executed) == 0  # embrione blocks actions

    @pytest.mark.asyncio
    async def test_act_blocked_by_allowlist(self):
        actor = FakeActor(allowlist={"alert_human"})
        thinker = FakeThinker(action="restart_service", confidence=0.9)
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=thinker,
            actor=actor,
        )
        result = await pl.single_pulse()
        assert len(actor.executed) == 0

    @pytest.mark.asyncio
    async def test_reflect_stores_episode_on_action(self):
        episodic = FakeEpisodic()
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=FakeThinker(action="restart_service", confidence=0.9),
            episodic=episodic,
        )
        await pl.single_pulse()
        assert len(episodic.episodes) >= 1

    @pytest.mark.asyncio
    async def test_reflect_skips_when_green_and_no_action(self):
        episodic = FakeEpisodic()
        pl = _make_pulse_loop(episodic=episodic)
        await pl.single_pulse()
        assert len(episodic.episodes) == 0

    @pytest.mark.asyncio
    async def test_recent_pulses_capped_at_50(self):
        pl = _make_pulse_loop()
        for _ in range(60):
            await pl.single_pulse()
        assert len(pl._recent_pulses) == 50

    @pytest.mark.asyncio
    async def test_on_pulse_callback(self):
        results = []
        async def on_pulse(result):
            results.append(result)

        from cell_core.pulse import PulseLoop
        from cell_core.lifecycle import Maturation
        from cell_core.homeostasis import HomeostaticController

        config = CellConfig(
            name="test", dna_path="test.json",
            birth_date=datetime.now(timezone.utc) - timedelta(days=50),
        )

        class FakeSafety:
            async def check(self):
                return SafetyCheckResult(can_proceed=True)

        pl = PulseLoop(
            config=config,
            sensors=[FakeSensor()],
            thinker=FakeThinker(),
            actor=FakeActor(),
            stm=FakeSTM(), ltm=FakeLTM(), episodic=FakeEpisodic(),
            lifecycle=Maturation(config.birth_date),
            safety=FakeSafety(),
            homeostasis=HomeostaticController(),
            on_pulse=on_pulse,
        )
        # Can't test run() (infinite loop), but single_pulse doesn't call on_pulse
        # on_pulse is called only in run()
