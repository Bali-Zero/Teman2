"""Database reachability check (placeholder parity with legacy agent)."""

from __future__ import annotations

from backend.self_healing.checks.base import CheckResult


class DBCheck:
    name = "db"

    def __init__(self, connect_callable=None) -> None:
        # Inject a cheap async health probe (e.g., SELECT 1 via the pool).
        # When None, the check is a no-op — this mirrors the legacy agent
        # and keeps parity until a real probe lands.
        self._probe = connect_callable

    async def run(self) -> CheckResult:
        if self._probe is None:
            return CheckResult(healthy=True, detail={"probe": "not_configured"})
        try:
            await self._probe()
            return CheckResult(healthy=True, detail={"probe": "configured"})
        except Exception as exc:  # noqa: BLE001
            return CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")
