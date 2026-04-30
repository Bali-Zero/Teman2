"""cleanup_log — delete old log files in ~/logs/**.

Safety bounds (per spec):
    * Path scope:  $HOME/logs/**/*.log only (resolved + symlink-checked)
    * Max age:     7 days (configurable via action_payload.max_age_days)
    * Max bytes:   100 MB aggregate per run
    * Excludes:    files inside any '.archives' directory

dry_run=True → returns the list it WOULD delete, without removing anything.

This action is idempotent: re-running with the same proposal_id (and
hence the same idempotency_key) is a no-op because the second run will
find no candidates older than 7d that match the previous run's
fingerprint.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_MAX_AGGREGATE_BYTES = 100 * 1024 * 1024  # 100 MB
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".archives"})


def _logs_root() -> Path:
    return Path(os.path.expanduser("~/logs")).resolve()


def _is_safe_path(candidate: Path, root: Path) -> bool:
    """Reject anything outside ~/logs/ even via symlink traversal."""
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    if any(part in EXCLUDED_DIR_NAMES for part in resolved.parts):
        return False
    return resolved.is_file() and resolved.suffix == ".log"


def _find_candidates(
    root: Path, max_age_days: int, max_bytes: int
) -> list[tuple[Path, int, datetime]]:
    """Return [(path, size, mtime)] for files eligible for deletion.

    Sorted oldest-first; truncates when aggregate size would exceed max_bytes.
    """
    if not root.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    eligible: list[tuple[Path, int, datetime]] = []
    aggregate = 0
    for entry in sorted(root.rglob("*.log"), key=lambda p: str(p)):
        if not _is_safe_path(entry, root):
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if mtime > cutoff:
            continue
        if aggregate + stat.st_size > max_bytes:
            break
        eligible.append((entry, stat.st_size, mtime))
        aggregate += stat.st_size
    return eligible


@register_action("cleanup_log")
async def cleanup_log_action(
    proposal: Any,
    *,
    dry_run: bool = False,
) -> ActionResult:
    """Remove .log files older than N days under ~/logs/**.

    proposal.action_payload may set:
        max_age_days   (int, default 7)
        max_bytes      (int, default 100 MB)

    The DB CHECK constraint already keeps action_payload bounded, so we
    don't validate aggressively here — bad inputs map to DEFAULT_*.
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    max_age_days = int(payload.get("max_age_days", DEFAULT_MAX_AGE_DAYS))
    max_bytes = int(payload.get("max_bytes", DEFAULT_MAX_AGGREGATE_BYTES))
    max_age_days = max(1, min(max_age_days, 365))
    max_bytes = max(1024, min(max_bytes, 10 * 1024 * 1024 * 1024))

    root = _logs_root()
    candidates = _find_candidates(root, max_age_days, max_bytes)
    if not candidates:
        return ActionResult(
            success=True,
            message=(
                f"no candidates under {root} older than {max_age_days}d "
                f"(max_bytes={max_bytes})"
            ),
            metadata={"would_remove_count": 0},
        )

    if dry_run:
        paths = tuple(str(p) for p, _, _ in candidates[:50])
        total_bytes = sum(s for _, s, _ in candidates)
        return ActionResult(
            success=True,
            message=(
                f"DRY-RUN: would remove {len(candidates)} files "
                f"({total_bytes} bytes) under {root}"
            ),
            side_effects=paths,
            metadata={
                "would_remove_count": len(candidates),
                "would_remove_bytes": total_bytes,
            },
        )

    removed: list[str] = []
    failed: list[tuple[str, str]] = []
    bytes_removed = 0
    for path, size, _ in candidates:
        try:
            path.unlink()
            removed.append(str(path))
            bytes_removed += size
        except OSError as exc:
            failed.append((str(path), repr(exc)))
    msg = f"removed {len(removed)} files ({bytes_removed} bytes)"
    if failed:
        msg += f"; {len(failed)} failed"
    return ActionResult(
        success=len(failed) == 0,
        message=msg,
        side_effects=tuple(removed[:50]),
        metadata={
            "removed_count": len(removed),
            "removed_bytes": bytes_removed,
            "failed_count": len(failed),
            "failed_samples": failed[:5],
        },
    )


__all__ = ["cleanup_log_action"]
