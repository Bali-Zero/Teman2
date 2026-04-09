"""
Mata Garuda — CLI Runtime.

Subprocess wrapper per LLM CLI (claude, gemini, codex).
Vincolo inviolabile: MAI API HTTP, MAI SDK import.
Tutto passa via subprocess blocking.

Multi-account fallback for Claude CLI:
  CLAUDE_CODE_OAUTH_TOKEN_1 → account 1 (try first)
  CLAUDE_CODE_OAUTH_TOKEN_2 → account 2 (if 1 exhausted)
  CLAUDE_CODE_OAUTH_TOKEN_3 → account 3 (if 2 exhausted)
  keychain fallback          → whatever logged in via claude auth
  gemini --prompt            → final fallback if all Claude exhausted

The "latch" pattern: once a token is marked exhausted in a run,
subsequent calls skip it instantly (0s) instead of waiting for timeout.

Usage:
    runtime = CLIRuntime(model="claude")
    output = runtime.invoke("You are a helpful agent", "Hello!")
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("mata_garuda.runtime")

# Timeout default per subprocess (5 minuti)
DEFAULT_TIMEOUT = 300

# Token env var names (in priority order)
CLAUDE_TOKEN_VARS = [
    "CLAUDE_CODE_OAUTH_TOKEN_1",  # antonellosiano@gmail.com
    "CLAUDE_CODE_OAUTH_TOKEN_2",  # kaiser198719871987@gmail.com
    "CLAUDE_CODE_OAUTH_TOKEN_3",  # sianoantonello@gmail.com
]

# Rate limit detection patterns in stderr/stdout
# Aligned with bali-intel-scraper/scripts/claude_cli_enricher.py
RATE_LIMIT_PATTERNS = re.compile(
    r"rate.?limit|too many requests|429|exhausted|quota|"
    r"capacity|overloaded|try again later|hit your limit|"
    r"timeout after 90s|possibly rate limit",
    re.IGNORECASE,
)

# Mapping model -> CLI command + flags
CLI_CONFIGS: dict[str, dict] = {
    "claude": {
        "cmd": "claude",
        "print_flag": "--print",
        "system_flag": "--system-prompt",
        "model_flag": "--model",
    },
    "gemini": {
        "cmd": "gemini",
        "print_flag": "--prompt",  # gemini usa --prompt, non --print
        "system_flag": None,  # gemini non ha --system-prompt diretto
        "model_flag": "--model",
    },
    "codex": {
        "cmd": "codex",
        "print_flag": "exec",
        "system_flag": None,
        "model_flag": None,
    },
}

# Latch: tokens marked exhausted during this process lifetime.
# Resets on process restart (each CLI run is a fresh process).
_exhausted_tokens: set[str] = set()


def _is_rate_limited(stdout: str, stderr: str) -> bool:
    """Detect if a CLI call was rate-limited from output strings."""
    combined = (stdout or "") + (stderr or "")
    return bool(RATE_LIMIT_PATTERNS.search(combined))


def _get_token_chain() -> list[tuple[str, str]]:
    """Build the ordered list of (label, token_value) to try.

    Aligned with bali-intel-scraper/scripts/claude_cli_enricher.py:
      1. CLAUDE_CODE_OAUTH_TOKEN_1/2/3 (explicit chain)
      2. CLAUDE_CODE_OAUTH_TOKEN (legacy single token, if different from above)
      3. "" (keychain — CLI uses whatever account is logged in)

    Returns:
        List of (label, token_or_empty). Empty string means "use keychain default".
    """
    chain: list[tuple[str, str]] = []
    for var_name in CLAUDE_TOKEN_VARS:
        token = os.environ.get(var_name, "").strip()
        if token:
            chain.append((var_name, token))

    # Legacy single token (e.g., from plist or older config)
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and not any(t == legacy for _, t in chain):
        chain.append(("token_legacy", legacy))

    # Always fall back to keychain as last resort (empty = let CLI use keychain)
    chain.append(("keychain", ""))
    return chain


@dataclass
class CLIResult:
    """Output di una singola invocazione CLI."""

    stdout: str
    stderr: str
    returncode: int
    elapsed_seconds: float
    model: str
    token_used: str = "keychain"
    command: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return self.stdout.strip()


class CLIRuntime:
    """
    Subprocess wrapper per LLM CLI tools.

    Supporta: claude (--print), gemini (--prompt), codex (exec).
    Sempre blocking, mai interattivo.

    Claude multi-account fallback:
    - Tries each CLAUDE_CODE_OAUTH_TOKEN_N in order
    - Latches exhausted tokens (skips them instantly)
    - Falls back to gemini if all Claude tokens exhausted
    """

    def __init__(
        self,
        model: str = "claude",
        timeout: int = DEFAULT_TIMEOUT,
        working_dir: Optional[str] = None,
    ):
        if model not in CLI_CONFIGS:
            raise ValueError(
                f"Unknown model '{model}'. Supported: {list(CLI_CONFIGS.keys())}"
            )
        self.model = model
        self.config = CLI_CONFIGS[model]
        self.timeout = timeout
        self.working_dir = working_dir

    def _build_command(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        extra_flags: Optional[list[str]] = None,
    ) -> list[str]:
        """Build the subprocess command list."""
        cmd = [self.config["cmd"]]

        if self.model == "codex":
            # codex exec "prompt"
            cmd.append(self.config["print_flag"])
            cmd.append(prompt)
            return cmd

        # claude: --print "prompt" / gemini: --prompt "prompt"
        cmd.append(self.config["print_flag"])
        cmd.append(prompt)

        # System prompt (claude only for now)
        if system_prompt and self.config["system_flag"]:
            cmd.append(self.config["system_flag"])
            cmd.append(system_prompt)

        # For gemini: prepend system prompt to user prompt
        if system_prompt and not self.config["system_flag"]:
            combined = f"<system>\n{system_prompt}\n</system>\n\n{prompt}"
            cmd[cmd.index(prompt)] = combined

        if extra_flags:
            cmd.extend(extra_flags)

        return cmd

    def _run_subprocess(
        self,
        cmd: list[str],
        env: Optional[dict] = None,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess with optional env override."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=self.working_dir,
            env=env,
        )

    def _invoke_single(
        self,
        cmd: list[str],
        token_label: str,
        token_value: str = "",
    ) -> CLIResult:
        """Invoke CLI with a specific token. Returns CLIResult."""
        # Build env with token override
        # Empty string = use keychain (pop the var so CLI falls back to keychain)
        env = os.environ.copy()
        if token_value:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token_value
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

        start = time.monotonic()
        try:
            result = self._run_subprocess(cmd, env=env)
            elapsed = time.monotonic() - start

            return CLIResult(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                elapsed_seconds=round(elapsed, 2),
                model=self.model,
                token_used=token_label,
                command=cmd,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return CLIResult(
                stdout="",
                stderr=f"Timeout after {self.timeout}s",
                returncode=-1,
                elapsed_seconds=round(elapsed, 2),
                model=self.model,
                token_used=token_label,
                command=cmd,
            )
        except FileNotFoundError:
            return CLIResult(
                stdout="",
                stderr=f"Command not found: {cmd[0]}",
                returncode=-2,
                elapsed_seconds=0.0,
                model=self.model,
                token_used=token_label,
                command=cmd,
            )

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        extra_flags: Optional[list[str]] = None,
    ) -> CLIResult:
        """
        Invoke the CLI tool with multi-account fallback.

        For Claude: tries each CLAUDE_CODE_OAUTH_TOKEN_N in order,
        latches exhausted tokens, falls back to gemini.

        Args:
            prompt: User message / query to send
            system_prompt: System instructions (agent persona, constraints)
            extra_flags: Additional CLI flags

        Returns:
            CLIResult with stdout, stderr, returncode, timing
        """
        cmd = self._build_command(prompt, system_prompt, extra_flags)

        # Non-Claude models: single call, no fallback chain
        if self.model != "claude":
            logger.info(f"[CLIRuntime] Invoking {self.model} (no fallback chain)")
            return self._invoke_single(cmd, "default", "")

        # Claude: try each token in the chain
        token_chain = _get_token_chain()

        for label, token in token_chain:
            # Latch: skip exhausted tokens instantly
            if label in _exhausted_tokens:
                logger.info(f"[CLIRuntime] SKIP {label} (exhausted latch)")
                continue

            logger.info(f"[CLIRuntime] Trying Claude with {label}")
            result = self._invoke_single(cmd, label, token)

            if result.success:
                logger.info(
                    f"[CLIRuntime] Success via {label} in {result.elapsed_seconds}s "
                    f"({len(result.output)} chars)"
                )
                return result

            # Check if rate-limited
            if _is_rate_limited(result.stdout, result.stderr):
                _exhausted_tokens.add(label)
                logger.warning(
                    f"[CLIRuntime] {label} EXHAUSTED (rate limited). "
                    f"Latched for this run."
                )
                continue

            # Non-rate-limit failure: return the error, don't try next token
            logger.warning(
                f"[CLIRuntime] {label} failed (non-rate-limit): "
                f"{result.stderr[:200]}"
            )
            return result

        # All Claude tokens exhausted — fallback to Gemini
        logger.warning(
            "[CLIRuntime] All Claude tokens exhausted. Falling back to Gemini."
        )
        gemini_config = CLI_CONFIGS["gemini"]
        gemini_cmd = [gemini_config["cmd"], gemini_config["print_flag"]]

        # Build gemini prompt (prepend system if available)
        if system_prompt:
            gemini_prompt = f"<system>\n{system_prompt}\n</system>\n\n{prompt}"
        else:
            gemini_prompt = prompt
        gemini_cmd.append(gemini_prompt)

        result = self._invoke_single(gemini_cmd, "gemini_fallback", "")
        if result.success:
            logger.info(
                f"[CLIRuntime] Gemini fallback success in {result.elapsed_seconds}s"
            )
            result.model = "gemini"
        else:
            logger.error("[CLIRuntime] Gemini fallback also failed")

        return result


def get_exhausted_tokens() -> set[str]:
    """Get the set of currently latched (exhausted) token labels."""
    return _exhausted_tokens.copy()


def reset_exhausted_tokens() -> None:
    """Reset the exhausted token latch (e.g., for a new run)."""
    _exhausted_tokens.clear()


def parse_tool_calls(text: str) -> list[dict]:
    """
    Parse tool calls from LLM text output.

    LLMs without native function calling emit JSON-in-text.
    We look for <tool_call> blocks or ```json blocks with tool_name/arguments.

    Returns:
        List of {"tool_name": str, "arguments": dict}
    """
    calls = []

    # Pattern 1: <tool_call>{"tool_name": ..., "arguments": {...}}</tool_call>
    for match in re.finditer(
        r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL
    ):
        try:
            parsed = json.loads(match.group(1))
            if "tool_name" in parsed:
                calls.append(parsed)
        except json.JSONDecodeError:
            continue

    if calls:
        return calls

    # Pattern 2: ```json\n{"tool_name": ..., "arguments": {...}}\n```
    for match in re.finditer(
        r"```json\s*\n(\{.*?\})\s*\n```", text, re.DOTALL
    ):
        try:
            parsed = json.loads(match.group(1))
            if "tool_name" in parsed:
                calls.append(parsed)
        except json.JSONDecodeError:
            continue

    return calls
