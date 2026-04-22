"""Actuator: prune npm + pip + brew caches. Idempotent, dry-run lists bytes freed."""
from __future__ import annotations

import asyncio
from organism.actuators.base import ActuatorBase


CACHE_COMMANDS = [
    ("npm", ["npm", "cache", "clean", "--force"]),
    ("pip", ["pip", "cache", "purge"]),
    ("brew", ["brew", "cleanup", "--prune=all"]),
]


class CleanupCache(ActuatorBase):
    name = "cleanup_cache"

    async def _execute(self, params: dict) -> dict:
        results = {}
        for tool, cmd in CACHE_COMMANDS:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                out, err = await asyncio.wait_for(proc.communicate(), timeout=60.0)
                results[tool] = {
                    "returncode": proc.returncode,
                    "stdout_tail": out.decode("utf-8", errors="replace")[-300:],
                }
            except FileNotFoundError:
                results[tool] = {"skipped": "binary_not_found"}
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
                results[tool] = {"error": "timeout_60s"}
            except Exception as exc:
                results[tool] = {"error": str(exc)[:200]}
        return {"caches": results}

    async def _dry_run(self, params: dict) -> dict:
        return {"would_run": [" ".join(cmd) for _, cmd in CACHE_COMMANDS]}
