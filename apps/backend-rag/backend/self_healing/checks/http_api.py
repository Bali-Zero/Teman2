"""HTTP API liveness probe."""

from __future__ import annotations

import httpx

from backend.self_healing.checks.base import CheckResult


class HTTPAPICheck:
    name = "api"

    def __init__(self, url: str, client: httpx.AsyncClient | None = None, timeout: float = 5.0) -> None:
        self.url = url
        self.client = client
        self.timeout = timeout

    async def run(self) -> CheckResult:
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        close_after = self.client is None
        try:
            response = await client.get(self.url, timeout=self.timeout)
            healthy = response.status_code == 200
            return CheckResult(
                healthy=healthy,
                detail={"url": self.url, "status_code": response.status_code},
                error=None if healthy else f"HTTP {response.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")
        finally:
            if close_after:
                await client.aclose()
