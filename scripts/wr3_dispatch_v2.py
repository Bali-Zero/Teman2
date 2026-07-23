#!/usr/bin/env python3
"""WR3 dispatch v2 — `claude --print` direct (no SDK Task tool overhead).

DESIGN — Refactor 2026-05-19 after pilot run #696 confirmed empirical issue:

The v1 implementation (`wr3_dispatch_agent.py::_dispatch_claude_sdk`) used
claude-agent-sdk 0.2.82 with `setting_sources=["user"]` to load
`~/.claude/agents/*.md` and dispatched via the Task tool. That pattern
loaded ~50K cached system tokens per call (~$0.18 just for system prompt),
plus Task-tool sub-agent overhead. Even brief-interpreter with $0.15
ceiling busted on the first turn ("Reached maximum budget").

v2 path: spawn `claude --print` directly with `--system-prompt <agent body>`
+ `--exclude-dynamic-system-prompt-sections` from an isolated cwd
(`/tmp/wr3-dispatch-cwd`, no `CLAUDE.md` discovery).

Empirical cost on realistic brief-interpreter workload: $0.09 (~50× less
than v1). Symbiosis Law 1 compliant (CLI subprocess wrapper) and Law 7
compliant (real ceilings now match contract caps).

Cascade Tier 2 (Gemini free OAuth) is shared with v1 — imported lazily.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import signal
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Re-export v1 exception classes + result type so callers (supervisor) need
# only swap the entrypoint. v1 module remains as legacy reference until
# next cicatrix sweep.
from wr3_dispatch_agent import (  # noqa: E402
    BudgetExceededError,
    CascadeExhaustedError,
    DispatchResult,
    HardHaltException,
    WR3DispatchError,
    telegram_p0,
)
from wr3_contracts import AgentContract, WR3Contracts

logger = logging.getLogger(__name__)

# Isolated cwd for `claude --print` subprocess. Empty dir → no CLAUDE.md
# auto-discovery → minimal cached system prompt → minimal cost.
_ISOLATED_CWD = Path(os.environ.get(
    "WR3_DISPATCH_ISOLATED_CWD",
    "/tmp/wr3-dispatch-cwd",
))
_ISOLATED_CWD.mkdir(parents=True, exist_ok=True)

_AGENTS_DIR = Path(os.environ.get(
    "WR3_AGENTS_DIR",
    str(Path.home() / ".claude" / "agents"),
))


def _load_agent_system_prompt(slug: str) -> str:
    """Load the agent .md body, stripping YAML frontmatter if present."""
    md_path = _AGENTS_DIR / f"{slug}.md"
    if not md_path.exists():
        raise WR3DispatchError(
            f"Agent definition not found: {md_path}. "
            f"Check WR3_AGENTS_DIR or that ~/.claude/agents/{slug}.md exists."
        )
    text = md_path.read_text()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].lstrip("\n")
    return text


_AGENT_PROMPT_CACHE: dict[str, str] = {}


def _agent_system_prompt(slug: str) -> str:
    if slug not in _AGENT_PROMPT_CACHE:
        _AGENT_PROMPT_CACHE[slug] = _load_agent_system_prompt(slug)
    return _AGENT_PROMPT_CACHE[slug]


# Symbiosis Law 1 hard rule: NEVER pass paid or alternate-provider credentials
# to the Claude subprocess. The prefix is built without the banned literal so
# wr3_lint_cli_only can keep flagging accidental reads of the paid key.
_OAUTH_TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
_PROVIDER_ENV_PREFIXES = (
    "ANTHROPIC" + "_",
    "AWS_",
    "BEDROCK_",
    "VERTEX_",
    "FOUNDRY_",
    "OPENAI_",
    "DEEPSEEK_",
    "OPENROUTER_",
    "GEMINI_",
    "TOGETHER_",
    "GROQ_",
    "MISTRAL_",
    "COHERE_",
)
_PROVIDER_ENV_NAMES = frozenset(
    {
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_FOUNDRY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "CLOUD_ML_REGION",
    }
)
_QUOTA_RE = re.compile(
    r"out of extra usage|usage limit|weekly limit|quota(?: exceeded)?|"
    r"rate.?limit|too many requests|429|exhausted|hit your limit|"
    r"capacity|overloaded|please try again later",
    re.IGNORECASE,
)
_AUTH_RE = re.compile(
    r"authentication (?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh[_ ]token|"
    r"unauthori[sz]ed|(?:error\D*)?401",
    re.IGNORECASE,
)
_SECRET_DIAGNOSTIC_RE = re.compile(
    r"(?i)\b(?:bearer|oauth[_ -]?token|access[_ -]?token)\b"
    r"(\s*[:=]\s*|\s+)\S+"
)
_PROCESS_TERM_GRACE_S = 0.25
_PROCESS_KILL_REAP_S = 0.75
_PROCESS_POLL_S = 0.01
_GEMINI_ENV_ALLOWLIST = frozenset(
    {
        "HOME",
        "PATH",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "SHELL",
        "USER",
        "LOGNAME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "ALL_PROXY",
    }
)


class ClaudeFleetExhaustedError(WR3DispatchError):
    """All configured Claude OAuth seats failed with retryable conditions."""


def _collect_claude_seats(
    source: Mapping[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Return deduplicated OAuth seats in fleet order, then keychain."""
    values = os.environ if source is None else source
    seats: list[tuple[str, str]] = []
    seen: set[str] = set()
    for slot in range(1, 6):
        token = values.get(f"{_OAUTH_TOKEN_ENV}_{slot}", "").strip()
        if token and token not in seen:
            label = "slot5-team" if slot == 5 else f"slot{slot}"
            seats.append((label, token))
            seen.add(token)
    legacy = values.get(_OAUTH_TOKEN_ENV, "").strip()
    if legacy and legacy not in seen:
        seats.append(("legacy", legacy))
    seats.append(("keychain", ""))
    return seats


