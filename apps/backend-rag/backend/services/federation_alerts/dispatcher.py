"""Subprocess wrapper around scripts/ai-dispatch.sh + ConsiglioV1.

Per spec B1: the daemon dispatches multi-LLM via subprocess to the
existing federation CLI cascade — no aspirational ADK+A2A layer.

Per spec B9: ConsiglioV1.deliberate() is sync (subprocess.run inside).
We wrap it in asyncio.to_thread() with a hard timeout so the daemon
event loop never blocks indefinitely if 2/4 LLMs are down.

Per Golden Rule #13: ANTHROPIC_API_KEY is stripped from the subprocess
env before invoking ai-dispatch.sh. Defense-in-depth even though the
shell script does not source it.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
AI_DISPATCH_SCRIPT = PROJECT_ROOT / "scripts" / "ai-dispatch.sh"


def _safe_env() -> dict[str, str]:
    """Return os.environ with ANTHROPIC_API_KEY stripped (Golden Rule #13)."""
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


@dataclass(frozen=True)
class DispatchResult:
    """Structured result of one ai-dispatch.sh invocation."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    duration_sec: float
    timed_out: bool = False


async def dispatch_via_ai_dispatch(
    command: str,
    prompt: str,
    *,
    timeout_sec: int = 120,
    cwd: Path | None = None,
) -> DispatchResult:
    """Run scripts/ai-dispatch.sh with the given command + prompt.

    The shell script itself implements the LLM cascade (gemini 3.1 → 2.5,
    claude OAuth token rotation, etc.). We just supervise the subprocess.

    Returns DispatchResult — never raises on subprocess failure. The
    daemon decides whether a non-zero return code is a hard error or
    just degraded mode.
    """
    if not AI_DISPATCH_SCRIPT.exists():
        return DispatchResult(
            success=False,
            stdout="",
            stderr=f"ai-dispatch.sh not found at {AI_DISPATCH_SCRIPT}",
            return_code=-1,
            duration_sec=0.0,
        )

    proc = await asyncio.create_subprocess_exec(
        str(AI_DISPATCH_SCRIPT),
        command,
        prompt,
        cwd=str(cwd or PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_safe_env(),
    )

    loop = asyncio.get_event_loop()
    started_at = loop.time()
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        elapsed = loop.time() - started_at
        logger.warning(
            "ai-dispatch timeout: %s after %.1fs (rc=killed)",
            command, elapsed,
        )
        return DispatchResult(
            success=False,
            stdout="",
            stderr=f"timeout after {timeout_sec}s",
            return_code=-9,
            duration_sec=elapsed,
            timed_out=True,
        )

    elapsed = loop.time() - started_at
    return DispatchResult(
        success=(proc.returncode == 0),
        stdout=(stdout_bytes or b"").decode("utf-8", errors="replace"),
        stderr=(stderr_bytes or b"").decode("utf-8", errors="replace"),
        return_code=proc.returncode if proc.returncode is not None else -1,
        duration_sec=elapsed,
    )


async def deliberate_with_deadline(
    consiglio: Any,
    question_prompt: str,
    *,
    deadline_sec: int = 180,
    members: tuple[str, ...] | None = None,
    context_files: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap blocking ConsiglioV1.deliberate() with hard async timeout.

    Returns a normalized dict with keys:
        passed: bool          — gate_6_passes equivalent (≥3/4 active)
        active_llms: int
        claims: list[dict]    — per-claim votes
        meta: dict
        errors: dict          — present if timeout or crash

    On timeout, returns {passed: False, errors: {deadline: ...}} so
    callers can quarantine the proposal without blocking forever.
    """
    def _run_sync() -> Any:
        kwargs: dict[str, Any] = {}
        if members is not None:
            kwargs["members"] = members
        if context_files is not None:
            kwargs["context_files"] = context_files
        return consiglio.deliberate(question_prompt, **kwargs)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_sync), timeout=deadline_sec
        )
    except asyncio.TimeoutError:
        logger.warning(
            "consiglio_deadline_exceeded after %ds", deadline_sec
        )
        return {
            "passed": False,
            "active_llms": 0,
            "claims": [],
            "meta": {},
            "errors": {"deadline": f"exceeded {deadline_sec}s"},
        }
    except Exception as exc:  # noqa: BLE001 — keep daemon alive
        logger.exception("consiglio_crashed: %s", exc)
        return {
            "passed": False,
            "active_llms": 0,
            "claims": [],
            "meta": {},
            "errors": {"crash": str(exc)[:500]},
        }

    # Normalize ConsiglioResult dataclass to a plain dict
    active = int(result.meta.get("active_llms", 0))
    return {
        "passed": active >= 3,  # Gate 6 default ≥3/4
        "active_llms": active,
        "claims": [
            {"key": c.key, "value": c.value, "votes": dict(c.votes)}
            for c in result.claims
        ],
        "meta": dict(result.meta),
        "errors": {},
    }


def quick_subprocess_check() -> bool:
    """Synchronous startup probe: confirm ai-dispatch.sh is executable.

    Returns True on success. The daemon refuses to leave 'observe' mode
    if this probe fails (B1 mitigation: fail closed).
    """
    if not AI_DISPATCH_SCRIPT.exists():
        return False
    try:
        result = subprocess.run(
            [str(AI_DISPATCH_SCRIPT), "help"],
            capture_output=True,
            timeout=10,
            check=False,
            env=_safe_env(),
        )
        return result.returncode in (0, 1)  # help often exits 1; just need it to RUN
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ai-dispatch probe failed: %s", exc)
        return False


__all__ = [
    "DispatchResult",
    "dispatch_via_ai_dispatch",
    "deliberate_with_deadline",
    "quick_subprocess_check",
]
