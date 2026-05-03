"""Safety mechanisms — kill switch + maintenance mode.
Three independent kill switches that CELL cannot modify:
1. Redis key: cell:disabled
2. Redis key: cell:maintenance
3. File on disk: /tmp/cell.disabled

If Redis is unavailable, CELL continues (fail-open) — file kill switch still works.

SafetyCheckResult imported from cell-core (shared type).
SafetyGate stays CELL-specific (Redis key format: cell:disabled, not cell:cell:disabled).
"""
import logging
from pathlib import Path
from typing import Any

from cell_core.types import SafetyCheckResult

logger = logging.getLogger("cell.safety")


class CellDisabledError(Exception):
    pass


class CellMaintenanceError(Exception):
    pass


class SafetyGate:
    def __init__(self, redis: Any, disable_file: str = "/tmp/cell.disabled") -> None:
        self._redis = redis
        self._disable_file = Path(disable_file)

    async def check(self) -> SafetyCheckResult:
        # File kill switch always checked first (works without Redis)
        if self._disable_file.exists():
            return SafetyCheckResult(
                can_proceed=False, reason="disabled",
                detail=f"Disable file exists: {self._disable_file}",
            )

        # Redis kill switches — fail-open if Redis unavailable
        try:
            disabled = await self._redis.get("cell:disabled")
            if disabled is not None:
                val = disabled.decode() if isinstance(disabled, bytes) else disabled
                return SafetyCheckResult(
                    can_proceed=False, reason="disabled",
                    detail=f"Redis cell:disabled set by: {val}",
                )
            maintenance = await self._redis.get("cell:maintenance")
            if maintenance is not None:
                val = maintenance.decode() if isinstance(maintenance, bytes) else maintenance
                return SafetyCheckResult(
                    can_proceed=False, reason="maintenance",
                    detail=f"Maintenance: {val}",
                )
        except Exception as e:
            logger.warning(f"Redis unavailable, proceeding without kill switch: {e}")

        return SafetyCheckResult(can_proceed=True)
