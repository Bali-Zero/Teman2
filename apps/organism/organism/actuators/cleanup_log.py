"""Actuator: delete old log files under given search dirs (default ~/logs/).

Idempotent: scans `search_dirs` recursively for `*.log` whose mtime is older
than `min_age_days` (default 30), then unlinks. Returns count + bytes freed.
Missing directories are silently skipped so the actuator works in fresh
installs without tripping over.
"""
import time
from pathlib import Path

from organism.actuators.base import ActuatorBase


DEFAULT_SEARCH_DIRS = [Path.home() / "logs"]


class CleanupLog(ActuatorBase):
    name = "cleanup_log"

    def __init__(self, search_dirs: list[Path] | None = None):
        self.search_dirs = (
            search_dirs if search_dirs is not None else DEFAULT_SEARCH_DIRS
        )

    def _candidates(self, min_age_days: int) -> list[tuple[Path, int]]:
        now = time.time()
        cutoff = now - min_age_days * 86400
        results: list[tuple[Path, int]] = []
        for d in self.search_dirs:
            if not d.exists():
                continue
            for p in d.rglob("*.log"):
                try:
                    stat = p.stat()
                except OSError:
                    continue
                if stat.st_mtime < cutoff:
                    results.append((p, stat.st_size))
        return results

    async def _execute(self, params: dict) -> dict:
        min_age = int(params.get("min_age_days", 30))
        candidates = self._candidates(min_age)
        deleted = 0
        bytes_freed = 0
        for p, size in candidates:
            try:
                p.unlink()
                deleted += 1
                bytes_freed += size
            except OSError:
                # File may have been rotated/removed between scan and unlink;
                # not fatal — report what we managed.
                pass
        return {
            "deleted_count": deleted,
            "bytes_freed": bytes_freed,
            "min_age_days": min_age,
        }

    async def _dry_run(self, params: dict) -> dict:
        min_age = int(params.get("min_age_days", 30))
        candidates = self._candidates(min_age)
        return {
            "would_delete_count": len(candidates),
            "would_free_bytes": sum(s for _, s in candidates),
            "sample_paths": [str(p) for p, _ in candidates[:5]],
        }