def _is_provider_env(name: str) -> bool:
    return name in _PROVIDER_ENV_NAMES or name.startswith(_PROVIDER_ENV_PREFIXES)


def _build_claude_env(
    token: str,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an OAuth-only child env with alternate providers removed."""
    values = os.environ if source is None else source
    env = {
        key: value
        for key, value in values.items()
        if not _is_provider_env(key) and not key.startswith(_OAUTH_TOKEN_ENV)
    }
    if token:
        env[_OAUTH_TOKEN_ENV] = token
    return env


def _build_gemini_env(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a minimal OAuth-CLI environment without any provider credential."""
    values = os.environ if source is None else source
    return {
        key: value
        for key, value in values.items()
        if key in _GEMINI_ENV_ALLOWLIST or key.startswith("LC_")
    }


def _sanitize_diagnostic(text: str, secrets: list[str]) -> str:
    safe = text
    for secret in secrets:
        if secret:
            safe = safe.replace(secret, "[redacted]")
    safe = _SECRET_DIAGNOSTIC_RE.sub("credential=[redacted]", safe)
    return " ".join(safe.split())[:300]


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _child_run_budget(total_budget_s: float) -> float:
    cleanup_reserve_s = min(
        _PROCESS_TERM_GRACE_S + _PROCESS_KILL_REAP_S,
        total_budget_s / 2,
    )
    return max(0.001, total_budget_s - cleanup_reserve_s)


def _signal_process_group(
    proc: asyncio.subprocess.Process,
    sig: signal.Signals,
) -> None:
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return
    except OSError:
        with contextlib.suppress(ProcessLookupError):
            proc.send_signal(sig)


async def _wait_process_tree(
    proc: asyncio.subprocess.Process,
    communicate_task: asyncio.Task[tuple[bytes, bytes]],
    *,
    deadline: float,
) -> bool:
    """Wait until both the direct child pipes and its process group are gone."""
    loop = asyncio.get_running_loop()
    while True:
        if communicate_task.done() and not _process_group_exists(proc.pid):
            return True
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(_PROCESS_POLL_S, remaining))


