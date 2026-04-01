"""LocalEffector — executes local machine actions.

Currently supports:
  ollama_restart  — brew services restart ollama
  run_backup      — triggers ~/scripts/fly-pg-backup.sh

These are intentionally non-Fly.io actions that CELL was previously
blind to. All calls are async subprocesses; timeout enforced.
"""
import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("cell.effectors.local")


@dataclass
class LocalResult:
    success: bool
    action: str
    detail: str
    returncode: int = 0


class LocalEffector:
    """Executes local shell actions with a hard timeout."""

    def __init__(self, timeout_seconds: float = 120.0) -> None:
        self._timeout = timeout_seconds

    async def execute(self, action: str) -> LocalResult:
        if action == "ollama_restart":
            return await self._run(action, ["brew", "services", "restart", "ollama"])
        elif action == "run_backup":
            script = os.path.expanduser("~/scripts/fly-pg-backup.sh")
            return await self._run(action, ["bash", script])
        else:
            return LocalResult(success=False, action=action, detail=f"Unknown local action: {action}")

    async def _run(self, action: str, cmd: list[str]) -> LocalResult:
        logger.info(f"LocalEffector: executing {action} → {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return LocalResult(
                    success=False,
                    action=action,
                    detail=f"Timed out after {self._timeout}s",
                    returncode=-1,
                )

            rc = proc.returncode or 0
            out = stdout.decode(errors="replace").strip()
            err = stderr.decode(errors="replace").strip()
            detail = out or err or f"exit {rc}"

            if rc == 0:
                logger.info(f"LocalEffector {action} OK: {detail[:120]}")
                return LocalResult(success=True, action=action, detail=detail[:200], returncode=rc)
            else:
                logger.error(f"LocalEffector {action} FAILED (rc={rc}): {detail[:120]}")
                return LocalResult(success=False, action=action, detail=detail[:200], returncode=rc)

        except Exception as e:
            logger.error(f"LocalEffector {action} exception: {e}")
            return LocalResult(success=False, action=action, detail=str(e), returncode=-1)
