"""ErrorRateSensor — counts 5xx errors in the last 5 minutes from the backend.

Makes a single GET /api/cell/metrics call (lightweight SQL query).
Uses a cooldown to avoid calling more than once per minute.

Thresholds:
  > 3 errors in 5min  → YELLOW
  > 10 errors in 5min → RED
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cell.sensors.error_rate")

_YELLOW_THRESHOLD = 3
_RED_THRESHOLD = 10
_COOLDOWN_SECONDS = 60
_NORMALIZE_MAX = 10.0  # denominator for error_rate_norm vector component


@dataclass
class SensorReading:
    status: str  # "green", "yellow", "red"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error_rate_norm(self) -> float:
        """Normalised error rate for FAISS vector (0.0–1.0)."""
        count = self.metadata.get("errors_5min", 0)
        return min(count / _NORMALIZE_MAX, 1.0)


class ErrorRateSensor:
    """Fetches 5-minute 5xx error count from /api/cell/metrics."""

    def __init__(self, client: Any, metrics_url: str) -> None:
        self._client = client
        self._metrics_url = metrics_url
        self._last_call: float = 0.0
        self._last_reading: SensorReading = SensorReading(
            status="green",
            metadata={"errors_5min": 0, "source": "init"},
        )

    async def read(self) -> SensorReading:
        now = time.monotonic()
        if now - self._last_call < _COOLDOWN_SECONDS:
            # Return cached reading within cooldown window
            return self._last_reading

        self._last_call = now
        try:
            response = await self._client.get(self._metrics_url, timeout=5.0)
            if response.status_code != 200:
                logger.warning(f"ErrorRateSensor: /api/cell/metrics returned {response.status_code}")
                self._last_reading = SensorReading(
                    status="yellow",
                    metadata={"reason": f"metrics endpoint returned {response.status_code}"},
                )
                return self._last_reading

            data = response.json()
            errors_5min = int(data.get("errors_5min", 0))

            if errors_5min > _RED_THRESHOLD:
                status = "red"
            elif errors_5min > _YELLOW_THRESHOLD:
                status = "yellow"
            else:
                status = "green"

            self._last_reading = SensorReading(
                status=status,
                metadata={
                    "errors_5min": errors_5min,
                    "threshold_yellow": _YELLOW_THRESHOLD,
                    "threshold_red": _RED_THRESHOLD,
                },
            )
        except Exception as e:
            logger.warning(f"ErrorRateSensor: failed to fetch metrics: {e}")
            # On failure, return last known reading (fail-open: don't escalate on sensor error)
            self._last_reading = SensorReading(
                status="yellow",
                metadata={"reason": f"metrics fetch failed: {e}", "errors_5min": 0},
            )

        return self._last_reading