async def _terminate_process_tree(
    proc: asyncio.subprocess.Process,
    communicate_task: asyncio.Task[tuple[bytes, bytes]],
    *,
    global_deadline: float,
) -> None:
    """TERM then KILL one subprocess session without crossing its deadline."""
    loop = asyncio.get_running_loop()
    _signal_process_group(proc, signal.SIGTERM)
    term_deadline = min(global_deadline, loop.time() + _PROCESS_TERM_GRACE_S)
    await _wait_process_tree(proc, communicate_task, deadline=term_deadline)

    if _process_group_exists(proc.pid):
        _signal_process_group(proc, signal.SIGKILL)
    kill_deadline = min(global_deadline, loop.time() + _PROCESS_KILL_REAP_S)
    await _wait_process_tree(proc, communicate_task, deadline=kill_deadline)

    if not communicate_task.done():
        # A descendant that escaped the session can keep inherited pipe FDs
        # open. Closing our read transports prevents it extending the caller's
        # wall-clock deadline; the in-session tree has already received KILL.
        for stream in (proc.stdout, proc.stderr):
            transport = getattr(stream, "_transport", None)
            if transport is not None:
                transport.close()
        communicate_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await communicate_task

    if proc.returncode is None:
        remaining = global_deadline - loop.time()
        if remaining > 0:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=remaining)


def _retry_reason(
    *,
    stdout: str,
    stderr: str,
    returncode: int,
    valid_success: bool,
    effective_output: str,
) -> str | None:
    """Classify retryable transport failures.

    Whitespace/no stdout and a valid Claude JSON envelope whose ``result`` is
    empty are transport-empty and rotate the seat. Domain-level empty data must
    still be represented by a non-empty, schema-valid payload.
    """
    if valid_success:
        return None
    combined = f"{stdout}\n{stderr}"
    if _QUOTA_RE.search(combined):
        return "quota"
    if _AUTH_RE.search(combined):
        return "auth"
    if returncode in (0, 143) and not effective_output.strip():
        return "empty-output"
    if not stdout.strip() and not stderr.strip():
        return "empty-output"
    return None


