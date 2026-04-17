"""Claude via Max plan OAuth (subprocess to ``claude -p``).

Project policy (``memory/feedback_claude_oauth_only.md``): all Claude
integrations must use the Max plan OAuth token, never ``ANTHROPIC_API_KEY``.
The Python SDK ``anthropic.Anthropic`` has no OAuth-token mode — this module
is the substitute: it shells out to the ``claude`` CLI which reads
``CLAUDE_CODE_OAUTH_TOKEN`` from the environment.

Pattern mirrored from ``scripts/cron-agent.sh`` tier-2 handler (same 3-token
fallback + rate-limit detection + empty-output guard). Kept intentionally
minimal — no streaming, no tool-use — because the only 3 backend consumers
(``article_composer``, ``coreference``, ``multi_ai_adapter.ClaudeAdapter``)
all do the same thing: one-shot prompt → one-shot text completion.

Never import this from a module that also imports ``anthropic``. The whole
point is to not need the SDK.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT_S: Final[int] = 120
RATE_LIMIT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"rate.limit|too many requests|429|exhausted|quota|hit your limit|capacity|overloaded",
    re.IGNORECASE,
)


class ClaudeOAuthError(RuntimeError):
    """Raised when every OAuth token (and keychain fallback) failed."""


class ClaudeOAuthNotAvailable(RuntimeError):
    """Raised when the ``claude`` CLI binary is missing from PATH."""


@dataclass(frozen=True)
class ClaudeOAuthResponse:
    """Minimal response envelope returned by :func:`complete`."""

    text: str
    token_label: str
    elapsed_s: float
    attempts: int


def _collect_tokens() -> list[tuple[str, str]]:
    """Return ordered list of ``(token, label)`` pairs to try.

    Order:
    1. ``CLAUDE_CODE_OAUTH_TOKEN_1/2/3`` in numeric order (skip empties),
    2. Legacy ``CLAUDE_CODE_OAUTH_TOKEN`` if not already covered,
    3. Sentinel ``("", "keychain")`` — runs the CLI with the env var *unset*
       so it falls back to the macOS keychain-stored token.
    """
    collected: list[tuple[str, str]] = []
    seen: set[str] = set()

    for i in (1, 2, 3):
        tok = os.getenv(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok and tok not in seen:
            collected.append((tok, f"token_{i}"))
            seen.add(tok)

    legacy = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and legacy not in seen:
        collected.append((legacy, "token_legacy"))
        seen.add(legacy)

    collected.append(("", "keychain"))
    return collected


def _build_env(token: str) -> dict[str, str]:
    """Env vars for the ``claude`` subprocess.

    Strips ``ANTHROPIC_API_KEY`` unconditionally (Golden Rule: never let the
    CLI silently pick up a pay-as-you-go key) and sets
    ``CLAUDE_CODE_OAUTH_TOKEN`` when the caller passes one.
    """
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    else:
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


async def complete_async(
    prompt: str,
    *,
    model: str | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> ClaudeOAuthResponse:
    """Run ``claude -p`` with 3-token fallback and return the text completion.

    Args:
        prompt: The user prompt (system-prompt handling is deferred to the
            CLI — pass everything inline for now).
        model: Optional model id forwarded as ``claude -p --model <id>``.
            Accepts any slug the CLI accepts (``claude-opus-4-7``,
            ``claude-sonnet-4-6``, ``claude-haiku-4-5``, …).
        timeout_s: Per-attempt wall-clock timeout. The total cap is roughly
            ``timeout_s × len(tokens)``.

    Returns:
        :class:`ClaudeOAuthResponse` with the completion text and the label
        of the token that succeeded.

    Raises:
        :class:`ClaudeOAuthNotAvailable`: the ``claude`` binary is missing.
        :class:`ClaudeOAuthError`: every token hit rate-limit / empty output
            / non-zero exit.
    """
    if not prompt:
        raise ValueError("prompt must be non-empty")

    tokens = _collect_tokens()
    start = time.monotonic()
    last_error = ""

    for attempt, (token, label) in enumerate(tokens, start=1):
        cmd: list[str] = [
            "claude",
            "-p",
            "--permission-mode",
            "bypassPermissions",
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.append(prompt)

        env = _build_env(token)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ClaudeOAuthNotAvailable(
                "`claude` CLI not found in PATH. Install: https://claude.ai/code",
            ) from exc

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await proc.wait()
            except Exception:
                pass
            last_error = f"{label}: timeout after {timeout_s}s"
            logger.warning(last_error)
            continue

        exit_code = proc.returncode or 0
        output = (stdout_b.decode(errors="replace") or "").strip()
        stderr = (stderr_b.decode(errors="replace") or "").strip()

        combined = f"{output}\n{stderr}"

        if exit_code != 0 and RATE_LIMIT_PATTERN.search(combined):
            last_error = f"{label}: rate limited"
            logger.warning("%s: rate limited, trying next", label)
            continue

        if not output and exit_code in (0, 143):
            last_error = f"{label}: empty output (quota?)"
            logger.warning("%s: empty output (likely quota/rate issue), trying next", label)
            continue

        if exit_code != 0:
            last_error = f"{label}: exit={exit_code} stderr={stderr[:200]}"
            logger.warning(last_error)
            continue

        elapsed = time.monotonic() - start
        logger.info("claude -p success via %s (%.2fs, attempt %d)", label, elapsed, attempt)
        return ClaudeOAuthResponse(
            text=output,
            token_label=label,
            elapsed_s=elapsed,
            attempts=attempt,
        )

    raise ClaudeOAuthError(
        f"All {len(tokens)} OAuth attempts failed. Last error: {last_error}",
    )


def complete(
    prompt: str,
    *,
    model: str | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> ClaudeOAuthResponse:
    """Synchronous wrapper around :func:`complete_async`.

    Useful for the 3 existing call sites that are sync code paths. Does NOT
    work inside an already-running event loop — use
    :func:`complete_async` from async code.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        raise RuntimeError(
            "complete() is sync; inside a running event loop call complete_async() instead",
        )

    return asyncio.run(complete_async(prompt, model=model, timeout_s=timeout_s))
