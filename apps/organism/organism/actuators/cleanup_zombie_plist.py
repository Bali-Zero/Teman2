"""Actuator: detect + remove orphan LaunchAgent plists.

Criteria for orphan:
1. Plist file exists in ~/Library/LaunchAgents/com.balizero.*.plist
2. Its Label is NOT in `launchctl list` output
3. Its referenced script/binary does NOT exist on disk

When all 3 conditions hold -> plist is a zombie (leftover from a removed
agent). Dry-run shows candidates. Execute unloads (if loaded) + deletes.
"""
from __future__ import annotations

import asyncio
import plistlib
from pathlib import Path
from organism.actuators.base import ActuatorBase


LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
TARGET_PREFIX = "com.balizero."


class CleanupZombiePlist(ActuatorBase):
    name = "cleanup_zombie_plist"

    def __init__(self, *, launchagents_dir: Path | None = None):
        super().__init__()
        self.launchagents_dir = launchagents_dir or LAUNCHAGENTS_DIR

    async def _execute(self, params: dict) -> dict:
        zombies = await self._find_zombies()
        removed = []
        failed = {}
        for plist_path, label in zombies:
            try:
                # launchctl unload (ignore errors -- not loaded = ok)
                await self._run(["launchctl", "unload", str(plist_path)])
                plist_path.unlink()
                removed.append({"path": str(plist_path), "label": label})
            except Exception as exc:
                failed[label] = str(exc)[:200]
        return {"removed_count": len(removed), "removed": removed, "failed": failed}

    async def _dry_run(self, params: dict) -> dict:
        zombies = await self._find_zombies()
        return {
            "would_remove_count": len(zombies),
            "would_remove": [
                {"path": str(p), "label": l} for p, l in zombies
            ],
        }

    async def _find_zombies(self) -> list[tuple[Path, str]]:
        if not self.launchagents_dir.exists():
            return []
        loaded_labels = await self._loaded_labels()
        zombies: list[tuple[Path, str]] = []
        for plist_path in self.launchagents_dir.glob(f"{TARGET_PREFIX}*.plist"):
            label = plist_path.stem
            if label in loaded_labels:
                continue  # actively loaded, not a zombie
            # Parse plist to find referenced script/binary
            referenced = self._referenced_program(plist_path)
            if referenced is None:
                # Unreadable / malformed plist — skip for safety (don't auto-delete)
                continue
            if referenced.exists():
                continue  # program still exists, keep the plist
            zombies.append((plist_path, label))
        return zombies

    async def _loaded_labels(self) -> set[str]:
        rc, out, _ = await self._run(["launchctl", "list"])
        if rc != 0:
            return set()
        labels = set()
        for line in out.splitlines()[1:]:  # skip header
            parts = line.split("\t")
            if len(parts) >= 3:
                labels.add(parts[-1].strip())
        return labels

    @staticmethod
    def _referenced_program(plist_path: Path) -> Path | None:
        try:
            with plist_path.open("rb") as f:
                data = plistlib.load(f)
            program = data.get("Program") or (
                data.get("ProgramArguments", [None])[0] if data.get("ProgramArguments") else None
            )
            if program:
                return Path(program)
        except Exception:
            return None
        return None

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