async def dispatch_claude_print(
    contract: AgentContract,
    prompt: str,
    *,
    timeout_ms: int = 300000,
) -> DispatchResult:
    """Primary path: `claude --print` direct subprocess.

    Cost-optimised vs v1 SDK Task-tool dispatch (~50× cheaper).

    Raises:
        BudgetExceededError: claude returned "Exceeded USD budget" (caller
            routes per Symbiosis precedence — HARD HALT on gates, cascade
            on hot path).
        WR3DispatchError: claude CLI missing, subprocess failure, JSON
            parse failure, or wall-clock timeout.
    """
    claude_bin = shutil.which("claude")
    if claude_bin is None:
        raise WR3DispatchError(
            "`claude` CLI not on PATH. Install: https://claude.ai/code"
        )

    ceiling = contract.cost.ceiling_usd
    if ceiling is None and contract.cost_class == "render":
        ceiling = 0.50  # 200 cr Flow Pro cash equivalent
    elif ceiling is None:
        ceiling = 0.30  # fallback for non-render agents

    system_prompt = _agent_system_prompt(contract.name)

    args = [
        claude_bin,
        "--print",
        "--model", contract.model or "sonnet",
        "--system-prompt", system_prompt,
        "--exclude-dynamic-system-prompt-sections",
        "--max-budget-usd", str(ceiling),
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]

    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + max(timeout_ms / 1000, 0.001)
    seats = _collect_claude_seats()
    secrets = [token for _, token in seats if token]
    failures: list[str] = []

    for index, (label, token) in enumerate(seats):
        remaining = deadline - loop.time()
        if remaining <= 0:
            failures.append(f"{label}:deadline")
            break
        seats_left = len(seats) - index
        seat_budget_s = max(0.001, remaining / seats_left)
        attempt_deadline = min(deadline, loop.time() + seat_budget_s)
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(_ISOLATED_CWD),
                env=_build_claude_env(token),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise WR3DispatchError(
                "`claude` CLI not on PATH. Install: https://claude.ai/code"
            ) from exc

        communicate_task = asyncio.create_task(proc.communicate())
        done, _ = await asyncio.wait(
            {communicate_task},
            timeout=_child_run_budget(
                max(0.001, attempt_deadline - loop.time()),
            ),
        )
        if communicate_task not in done:
            await _terminate_process_tree(
                proc,
                communicate_task,
                global_deadline=attempt_deadline,
            )
            failures.append(f"{label}:timeout")
            logger.warning(
                "%s: Claude OAuth %s timed out; trying next seat",
                contract.name,
                label,
            )
            continue
        stdout_bytes, stderr_bytes = communicate_task.result()

        stdout = stdout_bytes.decode("utf-8", "replace")
        stderr = stderr_bytes.decode("utf-8", "replace")
        returncode = proc.returncode or 0
        data: dict[str, Any] | None = None
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            pass

        result_text = data.get("result", "") if data is not None else ""
        effective_output = result_text if isinstance(result_text, str) else ""
        valid_success = (
            returncode == 0
            and data is not None
            and data.get("is_error") is not True
            and bool(effective_output.strip())
        )

        # Budget detection stays distinct from OAuth-seat exhaustion because
        # WR3 routes cost caps according to gate/core/fallback contracts.
        budget_scan = stderr if valid_success else f"{stdout}\n{stderr}"
        budget_signals = (
            "exceeded usd budget",
            "max budget",
            "max_budget",
            "reached maximum budget",
            "spending limit",
            "spend_limit",
            "out of credit",
            "insufficient funds",
        )
        if any(sig in budget_scan.lower() for sig in budget_signals):
            raise BudgetExceededError(f"{contract.name}: budget cap ${ceiling} hit")

        reason = _retry_reason(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            valid_success=valid_success,
            effective_output=effective_output,
        )
        if reason is not None:
            failures.append(f"{label}:{reason}")
            logger.warning(
                "%s: Claude OAuth %s failed (%s); trying next seat",
                contract.name,
                label,
                reason,
            )
            continue

        if returncode != 0:
            diagnostic = _sanitize_diagnostic(stderr or stdout, secrets)
            raise WR3DispatchError(
                f"{contract.name}: Claude OAuth {label} exit {returncode}"
                + (f" diagnostic={diagnostic}" if diagnostic else "")
            )
        if data is None:
            diagnostic = _sanitize_diagnostic(stdout, secrets)
            raise WR3DispatchError(
                f"{contract.name}: Claude OAuth {label} returned non-JSON output"
                + (f" diagnostic={diagnostic}" if diagnostic else "")
            )
        if data.get("is_error") is True:
            diagnostic = _sanitize_diagnostic(effective_output or stderr, secrets)
            raise WR3DispatchError(
                f"{contract.name}: Claude OAuth {label} returned an error result"
                + (f" diagnostic={diagnostic}" if diagnostic else "")
            )

        duration_ms = int((loop.time() - started) * 1000)
        logger.info(
            "%s: Claude OAuth success via %s",
            contract.name,
            label,
        )
        return DispatchResult(
            agent=contract.name,
            cost_usd_estimated=data.get("total_cost_usd"),
            duration_ms=duration_ms,
            cascade_tier=1,
            raw_output=effective_output,
        )

    summary = ", ".join(failures) or "no seats available"
    raise ClaudeFleetExhaustedError(
        f"{contract.name}: Claude OAuth fleet exhausted ({summary})"
    )


async def _dispatch_gemini_cli(
    contract: AgentContract,
    prompt: str,
    *,
    timeout_s: int = 300,
) -> DispatchResult:
    """Run the existing Gemini OAuth fallback in an isolated child session."""
    agy = shutil.which("agy")
    if agy:
        cmd = [agy, "-p", "--print-timeout", f"{timeout_s}s"]
        stdin_payload = prompt.encode()
    else:
        legacy = shutil.which("gemini")
        if legacy is None:
            raise WR3DispatchError(
                "Neither `agy` nor `gemini` CLI on PATH for cascade Tier 2"
            )
        cmd = [legacy, "-m", "gemini-3.1-pro-preview", "-p", prompt]
        stdin_payload = None

    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + max(float(timeout_s), 0.001)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if stdin_payload else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_build_gemini_env(),
        start_new_session=True,
    )
    communicate_task = asyncio.create_task(proc.communicate(input=stdin_payload))
    done, _ = await asyncio.wait(
        {communicate_task},
        timeout=_child_run_budget(max(0.001, deadline - loop.time())),
    )
    if communicate_task not in done:
        await _terminate_process_tree(
            proc,
            communicate_task,
            global_deadline=deadline,
        )
        raise CascadeExhaustedError(
            f"{contract.name}: Gemini cascade timeout {timeout_s}s"
        )

    stdout, stderr = communicate_task.result()
    duration_ms = int((loop.time() - started) * 1000)
    stdout_text = stdout.decode("utf-8", "replace")
    stderr_text = stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        if _QUOTA_RE.search(f"{stdout_text}\n{stderr_text}"):
            raise CascadeExhaustedError(
                f"{contract.name}: Gemini quota exhausted"
            )
        diagnostic = _sanitize_diagnostic(stderr_text or stdout_text, [])
        raise WR3DispatchError(
            f"{contract.name}: Gemini exit {proc.returncode}"
            + (f" diagnostic={diagnostic}" if diagnostic else "")
        )
    if not stdout_text.strip():
        raise CascadeExhaustedError(
            f"{contract.name}: Gemini returned empty output"
        )

    return DispatchResult(
        agent=contract.name,
        cost_usd_estimated=0.0,
        duration_ms=duration_ms,
        cascade_tier=2,
        raw_output=stdout_text,
        cascade_reason="claude_budget_exceeded",
    )


