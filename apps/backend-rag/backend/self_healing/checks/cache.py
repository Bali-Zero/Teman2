"""Redis cache ping check."""

from __future__ import annotations

from backend.self_healing.checks.base import CheckResult


class CacheCheck:
    name = "cache"

    def __init__(self, redis_client=None) -> None:
        # redis_client is injected so the orchestrator can swap or re-create
        # the connection after an action has recovered it.
        self.redis_client = redis_client

    async def run(self) -> CheckResult:
        if self.redis_client is None:
            # No Redis configured — treat as healthy (service runs without cache)
            return CheckResult(healthy=True, detail={"configured": False})
        try:
            self.redis_client.ping()
            return CheckResult(healthy=True, detail={"configured": True})
        except Exception as exc:  # noqa: BLE001
            return CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")
