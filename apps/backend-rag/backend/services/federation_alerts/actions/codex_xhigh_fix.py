"""codex_xhigh_fix — invoke Codex CLI with gpt-5.5 xhigh profile to fix a P0 issue.

This action delegates a deep agentic coding task to the Codex CLI (OAuth Pro $200,
NO API key — Golden Rule #13 compliant). It is HITL_ONLY: production execution
always requires Telegram approval, regardless of FAD mode.

Safety bounds:
    * Subprocess timeout: 30 minutes hard cap (Codex xhigh long-horizon limit)
    * Sandbox: workspace-write (set in ~/.codex/config.toml profile xhigh)
    * env: ANTHROPIC_API_KEY stripped (defense-in-depth even though Codex
      doesn't read it)
    * Output: structured ActionResult — caller (FAD daemon) decides whether to
      open PR, commit, etc. This action does NOT push to git itself.

dry_run=True → returns the full prompt that WOULD be sent to Codex without
spawning the subprocess. Useful for offline review by the 4-LLM Consiglio.

Spec: docs/superpowers/specs/2026-04-30-federation-alert-dispatcher.md
       PR #393/#395/#397 (FAD shipping)
       PR (this one) — adds Codex 5.5 capability via existing dispatcher pattern
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 1800  # 30 min — matches ai-dispatch.sh codex-xhigh
MAX_TIMEOUT_SEC = 3600       # 60 min — hard ceiling for action_payload override
MAX_PROMPT_BYTES = 32 * 1024  # 32 KB prompt cap (Codex CLI handles ~64K but be conservative)


_STRIPPED_ENV_KEYS: frozenset[str] = frozenset({
    # Golden Rule #13 — Anthropic OAuth-only. Never let key into subprocess.
    "ANTHROPIC_API_KEY",
    "AWS_BEDROCK_ANTHROPIC_KEY",
    "VERTEX_AI_ANTHROPIC_KEY",
    # Codex CLI uses OAuth (Pro $200), not API key. The parent backend-rag
    # process keeps OPENAI_API_KEY for the frozen embedding model
    # (text-embedding-3-small), but that key MUST NOT leak into a Codex
    # subprocess where it would create a non-embedding text/code/image
    # billing path. Same defense for Gemini paid tiers (we use OAuth).
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
})


def _safe_env() -> dict[str, str]:
    """Strip provider API keys from subprocess env.

    Codex CLI uses OAuth (Pro $200 quota); embedding-only OPENAI_API_KEY
    must stay scoped to backend-rag and NEVER leak into Codex subprocess
    which could open a non-embedding billing path. Defense-in-depth for
    Anthropic, OpenAI, Google providers.
    """
    return {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV_KEYS}


@register_action("codex_xhigh_fix")
async def codex_xhigh_fix_action(
    proposal: Any,
    *,
    dry_run: bool = False,
) -> ActionResult:
    """Run Codex CLI with profile=xhigh to attempt a deep agentic fix.

    proposal.action_payload may set:
        prompt           (str, REQUIRED)  — task description for Codex
        timeout_sec      (int, default 1800, max 3600)
        cwd              (str, default $HOME/Desktop/nuzantara)

    The prompt is wrapped with hard rules + hard-rule reminder before being
    passed to Codex. The action does NOT mutate git state — Codex itself
    decides whether to commit. The FAD daemon is responsible for converting
    the resulting commit (if any) into a PR.
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    raw_prompt = payload.get("prompt", "").strip()
    if not raw_prompt:
        return ActionResult(
            success=False,
            message="missing required action_payload.prompt",
            metadata={"action": "codex_xhigh_fix"},
        )

    if len(raw_prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        return ActionResult(
            success=False,
            message=f"prompt exceeds {MAX_PROMPT_BYTES} byte cap",
            metadata={"action": "codex_xhigh_fix", "prompt_bytes": len(raw_prompt.encode("utf-8"))},
        )

    timeout = max(60, min(int(payload.get("timeout_sec", DEFAULT_TIMEOUT_SEC)), MAX_TIMEOUT_SEC))
    cwd = Path(payload.get("cwd") or os.path.expanduser("~/Desktop/nuzantara"))

    if not cwd.exists():
        return ActionResult(
            success=False,
            message=f"cwd does not exist: {cwd}",
            metadata={"action": "codex_xhigh_fix"},
        )

    # Wrap prompt with hard rules — Codex sees these even when invoked via FAD
    framed_prompt = (
        f"You are receiving an autonomous remediation task from the Federation "
        f"Alert Dispatcher (FAD).\n\n"
        f"Proposal ID: {getattr(proposal, 'proposal_id', 'unknown')}\n"
        f"Severity: {getattr(proposal, 'severity', 'unknown')}\n\n"
        f"Hard rules (CRITICAL, do NOT bypass):\n"
        f"- NO ANTHROPIC_API_KEY usage anywhere\n"
        f"- NO new OPENAI_API_KEY usage beyond existing embedding model\n"
        f"- NO --no-verify, NO --force-push\n"
        f"- workspace-write sandbox only\n"
        f"- Read AGENTS.md (root + path-specific) for project rules\n\n"
        f"Task:\n{raw_prompt}\n"
    )

    if dry_run:
        return ActionResult(
            success=True,
            message=f"[dry_run] would invoke codex --profile xhigh exec (timeout={timeout}s)",
            metadata={
                "action": "codex_xhigh_fix",
                "dry_run": True,
                "framed_prompt_bytes": len(framed_prompt.encode("utf-8")),
                "timeout_sec": timeout,
                "cwd": str(cwd),
            },
        )

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "codex",
            "--profile",
            "xhigh",
            "exec",
            framed_prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=_safe_env(),
        )
    except FileNotFoundError:
        return ActionResult(
            success=False,
            message="codex CLI not installed",
            metadata={"action": "codex_xhigh_fix"},
        )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ActionResult(
            success=False,
            message=f"codex xhigh timed out after {timeout}s",
            metadata={"action": "codex_xhigh_fix", "timed_out": True},
        )

    duration = time.monotonic() - start
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")[:2000]

    if proc.returncode != 0:
        return ActionResult(
            success=False,
            message=f"codex xhigh exit {proc.returncode}",
            metadata={
                "action": "codex_xhigh_fix",
                "duration_sec": round(duration, 1),
                "returncode": proc.returncode,
                "stderr_tail": err,
            },
        )

    return ActionResult(
        success=True,
        message=f"codex xhigh completed in {duration:.0f}s",
        side_effects=(),  # Codex itself decides whether to commit; FAD daemon inspects git afterwards
        metadata={
            "action": "codex_xhigh_fix",
            "duration_sec": round(duration, 1),
            "stdout_bytes": len(out),
            "returncode": 0,
        },
    )
