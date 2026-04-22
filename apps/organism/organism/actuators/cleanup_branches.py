r"""Actuator: delete local git branches marked [gone] (remote deleted).

Reuses the `commit-commands:clean_gone` logic pattern:
1. git fetch --prune
2. git branch -vv | awk '/: gone\]/ {print $1}' | xargs git branch -D
"""
from __future__ import annotations

import asyncio
import re
from organism.actuators.base import ActuatorBase


_GONE_RE = re.compile(r"^\s*([^\s]+)\s+[0-9a-f]+\s+\[.*:\s*gone\]", re.MULTILINE)


class CleanupBranches(ActuatorBase):
    name = "cleanup_branches"

    async def _execute(self, params: dict) -> dict:
        # 1. fetch --prune to refresh gone status
        await self._run(["git", "fetch", "--prune"])
        # 2. list branches + find gone
        gone = await self._find_gone_branches()
        deleted = []
        failed = {}
        for branch in gone:
            rc, out, err = await self._run(["git", "branch", "-D", branch])
            if rc == 0:
                deleted.append(branch)
            else:
                failed[branch] = err[:200]
        return {"deleted_count": len(deleted), "deleted": deleted, "failed": failed}

    async def _dry_run(self, params: dict) -> dict:
        await self._run(["git", "fetch", "--prune"])
        gone = await self._find_gone_branches()
        return {"would_delete_count": len(gone), "would_delete": gone}

    async def _find_gone_branches(self) -> list[str]:
        rc, out, _ = await self._run(["git", "branch", "-vv"])
        if rc != 0:
            return []
        return _GONE_RE.findall(out)

    @staticmethod
    async def _run(cmd: list[str]) -> tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            return (
                proc.returncode or 0,
                out.decode("utf-8", errors="replace"),
                err.decode("utf-8", errors="replace"),
            )
        except (asyncio.TimeoutError, FileNotFoundError, OSError) as exc:
            return (-1, "", str(exc)[:200])
