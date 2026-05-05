"""codex_image_gen — generate a single image via Codex CLI built-in $imagegen.

Uses Codex CLI (gpt-image-2 OAuth, Pro $200 quota — no API key, no
per-call billing). HITL_ONLY because generated images may be public-facing
(IG/LinkedIn/Twitter cards) and need editorial approval.

Safety bounds:
    * Subprocess timeout: 10 minutes
    * Output dir: $HOME/Desktop/nuzantara/research/dispatch/<date>/codex-images/
                  (resolved + symlink-checked)
    * Prompt size: 8 KB max
    * env: ANTHROPIC_API_KEY stripped (defense-in-depth)

dry_run=True → returns full prompt + target output path without spawning Codex.
"""
from __future__ import annotations

import asyncio
import logging
import os
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 600
MAX_TIMEOUT_SEC = 1200
MAX_PROMPT_BYTES = 8 * 1024
DISPATCH_ROOT = Path(os.path.expanduser("~/Desktop/nuzantara/research/dispatch"))
SAFE_NAME_CHARS = string.ascii_letters + string.digits + "-_"


_STRIPPED_ENV_KEYS: frozenset[str] = frozenset({
    # Golden Rule #13 — Anthropic OAuth-only.
    "ANTHROPIC_API_KEY",
    "AWS_BEDROCK_ANTHROPIC_KEY",
    "VERTEX_AI_ANTHROPIC_KEY",
    # Codex CLI uses OAuth Pro $200 quota for gpt-image-2; the parent
    # process's OPENAI_API_KEY (embedding-only) MUST NOT leak into the
    # image-gen subprocess where it would open a per-call billing path.
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
})


def _safe_env() -> dict[str, str]:
    """Strip provider API keys before spawning Codex subprocess.

    Mirrors codex_xhigh_fix._safe_env. The backend-rag parent process
    legitimately holds OPENAI_API_KEY for text-embedding-3-small, but
    image generation must run via Codex OAuth — never per-call billing.
    """
    return {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV_KEYS}


def _safe_name(s: str, default: str = "asset") -> str:
    cleaned = "".join(c if c in SAFE_NAME_CHARS else "-" for c in s)
    cleaned = cleaned.strip("-")[:80]
    return cleaned or default


def _is_path_safe(target: Path, root: Path) -> bool:
    """Reject path traversal even via symlink — must stay under root."""
    try:
        resolved_root = root.resolve()
        resolved_parent = target.parent.resolve()
        resolved_parent.relative_to(resolved_root)
    except (ValueError, OSError):
        return False
    return True


@register_action("codex_image_gen")
async def codex_image_gen_action(
    proposal: Any,
    *,
    dry_run: bool = False,
) -> ActionResult:
    """Invoke Codex CLI with $imagegen tag.

    proposal.action_payload may set:
        prompt        (str, REQUIRED)  — image description
        asset_name    (str, default 'asset')  — filename slug (no extension)
        dispatch_date (str, default today UTC YYYY-MM-DD)
        timeout_sec   (int, default 600, max 1200)
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return ActionResult(
            success=False,
            message="missing required action_payload.prompt",
            metadata={"action": "codex_image_gen"},
        )

    if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        return ActionResult(
            success=False,
            message=f"prompt exceeds {MAX_PROMPT_BYTES} byte cap",
            metadata={"action": "codex_image_gen"},
        )

    asset_name = _safe_name(payload.get("asset_name", "asset"))
    dispatch_date = payload.get("dispatch_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timeout = max(60, min(int(payload.get("timeout_sec", DEFAULT_TIMEOUT_SEC)), MAX_TIMEOUT_SEC))

    out_dir = DISPATCH_ROOT / dispatch_date / "codex-images"
    out_path = out_dir / f"{asset_name}.png"

    if not _is_path_safe(out_path, DISPATCH_ROOT):
        return ActionResult(
            success=False,
            message="resolved output path escapes dispatch root",
            metadata={"action": "codex_image_gen", "target_path": str(out_path)},
        )

    framed_prompt = (
        f"$imagegen {prompt}\n\n"
        f"Save the generated image to: {out_path}"
    )

    if dry_run:
        return ActionResult(
            success=True,
            message=f"[dry_run] would generate image to {out_path}",
            metadata={
                "action": "codex_image_gen",
                "dry_run": True,
                "target_path": str(out_path),
                "framed_prompt_bytes": len(framed_prompt.encode("utf-8")),
                "timeout_sec": timeout,
            },
        )

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ActionResult(
            success=False,
            message=f"failed to create output dir: {exc}",
            metadata={"action": "codex_image_gen", "target_dir": str(out_dir)},
        )

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "codex",
            "--profile",
            "image",
            "exec",
            framed_prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(out_dir),
            env=_safe_env(),
        )
    except FileNotFoundError:
        return ActionResult(
            success=False,
            message="codex CLI not installed",
            metadata={"action": "codex_image_gen"},
        )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ActionResult(
            success=False,
            message=f"codex image gen timed out after {timeout}s",
            metadata={"action": "codex_image_gen", "timed_out": True},
        )

    duration = time.monotonic() - start

    # Verify output produced
    if not out_path.exists() or out_path.stat().st_size < 1024:
        # Fallback: scan output dir for any newer png Codex may have named differently
        candidates = sorted(
            (p for p in out_dir.glob("*.png") if p.stat().st_mtime > start),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            try:
                candidates[0].rename(out_path)
            except OSError:
                pass

    if not out_path.exists() or out_path.stat().st_size < 1024:
        return ActionResult(
            success=False,
            message="no image produced (file missing or under 1KB)",
            metadata={
                "action": "codex_image_gen",
                "duration_sec": round(duration, 1),
                "returncode": proc.returncode,
                "stderr_tail": stderr.decode("utf-8", errors="replace")[:1000],
            },
        )

    return ActionResult(
        success=True,
        message=f"image generated at {out_path.name} ({out_path.stat().st_size} bytes)",
        side_effects=(str(out_path),),
        metadata={
            "action": "codex_image_gen",
            "duration_sec": round(duration, 1),
            "target_path": str(out_path),
            "size_bytes": out_path.stat().st_size,
        },
    )
