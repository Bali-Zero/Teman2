"""Base class for all actuators — enforces --dry-run, WAL, emit done event.

Every actuator subclass MUST:
- Set class attribute `name: str` (snake_case matching actuator_ref in YAML rules)
- Implement `async def _execute(self, params: dict) -> dict` (real side effect)
- Implement `async def _dry_run(self, params: dict) -> dict` (plan-only, no side effect)

The public .run() method:
1. Writes WAL entry to ~/logs/organism/wal/<name>-<uuid>.json
2. Calls _dry_run OR _execute depending on dry_run flag
3. Emits organism event with is_actuation=True on success/failure
4. Returns {"success": bool, **result}
"""
import abc
import json
import logging
import time
import uuid
from pathlib import Path

from organism.emit import emit_event
from organism.schemas import Severity


log = logging.getLogger(__name__)
WAL_DIR = Path.home() / "logs" / "organism" / "wal"


class ActuatorBase(abc.ABC):
    name: str  # subclass override — MUST match yaml_rules actuator field

    async def run(
        self,
        *,
        params: dict,
        correlation_id: str,
        dry_run: bool = False,
    ) -> dict:
        exec_id = str(uuid.uuid4())
        self._write_wal(exec_id, params, correlation_id, dry_run)
        try:
            if dry_run:
                result = {"dry_run": True, **(await self._dry_run(params))}
            else:
                result = await self._execute(params)
            try:
                await emit_event(
                    severity=Severity.INFO,
                    source=f"actuator.{self.name}",
                    kind=f"{self.name}_done",
                    payload={"exec_id": exec_id, "success": True, **result},
                    correlation_id=correlation_id,
                    is_actuation=True,
                )
            except Exception:
                log.exception("emit done event failed (non-fatal)")
            return {"success": True, **result}
        except Exception as exc:
            try:
                await emit_event(
                    severity=Severity.ERROR,
                    source=f"actuator.{self.name}",
                    kind=f"{self.name}_failed",
                    payload={"exec_id": exec_id, "error": str(exc)[:500]},
                    correlation_id=correlation_id,
                    is_actuation=True,
                )
            except Exception:
                log.exception("emit failed event failed (non-fatal)")
            return {"success": False, "error": str(exc)}

    @abc.abstractmethod
    async def _execute(self, params: dict) -> dict: ...

    @abc.abstractmethod
    async def _dry_run(self, params: dict) -> dict: ...

    def _write_wal(
        self,
        exec_id: str,
        params: dict,
        correlation_id: str,
        dry_run: bool,
    ) -> None:
        try:
            # Re-read WAL_DIR from module globals so monkeypatches in tests stick.
            import organism.actuators.base as _self_module

            wal_dir = _self_module.WAL_DIR
            wal_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": time.time(),
                "actuator": self.name,
                "exec_id": exec_id,
                "correlation_id": correlation_id,
                "dry_run": dry_run,
                "params": params,
            }
            (wal_dir / f"{self.name}-{exec_id}.json").write_text(
                json.dumps(entry, default=str),
                encoding="utf-8",
            )
        except Exception:
            log.exception("WAL write failed (non-fatal)")
