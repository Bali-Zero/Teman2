"""Claude via Max-plan OAuth (subprocess to ``claude -p``).

Local, self-contained substitute for the banned paid path
``anthropic.AsyncAnthropic(api_key=...)`` (CLAUDE.md §5 / Golden Rule #13).
``bali-intel-scraper`` is a separate app and cannot import
``backend.llm.claude_oauth_client`` from ``backend-rag`` — this is a
minimal mirror of that module's contract (one-shot prompt -> text, no
streaming, no tool-use), which is exactly what ``ai_engine`` needs.

The ``claude`` CLI reads ``CLAUDE_CODE_OAUTH_TOKEN`` from the environment
(or the macOS keychain when unset). ``ANTHROPIC_API_KEY`` is stripped
unconditionally so the CLI can never silently fall back to the paid key.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Final

from backend.core.logger import get_logger

logger = get_logger(__name__, component="claude_oauth")

DEFAULT_TIMEOUT_S: Final[int] = 120
_CLI_CANDIDATES: Final[tuple[Path, ...]] = (
    Path("/opt/homebrew/bin/claude"),
    Path.home() / ".local/bin" / "claude",
    Path.home() / ".npm-global/bin" / "claude",
    Path("/usr/local/bin/claude"),
)


class ClaudeOAuthError(RuntimeError):
    """Raised when the ``claude`` CLI fails or returns empty output."""


def _resolve_cli() -> str:
    resolved = shutil.which("claude")
    if resolved:
        return resolved
    for candidate in _CLI_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "claude"


def _build_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return env


async def complete_oauth(
    prompt: str,
    *,
    model: str | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Run ``claude -p`` and return the text completion.

    Args:
        prompt: The full prompt (any system framing must be inlined — the
            CLI has no separate system-prompt slot).
        model: Optional CLI model slug (e.g. ``claude-sonnet-4-6``).
        timeout_s: Wall-clock timeout for the subprocess.

    Raises:
        ClaudeOAuthError: missing binary, non-zero exit, timeout, or empty
            output.
    """
    if not prompt:
        raise ValueError("prompt must be non-empty")

    cmd: list[str] = [_resolve_cli(), "-p", "--permission-mode", "bypassPermissions"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=_build_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ClaudeOAuthError(
            "`claude` CLI not found in PATH. Install: https://claude.ai/code",
        ) from exc

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_s
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise ClaudeOAuthError(f"claude CLI timeout after {timeout_s}s") from exc

    output = (stdout_b.decode(errors="replace") or "").strip()
    stderr = (stderr_b.decode(errors="replace") or "").strip()

    if proc.returncode != 0:
        raise ClaudeOAuthError(
            f"claude CLI exit={proc.returncode} stderr={stderr[:200]}"
        )
    if not output:
        raise ClaudeOAuthError("claude CLI returned empty output (quota/rate?)")

    return output
