"""codex_visual_dispatch — generate full 15-asset visual bundle for a BZ dispatch.

Wraps scripts/codex_visual_orchestrator.py which produces hero+body+story+social
asset bundle in research/dispatch/<date>/codex-visuals/. HITL_ONLY because the
output goes to public-facing channels (IG/LinkedIn/Twitter) and must be reviewed
editorially.

Safety bounds:
    * Subprocess timeout: 60 minutes (15 assets × ~3min each, with parallelism)
    * Output: research/dispatch/<date>/codex-visuals/ (manifest.json + 15 PNG)
    * Topic text: 4 KB max
    * env: ANTHROPIC_API_KEY stripped

Idempotent: orchestrator skips if manifest.json already exists for the date,
unless force=True.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)


def _default_project_root() -> Path:
    """Resolve the repo root in worktrees, CI, and the canonical Pro checkout."""
    env_root = os.environ.get("NUZANTARA_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser()

    legacy_root = Path(os.path.expanduser("~/Desktop/nuzantara"))
    if legacy_root.exists():
        return legacy_root

    for parent in Path(__file__).resolve().parents:
        if (parent / "apps" / "backend-rag").exists():
            return parent

    return legacy_root


PROJECT_ROOT = _default_project_root()
ORCHESTRATOR_SCRIPT = PROJECT_ROOT / "scripts" / "codex_visual_orchestrator.py"
DISPATCH_ROOT = PROJECT_ROOT / "research" / "dispatch"
DEFAULT_TIMEOUT_SEC = 3600
MAX_TIMEOUT_SEC = 7200
MAX_TOPIC_BYTES = 4 * 1024


_STRIPPED_ENV_KEYS: frozenset[str] = frozenset({
    # Golden Rule #13 — Anthropic OAuth-only.
    "ANTHROPIC_API_KEY",
    "AWS_BEDROCK_ANTHROPIC_KEY",
    "VERTEX_AI_ANTHROPIC_KEY",
    # The visual orchestrator launches Codex (gpt-image-2 OAuth) in a loop.
    # Strip OPENAI/GEMINI/GOOGLE provider keys so the embedding-only key
    # held by backend-rag parent never leaks into a non-embedding path.
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
})


def _safe_env() -> dict[str, str]:
    """Strip provider API keys before spawning visual orchestrator.

    Same defense as codex_image_gen — OAuth-only quota for image gen,
    never leak embedding-only OPENAI_API_KEY into a billing path.
    """
    return {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV_KEYS}


@register_action("codex_visual_dispatch")
async def codex_visual_dispatch_action(
    proposal: Any,
    *,
    dry_run: bool = False,
) -> ActionResult:
    """Run codex_visual_orchestrator.py to generate the 15-asset bundle.

    proposal.action_payload may set:
        topic         (str, REQUIRED)  — topic description for the bundle
        dispatch_date (str, default today UTC YYYY-MM-DD)
        force         (bool, default False)  — regenerate even if manifest exists
        timeout_sec   (int, default 3600, max 7200)
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    topic = (payload.get("topic") or "").strip()
    if not topic:
        return ActionResult(
            success=False,
            message="missing required action_payload.topic",
            metadata={"action": "codex_visual_dispatch"},
        )

    if len(topic.encode("utf-8")) > MAX_TOPIC_BYTES:
        return ActionResult(
            success=False,
            message=f"topic exceeds {MAX_TOPIC_BYTES} byte cap",
            metadata={"action": "codex_visual_dispatch"},
        )

    if not ORCHESTRATOR_SCRIPT.exists():
        return ActionResult(
            success=False,
            message=f"orchestrator script missing: {ORCHESTRATOR_SCRIPT}",
            metadata={"action": "codex_visual_dispatch"},
        )

    dispatch_date = payload.get("dispatch_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    force = bool(payload.get("force", False))
    timeout = max(300, min(int(payload.get("timeout_sec", DEFAULT_TIMEOUT_SEC)), MAX_TIMEOUT_SEC))

    manifest_path = DISPATCH_ROOT / dispatch_date / "codex-visuals" / "manifest.json"

    args = [
        sys.executable,
        str(ORCHESTRATOR_SCRIPT),
        "--topic-text",
        topic,
        "--dispatch-date",
        dispatch_date,
    ]
    if force:
        args.append("--force")

    if dry_run:
        return ActionResult(
            success=True,
            message=f"[dry_run] would invoke codex_visual_orchestrator.py for {dispatch_date}",
            metadata={
                "action": "codex_visual_dispatch",
                "dry_run": True,
                "dispatch_date": dispatch_date,
                "force": force,
                "manifest_path": str(manifest_path),
                "topic_bytes": len(topic.encode("utf-8")),
                "timeout_sec": timeout,
            },
        )

    if manifest_path.exists() and not force:
        return ActionResult(
            success=True,
            message=f"manifest already exists for {dispatch_date} — skipping (force=False)",
            metadata={
                "action": "codex_visual_dispatch",
                "dispatch_date": dispatch_date,
                "manifest_path": str(manifest_path),
                "skipped": True,
            },
        )

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
            env=_safe_env(),
        )
    except FileNotFoundError:
        return ActionResult(
            success=False,
            message=f"python interpreter not found: {sys.executable}",
            metadata={"action": "codex_visual_dispatch"},
        )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ActionResult(
            success=False,
            message=f"visual orchestrator timed out after {timeout}s",
            metadata={"action": "codex_visual_dispatch", "timed_out": True},
        )

    duration = time.monotonic() - start

    if proc.returncode != 0 or not manifest_path.exists():
        return ActionResult(
            success=False,
            message=f"visual orchestrator exit {proc.returncode} (manifest_exists={manifest_path.exists()})",
            metadata={
                "action": "codex_visual_dispatch",
                "duration_sec": round(duration, 1),
                "returncode": proc.returncode,
                "stderr_tail": stderr.decode("utf-8", errors="replace")[:2000],
            },
        )

    # Read manifest summary
    try:
        import json as _json
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        success_count = manifest.get("assets_success", 0)
        total = manifest.get("assets_total", 0)
    except Exception:  # pragma: no cover — defensive: manifest.json corrupt
        success_count = 0
        total = 0

    return ActionResult(
        success=success_count > 0,
        message=f"generated {success_count}/{total} assets for {dispatch_date} in {duration:.0f}s",
        side_effects=(str(manifest_path),),
        metadata={
            "action": "codex_visual_dispatch",
            "duration_sec": round(duration, 1),
            "dispatch_date": dispatch_date,
            "manifest_path": str(manifest_path),
            "assets_success": success_count,
            "assets_total": total,
        },
    )
