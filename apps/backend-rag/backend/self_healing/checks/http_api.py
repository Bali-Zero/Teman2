"""HTTP API liveness probe."""

from __future__ import annotations

import httpx

from backend.self_healing.checks.base import CheckResult


# Golden Rule #10: module-level lazy singleton AsyncClient. Lifespan
# closes via close_http_api_check_client() in app_factory.lifespan().
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_http_api_check_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


class HTTPAPICheck:
    name = "api"

    def __init__(self, url: str, client: httpx.AsyncClient | None = None, timeout: float = 5.0) -> None:
        self.url = url
        self.client = client
        self.timeout = timeout

    async def run(self) -> CheckResult:
        client = self.client or _get_module_client(self.timeout)
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