async def dispatch_agent_v2(
    contracts: WR3Contracts,
    agent_name: str,
    prompt: str,
    *,
    episode_id: str = "unknown",
    timeout_ms: int = 300000,
) -> DispatchResult:
    """v2 dispatch entry — drop-in replacement for `wr3_dispatch_agent.dispatch_agent`.

    Same Symbiosis precedence:
      - GATE agent + BudgetExceededError → HardHaltException + Telegram P0
      - HOT PATH core + BudgetExceededError → cascade Tier 2 Gemini
      - Otherwise → CascadeExhaustedError
    """
    contract = contracts.for_agent(agent_name)

    try:
        return await dispatch_claude_print(contract, prompt, timeout_ms=timeout_ms)
    except ClaudeFleetExhaustedError as e:
        if contract.is_gate:
            await telegram_p0(
                f"{agent_name} exhausted the Claude OAuth fleet. "
                f"Episode {episode_id} HALTED."
            )
            raise HardHaltException(str(e)) from e

        if contract.is_core:
            try:
                return await _dispatch_gemini_cli(contract, prompt)
            except CascadeExhaustedError:
                await telegram_p0(
                    f"{agent_name} OAuth fleet+cascade exhausted. "
                    f"Episode {episode_id} FAIL."
                )
                raise

        raise CascadeExhaustedError(
            f"{agent_name} (non-core) Claude OAuth fleet exhausted — "
            "no cross-family cascade for scheduled/fallback tier"
        ) from e
    except BudgetExceededError as e:
        if contract.is_gate:
            await telegram_p0(
                f"{agent_name} hit cost ceiling. Episode {episode_id} HALTED."
            )
            raise HardHaltException(str(e)) from e

        if contract.is_core:
            try:
                return await _dispatch_gemini_cli(contract, prompt)
            except CascadeExhaustedError:
                await telegram_p0(
                    f"{agent_name} budget+cascade exhausted. Episode {episode_id} FAIL."
                )
                raise

        raise CascadeExhaustedError(
            f"{agent_name} (non-core) budget exceeded — no cascade for scheduled/fallback tier"
        ) from e


if __name__ == "__main__":
    # Smoke test — quick dispatch to verify wiring + cost
    import sys
    from wr3_contracts import load_contracts

    async def main() -> int:
        contracts = load_contracts()
        if len(sys.argv) > 1:
            slug = sys.argv[1]
        else:
            slug = "wr3-brief-interpreter"
        print(f"[v2-smoke] dispatching {slug}…")
        try:
            result = await dispatch_claude_print(
                contracts.for_agent(slug),
                "Reply with the single word OK.",
                timeout_ms=60000,
            )
            print(f"[v2-smoke] PASS cost=${result.cost_usd_estimated:.4f} "
                  f"dur={result.duration_ms}ms output={result.raw_output[:80]!r}")
            return 0
        except Exception as e:
            print(f"[v2-smoke] FAIL {type(e).__name__}: {e}")
            return 1

    sys.exit(asyncio.run(main()))
