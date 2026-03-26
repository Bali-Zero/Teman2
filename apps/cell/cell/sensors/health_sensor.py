"""Health sensor — reads /health endpoint from Nuzantara backend.
CELL's primary sensory organ. Every 60 seconds, checks if backend is alive."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass
class HealthReading:
    timestamp: datetime
    reachable: bool
    status_code: int = 0
    response_time_seconds: float = 0.0
    body: dict[str, Any] | None = None
    error: str = ""

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
            return HealthReading(timestamp=now, reachable=True, status_code=response.status_code, response_time_seconds=response.elapsed.total_seconds(), body=body)
        except Exception as e:
            return HealthReading(timestamp=now, reachable=False, error=str(e))
