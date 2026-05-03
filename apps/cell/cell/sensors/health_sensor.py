"""Health sensor — reads /health endpoint from Nuzantara backend.
CELL's primary sensory organ. Every 60 seconds, checks if backend is alive.

Sprint 1.B 2026-05-02: HealthSensor.read() now bridges the result into
~/.organism/last_seen/backend.api.json via emit_organ_last_seen, so the
genome_aggregator_sensor can classify backend.api correctly.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cell.utils.organ_emitter import emit_organ_last_seen

logger = logging.getLogger("cell.sensors.health")

_BACKEND_API_ORGAN_ID = "backend.api"


@dataclass
class HealthReading:
    timestamp: datetime
    reachable: bool
    status_code: int = 0
    response_time_seconds: float = 0.0
    body: dict[str, Any] | None = None
    error: str = ""


def bridge_reading_to_sidecar(reading: HealthReading) -> bool:
    """Translate a HealthReading into a Genoma sidecar file.

    Sprint 1.B 2026-05-02: backend.api lives on Fly.io with ephemeral
    filesystem; it cannot write the sidecar itself. Cell on Pro polls
    /health and bridges the result into ~/.organism/last_seen/backend.api.json
    via emit_organ_last_seen.

    Best-effort: never raises. Returns True on emit success, False otherwise.

    Mapping:
        reachable=True, status=200      → "ok"
        reachable=True, status!=200     → "degraded"
        reachable=False                 → "fail"
    """
    if not reading.reachable:
        status = "fail"
    elif reading.status_code == 200:
        status = "ok"
    else:
        status = "degraded"

    metadata: dict[str, Any] = {"http_status": reading.status_code}
    if reading.response_time_seconds:
        metadata["latency_ms"] = round(reading.response_time_seconds * 1000.0, 2)
    if reading.error:
        metadata["error"] = reading.error[:200]

    return emit_organ_last_seen(_BACKEND_API_ORGAN_ID, status, metadata=metadata)


class HealthSensor:
    def __init__(self, client: Any, url: str, timeout: float = 10.0) -> None:
        self._client = client
        self._url = url
        self._timeout = timeout

    async def read(self) -> HealthReading:
        now = datetime.now(timezone.utc)
        try:
            response = await self._client.get(self._url, timeout=self._timeout)
            body = None
            try:
                body = response.json()
            except Exception:
                pass
            reading = HealthReading(
                timestamp=now,
                reachable=True,
                status_code=response.status_code,
                response_time_seconds=response.elapsed.total_seconds(),
                body=body,
            )
        except Exception as e:
            reading = HealthReading(timestamp=now, reachable=False, error=str(e))

        # Sprint 1.B Cell-side bridge: translate to Genoma sidecar (best-effort)
        try:
            bridge_reading_to_sidecar(reading)
        except Exception as exc:  # pragma: no cover — bridge never raises out
            logger.debug(f"sidecar bridge failed: {exc}")

        return reading
