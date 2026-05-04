"""codex_overnight_queue — enqueue a long-horizon task for overnight execution.

This action writes a task spec to ~/codex-overnight/queue/ where the
codex-overnight-runner LaunchAgent will pick it up at 22:00 WITA.

It is **L2-allowed** (autonomous in production mode) because the queue
itself is non-destructive: the task just sits there until the runner
processes it. The runner has its own safeguards (8h timeout, sandbox
workspace-write, branch-isolated work, push to feature branch only).

Idempotent: same proposal_id (and therefore same idempotency_key) writes
to a deterministic filename so repeated triggers don't duplicate.

dry_run=True → returns the path it would write to + the spec content,
without touching the filesystem.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)

QUEUE_DIR = Path(os.path.expanduser("~/codex-overnight/queue"))
MAX_SPEC_BYTES = 32 * 1024
SAFE_SLUG_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _safe_slug(s: str, max_len: int = 60) -> str:
    """Make a filesystem-safe slug from arbitrary text."""
    slug = SAFE_SLUG_RE.sub("-", s.lower()).strip("-")
    return slug[:max_len] or "task"


@register_action("codex_overnight_queue")
async def codex_overnight_queue_action(
    proposal: Any,
    *,
    dry_run: bool = False,
) -> ActionResult:
    """Write a task spec to ~/codex-overnight/queue/ for overnight execution.

    proposal.action_payload may set:
        spec        (str, REQUIRED)  — full markdown task spec for Codex
        slug_hint   (str, optional)  — informative slug part of filename;
                                       falls back to proposal_id if empty.
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    spec = (payload.get("spec") or "").strip()
    if not spec:
        return ActionResult(
            success=False,
            message="missing required action_payload.spec",
            metadata={"action": "codex_overnight_queue"},
        )

    if len(spec.encode("utf-8")) > MAX_SPEC_BYTES:
        return ActionResult(
            success=False,
            message=f"spec exceeds {MAX_SPEC_BYTES} byte cap",
            metadata={"action": "codex_overnight_queue", "spec_bytes": len(spec.encode("utf-8"))},
        )

    proposal_id = str(getattr(proposal, "proposal_id", "unknown"))
    slug_hint = (payload.get("slug_hint") or proposal_id).strip()
    slug = _safe_slug(slug_hint)

    # Deterministic filename — same proposal_id always maps to same filename
    # so re-running the action is idempotent.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{slug}-{proposal_id[:12]}.md"
    target = QUEUE_DIR / filename

    if dry_run:
        return ActionResult(
            success=True,
            message=f"[dry_run] would queue overnight task at {target}",
            metadata={
                "action": "codex_overnight_queue",
                "dry_run": True,
                "target_path": str(target),
                "spec_bytes": len(spec.encode("utf-8")),
            },
        )

    try:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        # Use atomic write: write to .tmp then rename
        tmp = target.with_suffix(".md.tmp")
        tmp.write_text(spec, encoding="utf-8")
        tmp.rename(target)
    except OSError as exc:
        return ActionResult(
            success=False,
            message=f"failed to write queue file: {exc}",
            metadata={"action": "codex_overnight_queue", "target_path": str(target)},
        )

    return ActionResult(
        success=True,
        message=f"queued overnight task at {target.name}",
        side_effects=(str(target),),
        metadata={
            "action": "codex_overnight_queue",
            "target_path": str(target),
            "spec_bytes": len(spec.encode("utf-8")),
        },
    )
