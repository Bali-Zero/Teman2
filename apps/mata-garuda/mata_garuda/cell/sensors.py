"""Sensors — read MG state as cell-core SensorReadings.

Each sensor wraps an existing MG capability as a Sensor protocol implementation.
No new logic — just adapters.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess

from cell_core.types import SensorReading
from mata_garuda.runtime import fitness

logger = logging.getLogger("mata_garuda.cell")

# Thresholds for fitness → status mapping
_FITNESS_GREEN = 0.5
_FITNESS_YELLOW = 0.2


class FitnessSensor:
    """Reads agent fitness (success rate) as a SensorReading."""

    def __init__(self, agent_name: str = "Regulation Watcher") -> None:
        self.name = f"fitness:{agent_name}"
        self._agent_name = agent_name

    async def read(self, **context) -> SensorReading:
        rate = await asyncio.to_thread(fitness.get_success_rate, self._agent_name)
        if rate is None:
            return SensorReading(
                sensor_name=self.name, status="yellow",
                value=None, metadata={"reason": "no runs recorded"},
            )
        if rate >= _FITNESS_GREEN:
            status = "green"
        elif rate >= _FITNESS_YELLOW:
            status = "yellow"
        else:
            status = "red"
        return SensorReading(
            sensor_name=self.name, status=status,
            value=rate, metadata={"agent": self._agent_name},
        )


class RegulationSensor:
    """Checks if the regulation source (peraturan.go.id) is reachable."""

    SOURCE_URL = "https://peraturan.go.id"

    def __init__(self) -> None:
        self.name = "regulation_source"

    async def read(self, **context) -> SensorReading:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["curl", "-sI", "--max-time", "10", self.SOURCE_URL],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and "200" in result.stdout:
                return SensorReading(
                    sensor_name=self.name, status="green",
                    value=result.stdout[:100],
                )
            return SensorReading(
                sensor_name=self.name, status="red",
                value=result.stdout[:100],
                metadata={"returncode": result.returncode},
            )
        except Exception as e:
            return SensorReading(
                sensor_name=self.name, status="red",
                metadata={"error": str(e)},
            )


class GapStreamSensor:
    """Checks pending gap requests in nexus:gaps Redis stream."""

    STREAM_KEY = "nexus:gaps"

    def __init__(self) -> None:
        self.name = "gap_stream"

    async def read(self, **context) -> SensorReading:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["redis-cli", "XLEN", self.STREAM_KEY],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return SensorReading(
                    sensor_name=self.name, status="yellow",
                    metadata={"error": "redis-cli failed"},
                )
            count = int(result.stdout.strip())
            if count == 0:
                status = "green"
            elif count < 10:
                status = "yellow"
            else:
                status = "red"
            return SensorReading(
                sensor_name=self.name, status=status,
                value=count, metadata={"stream": self.STREAM_KEY},
            )
        except Exception as e:
            return SensorReading(
                sensor_name=self.name, status="yellow",
                metadata={"error": str(e)},
            )
