"""Actuator: adopt a new app module into the organism watch list.

Called on `new_module` events emitted by the git post-commit hook.
Performs maturity check; if passed AND no `.organism_ignore` marker,
creates a probationary 7-day watch via Redis key
`organism:probationary:<name>`. After probation expiry, Supervisor
(W4 integration) promotes to full watch.

Maturity signals (all required):
- `pyproject.toml` OR `package.json` in module root
- `README.md` in module root
- Git first-commit age on the module's path > 24h
- Current branch does NOT start with `feat/`, `fix/`, `session/`, `chore/`
- `.organism_ignore` file does NOT exist in module root

Idempotent: re-running on already-adopted module returns `already_adopted: true`.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from organism.actuators.base import ActuatorBase


PROBATIONARY_KEY_PREFIX = "organism:probationary:"
ADOPTED_KEY_PREFIX = "organism:adopted:"
DEFAULT_PROBATION_SECONDS = 7 * 86400  # 7 days
WIP_BRANCH_PREFIXES = ("feat/", "fix/", "session/", "chore/")


class AdoptModule(ActuatorBase):
    name = "adopt_module"

    def __init__(self, *, redis):
        self.redis = redis

    async def _execute(self, params: dict) -> dict:
        module_path = Path(params["module_path"])
        if not module_path.exists() or not module_path.is_dir():
            return {"adopted": False, "reason": "path_missing"}

        # Idempotency — already adopted
        already = await self.redis.get(ADOPTED_KEY_PREFIX + module_path.name)
        if already:
            return {
                "adopted": False,
                "reason": "already_adopted",
                "module_name": module_path.name,
            }

        # Probationary already active — do not reset TTL
        probationary = await self.redis.get(PROBATIONARY_KEY_PREFIX + module_path.name)
        if probationary:
            try:
                promote_at = float(probationary)
            except (ValueError, TypeError):
                promote_at = None
            return {
                "adopted": False,
                "reason": "probationary_active",
                "module_name": module_path.name,
                "promote_at": promote_at,
            }

        # Opt-out marker
        if (module_path / ".organism_ignore").exists():
            return {
                "adopted": False,
                "reason": "organism_ignore_opt_out",
                "module_name": module_path.name,
            }

        signals = await self._check_maturity(module_path)
        if not signals["is_mature"]:
            return {
                "adopted": False,
                "reason": "maturity_missing",
                "module_name": module_path.name,
                "missing": signals["missing"],
            }

        # Probationary watch — write Redis key with 7d TTL
        promote_at = time.time() + DEFAULT_PROBATION_SECONDS
        await self.redis.set(
            PROBATIONARY_KEY_PREFIX + module_path.name,
            str(promote_at),
            ex=DEFAULT_PROBATION_SECONDS,
        )
        return {
            "adopted": True,
            "mode": "probationary_7d",
            "module_name": module_path.name,
            "module_path": str(module_path),
            "promote_at": promote_at,
        }

    async def _dry_run(self, params: dict) -> dict:
        module_path = Path(params["module_path"])
        if module_path.exists():
            # Check idempotency first — matches _execute behavior
            already = await self.redis.get(ADOPTED_KEY_PREFIX + module_path.name)
            if already:
                return {
                    "would_adopt": False,
                    "module_name": module_path.name,
                    "reason": "already_adopted",
                }
            probationary = await self.redis.get(PROBATIONARY_KEY_PREFIX + module_path.name)
            if probationary:
                return {
                    "would_adopt": False,
                    "module_name": module_path.name,
                    "reason": "probationary_active",
                }
        signals = await self._check_maturity(module_path) if module_path.exists() else {
            "is_mature": False,
            "missing": ["path_missing"],
            "checks": {},
            "age_seconds": None,
            "branch": None,
        }
        has_opt_out = (module_path / ".organism_ignore").exists() if module_path.exists() else False
        would = signals["is_mature"] and not has_opt_out
        return {
            "would_adopt": would,
            "module_name": module_path.name,
            "maturity": signals,
            "has_opt_out": has_opt_out,
        }

    async def _check_maturity(self, path: Path) -> dict:
        has_manifest = (path / "pyproject.toml").exists() or (
            path / "package.json"
        ).exists()
        has_readme = (path / "README.md").exists()
        age_seconds = await self._git_first_commit_age(path)
        age_ok = age_seconds is not None and age_seconds > 24 * 3600
        branch = await self._current_branch(cwd=path.parent.parent)
        branch_ok = bool(branch) and not any(
            branch.startswith(p) for p in WIP_BRANCH_PREFIXES
        )
        is_mature = has_manifest and has_readme and age_ok and branch_ok
        checks = {
            "manifest": has_manifest,
            "readme": has_readme,
            "age_24h": age_ok,
            "branch_main": branch_ok,
        }
        missing = [k for k, v in checks.items() if not v]
        return {
            "is_mature": is_mature,
            "missing": missing,
            "checks": checks,
            "age_seconds": age_seconds,
            "branch": branch,
        }

    async def _git_first_commit_age(self, path: Path) -> float | None:
        """Return age in seconds of the first commit touching this path, or None."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "log",
                "--reverse",
                "--format=%ct",
                "--",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=path.parent.parent,  # repo root from apps/<name>/
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            lines = out.decode("utf-8", errors="replace").strip().splitlines()
            if not lines:
                return None
            first_ts = int(lines[0])
            return time.time() - first_ts
        except (asyncio.TimeoutError, ValueError, OSError):
            return None

    async def _current_branch(self, *, cwd: Path | None = None) -> str | None:
        """Get current git branch. Pass cwd to ensure correct repo lookup
        when daemon runs outside repo root.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return out.decode("utf-8", errors="replace").strip() or None
        except (asyncio.TimeoutError, OSError):
            return None
