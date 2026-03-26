"""Safety mechanisms — kill switch + maintenance mode.
Three independent kill switches that CELL cannot modify:
1. Redis key: cell:disabled
2. Redis key: cell:maintenance
3. File on disk: /tmp/cell.disabled
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class CellDisabledError(Exception):
    pass

class CellMaintenanceError(Exception):
    pass

@dataclass
class SafetyCheckResult:
    can_proceed: bool
    reason: str = ""
    detail: str = ""

class SafetyGate:
    def __init__(self, redis: Any, disable_file: str = "/tmp/cell.disabled") -> None:
        self._redis = redis
        self._disable_file = Path(disable_file)

    async def check(self) -> SafetyCheckResult:
        if self._disable_file.exists():
            return SafetyCheckResult(can_proceed=False, reason="disabled", detail=f"Disable file exists: {self._disable_file}")
        disabled = await self._redis.get("cell:disabled")
        if disabled is not None:
            return SafetyCheckResult(can_proceed=False, reason="disabled", detail=f"Redis cell:disabled set by: {disabled.decode() if isinstance(disabled, bytes) else disabled}")
        maintenance = await self._redis.get("cell:maintenance")
        if maintenance is not None:
            return SafetyCheckResult(can_proceed=False, reason="maintenance", detail=f"Maintenance: {maintenance.decode() if isinstance(maintenance, bytes) else maintenance}")
        return SafetyCheckResult(can_proceed=True)
