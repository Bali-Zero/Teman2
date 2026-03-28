"""DatabaseSensor — extracts DB connectivity status from /health body.

No additional HTTP call needed — reuses the HealthReading already fetched
by HealthSensor. Reads body.database.status.
"""
from dataclasses import dataclass, field
from typing import Any

from cell.sensors.health_sensor import HealthReading


@dataclass
class SensorReading:
    status: str  # "green", "yellow", "red"
    metadata: dict[str, Any] = field(default_factory=dict)


class DatabaseSensor:
    """Infers DB health from the /health response body.

    body.database.status:
      "connected" → GREEN
      any other value → YELLOW
      key absent / body None → RED
    """

    def read(self, health: HealthReading) -> SensorReading:
        if health.body is None:
            return SensorReading(status="red", metadata={"reason": "health body absent"})

        db_info = health.body.get("database", {})
        db_status = db_info.get("status", "") if isinstance(db_info, dict) else ""

        if db_status == "connected":
            return SensorReading(status="green", metadata={"db_status": db_status})
        elif db_status:
            return SensorReading(
                status="yellow",
                metadata={"db_status": db_status, "reason": f"unexpected db status: {db_status}"},
            )
        else:
            return SensorReading(
                status="red",
                metadata={"reason": "database.status missing from health body"},
            )
