"""Tests for mata_garuda.cell.thinker — passthrough decision gate."""
import pytest

from cell_core.types import HomeostaticState, Proposal, SensorReading
from cell_core.protocols import Thinker


class TestPassthroughThinker:
    def test_implements_thinker_protocol(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        assert isinstance(thinker, Thinker)

    @pytest.mark.asyncio
    async def test_proposes_run_when_red_fitness(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="fitness:Regulation Watcher", status="red", value=0.1),
        ]
        state = HomeostaticState(stress_level=0.8)
        proposal = await thinker.think(readings, state, {})
        assert proposal.action != "none"

    @pytest.mark.asyncio
    async def test_proposes_run_when_regulation_source_green(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="regulation_source", status="green"),
            SensorReading(sensor_name="fitness:Regulation Watcher", status="green", value=0.9),
        ]
        state = HomeostaticState()
        proposal = await thinker.think(readings, state, {})
        # Green across the board — still propose run (it's harvest time)
        assert proposal.action == "run_regulation_watcher"

    @pytest.mark.asyncio
    async def test_proposes_none_when_source_down(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="regulation_source", status="red"),
            SensorReading(sensor_name="fitness:Regulation Watcher", status="green", value=0.9),
        ]
        state = HomeostaticState()
        proposal = await thinker.think(readings, state, {})
        # Source down — don't try to scrape
        assert proposal.action == "none"

    @pytest.mark.asyncio
    async def test_proposes_none_when_sleeping(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="regulation_source", status="green"),
        ]
        state = HomeostaticState(circadian_phase="asleep")
        proposal = await thinker.think(readings, state, {})
        assert proposal.action == "none"
