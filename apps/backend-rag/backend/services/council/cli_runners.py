"""Async CLI runners for Council proponents.

Legge 1 compliance: LLM chiamati via subprocess `claude -p`, `gemini -p`,
`kimi -p`. No HTTP exception is wired here anymore — the DeepSeek V4 Pro
HTTP runner (SYMBIOSIS.md:176's "unica eccezione") was retired 2026-07-19
(Zero: pre-authorization REVOKED, key balance dead, HTTP-402). Its voting
seat is replaced by KimiCLIRunner (Moonshot Kimi K3, OAuth device-code,
no API key) per CLAUDE.md §5 "replacement refuter seat is Kimi K3".

Each runner:
- is async (asyncio.create_subprocess_exec) to run 3 proponents in parallel
- strips ANTHROPIC_API_KEY before claude calls (OAuth Max conflict)
- sets CLAUDE_PLUGIN_ROOT=/dev/null to avoid SessionEnd hook rc=1
- times out cleanly, never leaves zombies
- returns RunnerResult (never raises on model error; raises only on missing binary)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class CLIRunnerError(RuntimeError):
    """Raised when a runner cannot execute (binary missing, fatal subprocess error)."""


@dataclass
class RunnerResult:
    runner_name: str
    prompt_chars: int
    ok: bool
    output: str = ""
    error: str | None = None
    duration_ms: float = 0.0
    returncode: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class CLIRunner(ABC):
    """Abstract runner — one model, one invocation."""

    name: str
    default_timeout: int = 180

    @abstractmethod
    async def run(self, prompt: str, timeout: int | None = None) -> RunnerResult: ...

    async def run_json(
        self,
        prompt: str,
        timeout: int | None = None,
    ) -> tuple[dict[str, Any] | None, RunnerResult]:
        """Convenience: run and parse JSON from output (tolerant to markdown fences)."""
        result = await self.run(prompt, timeout=timeout)
        if not result.ok or not result.output:
            return None, result
        parsed = _extract_json(result.output)
        return parsed, result


class ClaudeCLIRunner(CLIRunner):
    """Runs `claude -p <prompt>` via OAuth Max subscription (no API key).

    Strips ANTHROPIC_API_KEY: it conflicts with OAuth token auth.
    Sets CLAUDE_PLUGIN_ROOT=/dev/null: disables SessionEnd hook which
    fires on every subprocess call and causes rc=1 even on success.
    Uses absolute path so launchd / cron (limited PATH) can find the binary.
    """

    name = "claude"
    default_timeout = 300

    def __init__(
        self,
        binary_path: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        self.binary_path = (
            binary_path or shutil.which("claude") or "/Users/nuzantara/.local/bin/claude"
        )
        self.extra_args = extra_args or []

    # NOTE: Claude CLI uses Max OAuth flat rate — no per-call tracking needed.
    async def run(
        self,
        prompt: str,
        timeout: int | None = None,
    ) -> RunnerResult:
        eff_timeout = timeout or self.default_timeout
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["CLAUDE_PLUGIN_ROOT"] = "/dev/null"
        cmd = [self.binary_path, "-p", prompt, *self.extra_args]
        return await _run_subprocess(
            name=self.name,
            cmd=cmd,
            prompt=prompt,
            env=env,
            timeout=eff_timeout,
            tolerate_nonzero_with_stdout=True,  # SessionEnd hook rc=1
        )


class GeminiCLIRunner(CLIRunner):
    """Runs `gemini -p <prompt>`. No env stripping; uses user auth."""

    name = "gemini"
    default_timeout = 240

    def __init__(self, binary_path: str | None = None) -> None:
        self.binary_path = binary_path or shutil.which("gemini") or "gemini"

    # TODO: tracking for paid Gemini API path requires subprocess stdout token
    # parsing — deferred to follow-up. The CLI subprocess does not return
    # structured usage data, so token counts cannot be reliably extracted here.
    async def run(
        self,
        prompt: str,
        timeout: int | None = None,
    ) -> RunnerResult:
        eff_timeout = timeout or self.default_timeout
        cmd = [self.binary_path, "-p", prompt]
        return await _run_subprocess(
            name=self.name,
            cmd=cmd,
            prompt=prompt,
            env=dict(os.environ),
            timeout=eff_timeout,
        )


class KimiCLIRunner(CLIRunner):
    """Runs `kimi -p <prompt> -m kimi-code/k3`. No API key — Moonshot Kimi
    OAuth device-code login (Allegro flat subscription).

    Replaces DeepSeekHTTPRunner as the third council voice. DeepSeek V4 Pro
    was RETIRED 2026-07-19 (Zero: pre-authorization revoked, key balance
    dead — HTTP-402); CLAUDE.md §5 names Kimi K3 as the sanctioned
    replacement refuter/second-opinion seat. Uses the subprocess pattern
    (Legge 1 CLI-only), not HTTP — no cost-tracking decorator needed, same
    as ClaudeCLIRunner/GeminiCLIRunner (flat-subscription, no per-token
    billing to record).
    """

    name = "kimi"
    default_timeout = 240

    DEFAULT_MODEL = "kimi-code/k3"

    def __init__(
        self,
        binary_path: str | None = None,
        model: str | None = None,
    ) -> None:
        self.binary_path = (
            binary_path
            or shutil.which("kimi")
            or os.path.expanduser("~/.kimi-code/bin/kimi")
        )
        self.model = model or self.DEFAULT_MODEL

    async def run(
        self,
        prompt: str,
        timeout: int | None = None,
    ) -> RunnerResult:
        eff_timeout = timeout or self.default_timeout
        cmd = [self.binary_path, "-p", prompt, "-m", self.model]
        return await _run_subprocess(
            name=self.name,
            cmd=cmd,
            prompt=prompt,
            env=dict(os.environ),
            timeout=eff_timeout,
        )


# ── Helpers ─────────────────────────────────────────────────────────────


async def _run_subprocess(
    *,
    name: str,
    cmd: list[str],
    prompt: str,
    env: dict[str, str],
    timeout: int,
    tolerate_nonzero_with_stdout: bool = False,
) -> RunnerResult:
    start = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as exc:
        raise CLIRunnerError(f"{name} binary not found: {cmd[0]}") from exc

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return RunnerResult(
            runner_name=name,
            prompt_chars=len(prompt),
            ok=False,
            error=f"timeout after {timeout}s",
            duration_ms=(time.perf_counter() - start) * 1000,
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
    duration_ms = (time.perf_counter() - start) * 1000

    rc = proc.returncode
    if rc == 0 and stdout:
        return RunnerResult(
            runner_name=name,
            prompt_chars=len(prompt),
            ok=True,
            output=stdout,
            duration_ms=duration_ms,
            returncode=rc,
        )
    if tolerate_nonzero_with_stdout and stdout:
        logger.debug(
            "%s returned rc=%s but has stdout; tolerating",
            name,
            rc,
        )
        return RunnerResult(
            runner_name=name,
            prompt_chars=len(prompt),
            ok=True,
            output=stdout,
            duration_ms=duration_ms,
            returncode=rc,
            meta={"tolerated_rc": rc},
        )
    return RunnerResult(
        runner_name=name,
        prompt_chars=len(prompt),
        ok=False,
        error=stderr[:300] or f"rc={rc} with empty stdout",
        duration_ms=duration_ms,
        returncode=rc,
    )


def _extract_json(response: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction — tolerant to markdown fences + prose."""
    if not response:
        return None

    candidates: list[str] = []
    if "```json" in response:
        try:
            candidates.append(response.split("```json", 1)[1].split("```", 1)[0])
        except IndexError:
            pass
    if "```" in response:
        try:
            candidates.append(response.split("```", 1)[1].split("```", 1)[0])
        except IndexError:
            pass
    if "{" in response and "}" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        if end > start:
            candidates.append(response[start:end])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None
