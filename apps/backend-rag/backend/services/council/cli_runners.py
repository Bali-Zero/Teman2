"""Async CLI runners for Council proponents.

Legge 1 compliance: LLM chiamati via subprocess `claude -p`, `gemini -p`.
Eccezione esplicita: DeepSeek R1 via HTTP (SYMBIOSIS.md:176).

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

import httpx

from backend.services.observability import llm_cost_tracked, set_usage

logger = logging.getLogger(__name__)


# Golden Rule #10: module-level lazy singleton AsyncClient for the
# DeepSeek HTTP runner. Lifespan-closed via close_council_runner_client().
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_council_runner_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


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
    async def run(self, prompt: str, timeout: int | None = None) -> RunnerResult:
        ...

    async def run_json(
        self, prompt: str, timeout: int | None = None,
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
            binary_path
            or shutil.which("claude")
            or "/Users/nuzantara/.local/bin/claude"
        )
        self.extra_args = extra_args or []

    # NOTE: Claude CLI uses Max OAuth flat rate — no per-call tracking needed.
    async def run(
        self, prompt: str, timeout: int | None = None,
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
        self, prompt: str, timeout: int | None = None,
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


class DeepSeekHTTPRunner(CLIRunner):
    """DeepSeek via HTTP API — Legge 1 explicit exception (SYMBIOSIS.md:176).

    Originally prototyped in the WR1 image_brainstorm agent (removed
    2026-04-22). This implementation uses httpx (async, Golden Rule 4);
    API key required.
    """

    name = "deepseek"
    default_timeout = 120

    API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEFAULT_MODEL = "deepseek-reasoner"  # R1

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise CLIRunnerError("DeepSeekHTTPRunner requires api_key")
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self._client = http_client

    @llm_cost_tracked(provider="deepseek", model_attr="model")
    async def run(
        self, prompt: str, timeout: int | None = None,
    ) -> RunnerResult:
        eff_timeout = timeout or self.default_timeout
        start = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

        client = self._client or _get_module_client(eff_timeout)

        try:
            resp = await client.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=eff_timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            if resp.status_code != 200:
                return RunnerResult(
                    runner_name=self.name,
                    prompt_chars=len(prompt),
                    ok=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                    duration_ms=duration_ms,
                )
            body = resp.json()
            usage = body.get("usage", {})
            set_usage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            )
            content = body["choices"][0]["message"]["content"]
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=True,
                output=content.strip(),
                duration_ms=duration_ms,
                meta={"model": self.model},
            )
        except Exception as exc:  # noqa: BLE001
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
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
            proc.communicate(), timeout=timeout,
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
            "%s returned rc=%s but has stdout; tolerating", name, rc,
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
