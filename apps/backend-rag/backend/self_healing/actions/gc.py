"""Force Python garbage collection — cheap memory-pressure relief."""

from __future__ import annotations

import gc

from backend.self_healing.actions.base import ActionResult


class GCAction:
    name = "gc_collect"
    target_check = "memory"

    async def run(self) -> ActionResult:
        try:
            collected = gc.collect()
            return ActionResult(success=True, detail=f"gc collected {collected} objects")
        except Exception as exc:  # noqa: BLE001
            return ActionResult(success=False, error=f"{type(exc).__name__}: {exc}")
