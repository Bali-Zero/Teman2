"""Tests for mata_garuda.cell.sensors — cell-core Sensor protocol implementations."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cell_core.types import SensorReading
from cell_core.protocols import Sensor


class TestFitnessSensor:
    def test_implements_sensor_protocol(self):
        from mata_garuda.cell.sensors import FitnessSensor
        sensor = FitnessSensor(agent_name="test")
        assert isinstance(sensor, Sensor)
        assert sensor.name == "fitness:test"

    @pytest.mark.asyncio
    async def test_reads_success_rate(self, tmp_path):
        from mata_garuda.cell.sensors import FitnessSensor

        # Write fake fitness data
        fitness_file = tmp_path / "test_fitness.jsonl"
        for i in range(5):
            fitness_file.open("a").write(
                json.dumps({"success": i < 4, "mutation_version": 0}) + "\n"
            )

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=0.8):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.sensor_name == "fitness:test"
        assert reading.status == "green"  # 0.8 > 0.5 threshold
        assert reading.value == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_low_fitness_is_yellow(self):
        from mata_garuda.cell.sensors import FitnessSensor

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=0.4):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.status == "yellow"

    @pytest.mark.asyncio
    async def test_very_low_fitness_is_red(self):
        from mata_garuda.cell.sensors import FitnessSensor

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=0.1):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.status == "red"

    @pytest.mark.asyncio
    async def test_no_runs_is_yellow(self):
        from mata_garuda.cell.sensors import FitnessSensor

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=None):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.status == "yellow"
        assert reading.value is None


class TestRegulationSensor:
    def test_implements_sensor_protocol(self):
        from mata_garuda.cell.sensors import RegulationSensor
        sensor = RegulationSensor()
        assert isinstance(sensor, Sensor)
        assert sensor.name == "regulation_source"

    @pytest.mark.asyncio
    async def test_reads_source_availability(self):
        from mata_garuda.cell.sensors import RegulationSensor

        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="HTTP/2 200")
            sensor = RegulationSensor()
            reading = await sensor.read()

        assert reading.status == "green"

    @pytest.mark.asyncio
    async def test_source_down_is_red(self):
        from mata_garuda.cell.sensors import RegulationSensor

        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="")
            sensor = RegulationSensor()
            reading = await sensor.read()

        assert reading.status == "red"


class TestGapStreamSensor:
    def test_implements_sensor_protocol(self):
        from mata_garuda.cell.sensors import GapStreamSensor
        sensor = GapStreamSensor()
        assert isinstance(sensor, Sensor)
        assert sensor.name == "gap_stream"

    @pytest.mark.asyncio
    async def test_reads_stream_length(self):
        from mata_garuda.cell.sensors import GapStreamSensor
        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="5\n")
            sensor = GapStreamSensor()
            reading = await sensor.read()
        assert reading.status == "yellow"  # 5 < 10 = yellow
        assert reading.value == 5

    @pytest.mark.asyncio
    async def test_zero_gaps_is_green(self):
        from mata_garuda.cell.sensors import GapStreamSensor
        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="0\n")
            sensor = GapStreamSensor()
            reading = await sensor.read()
        assert reading.status == "green"

    @pytest.mark.asyncio
    async def test_many_gaps_is_red(self):
        from mata_garuda.cell.sensors import GapStreamSensor
        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="25\n")
            sensor = GapStreamSensor()
            reading = await sensor.read()
        assert reading.status == "red"

    @pytest.mark.asyncio
    async def test_redis_unavailable_is_yellow(self):
        from mata_garuda.cell.sensors import GapStreamSensor
        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="")
            sensor = GapStreamSensor()
            reading = await sensor.read()
        assert reading.status == "yellow"
