"""
Mata Garuda — CLI Runtime.

Subprocess wrapper per LLM CLI/local tools (claude, agy, codex, ollama).
Vincolo inviolabile: MAI API HTTP, MAI SDK import.
Tutto passa via subprocess blocking.

Multi-account fallback for Claude CLI:
  CLAUDE_CODE_OAUTH_TOKEN_1 → account 1 (try first)
  CLAUDE_CODE_OAUTH_TOKEN_2 → account 2 (if 1 exhausted)
  CLAUDE_CODE_OAUTH_TOKEN_3 → account 3 (if 2 exhausted)
  CLAUDE_CODE_OAUTH_TOKEN_4 → account 4 (if 3 exhausted)
  CLAUDE_CODE_OAUTH_TOKEN_5 → Team seat (last-resort subscription)
  CLAUDE_CODE_OAUTH_TOKEN   → legacy single-token fallback
  keychain fallback          → whatever logged in via claude auth
  agy -p                     → final fallback if all Claude exhausted

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
    "CLAUDE_CODE_OAUTH_TOKEN_4",  # fourth MAX automation account
    "CLAUDE_CODE_OAUTH_TOKEN_5",  # Team premium seat, last-resort
]

# Rate limit detection patterns in stderr/stdout
# Aligned with bali-intel-scraper/scripts/claude_cli_enricher.py
RATE_LIMIT_PATTERNS = re.compile(
    r"rate.?limit|too many requests|(?<![\d/])429(?![\d/])|exhausted|quota|"
    r"usage limit|weekly limit|capacity|overloaded|try again later|hit your limit|"
    r"timeout after 90s|possibly rate limit",
    re.IGNORECASE,
)
AUTH_FAILURE_PATTERNS = re.compile(
    r"authentication (?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token|"
    r"unauthori[sz]ed|(?<![\d/])401(?![\d/])",
    re.IGNORECASE,
)
_OAUTH_SCRUB_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "CLOUD_ML_REGION",
})
_OAUTH_SCRUB_PREFIXES = (
    "AWS_",
    "VERTEX_AI_",
    "ANTHROPIC_VERTEX_",
    "ANTHROPIC_BEDROCK_",
    "ANTHROPIC_FOUNDRY_",
)


def _oauth_cli_env(token: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in _OAUTH_SCRUB_KEYS
        and not key.startswith(_OAUTH_SCRUB_PREFIXES)
    }
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    else:
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env

# Mapping model -> CLI command + flags
DEFAULT_OLLAMA_MODEL = os.environ.get("MATA_GARUDA_OLLAMA_MODEL", "qwen3.5:9b")
DEFAULT_AGY_MODEL = os.environ.get("MATA_GARUDA_AGY_MODEL", "gemini-3.5-flash")
DEFAULT_AGY_PRINT_TIMEOUT = os.environ.get("MATA_GARUDA_AGY_PRINT_TIMEOUT", "5m")

CLI_CONFIGS: dict[str, dict] = {
    "claude": {
        "cmd": "claude",
        "print_flag": "--print",
        # INTENTIONAL: --system-prompt (NOT --append-system-prompt) per SYMBIOSIS
        # Pillar 2 (OSINT blindato). Each mata-garuda agent runs with ONLY its
        # GENOME.md — no leak of Nuzantara root CLAUDE.md, MEMORY.md, or auto-
        # loaded Claude Code skills into OSINT agent reasoning. Trade-off: this
        # bypasses ~/.claude/settings.json excludeDynamicSystemPromptSections
        # (the flag is ignored with --system-prompt per CLI help), costing
        # ~3-8KB cache miss/run. Eval: docs/brainstorms/2026-05-15-mata-garuda-
        # system-prompt/README.md + GitHub issue #672. Do NOT refactor to
        # --append-system-prompt without re-reading that eval.
        "system_flag": "--system-prompt",
        "model_flag": "--model",
    },
    "agy": {
        "cmd": os.environ.get("MATA_GARUDA_AGY_BIN", "agy"),
        "print_flag": "-p",
        "system_flag": None,
        "model_flag": "--model",
        "timeout_flag": "--print-timeout",
    },
    "codex": {
        "cmd": "codex",
        "print_flag": "exec",
        "system_flag": None,
        "model_flag": None,
    },
    "ollama": {
        "cmd": "ollama",
        "print_flag": "run",
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


def _is_auth_failed(stdout: str, stderr: str) -> bool:
    """Detect account-specific OAuth/login failures from CLI output."""
    combined = (stdout or "") + (stderr or "")
    return bool(AUTH_FAILURE_PATTERNS.search(combined))


def _get_token_chain() -> list[tuple[str, str]]:
    """Build the ordered list of (label, token_value) to try.

    Aligned with bali-intel-scraper/scripts/claude_cli_enricher.py:
      1. CLAUDE_CODE_OAUTH_TOKEN_1/2/3/4/5 (explicit chain)
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
        return self.returncode == 0 and bool(self.output)

    @property
    def output(self) -> str:
        return self.stdout.strip()


class CLIRuntime:
    """
    Subprocess wrapper per LLM CLI tools.

    Supporta: claude (--print), agy (-p), codex (exec), ollama (local).
    Sempre blocking, mai interattivo.

    Claude multi-account fallback:
    - Tries each CLAUDE_CODE_OAUTH_TOKEN_N in order
    - Latches exhausted tokens (skips them instantly)
    - Falls back to agy if all Claude tokens exhausted
    """

    def __init__(
        self,
        model: str = "claude",
        timeout: int = DEFAULT_TIMEOUT,
        working_dir: Optional[str] = None,
    ):
        self.ollama_model: str | None = None
        self.agy_model: str | None = None
        if model.startswith("ollama:"):
            self.ollama_model = model.split(":", 1)[1].strip() or DEFAULT_OLLAMA_MODEL
            model = "ollama"
        elif model == "ollama":
            self.ollama_model = DEFAULT_OLLAMA_MODEL
        elif model.startswith("agy:"):
            self.agy_model = model.split(":", 1)[1].strip() or DEFAULT_AGY_MODEL
            model = "agy"
        elif model == "agy":
            self.agy_model = DEFAULT_AGY_MODEL

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

        if self.model == "ollama":
            combined = prompt
            if system_prompt:
                combined = f"<system>\n{system_prompt}\n</system>\n\n{prompt}"
            return [
                self.config["cmd"],
                self.config["print_flag"],
                self.ollama_model or DEFAULT_OLLAMA_MODEL,
                combined,
            ]

        if self.model == "agy":
            combined = prompt
            if system_prompt:
                combined = f"<system>\n{system_prompt}\n</system>\n\n{prompt}"
            cmd.extend([self.config["print_flag"], combined])
            if self.config["model_flag"] and (self.agy_model or DEFAULT_AGY_MODEL):
                cmd.extend([self.config["model_flag"], self.agy_model or DEFAULT_AGY_MODEL])
            if DEFAULT_AGY_PRINT_TIMEOUT:
                cmd.extend([self.config["timeout_flag"], DEFAULT_AGY_PRINT_TIMEOUT])
            if extra_flags:
                cmd.extend(extra_flags)
            return cmd

        # claude: --print "prompt"
        cmd.append(self.config["print_flag"])
        cmd.append(prompt)

        # System prompt (claude only for now)
        if system_prompt and self.config["system_flag"]:
            cmd.append(self.config["system_flag"])
            cmd.append(system_prompt)

        # For CLIs without system prompt support: prepend it to the user prompt.
        if system_prompt and not self.config["system_flag"]:
            combined = f"<system>\n{system_prompt}\n</system>\n\n{prompt}"
            cmd[cmd.index(prompt)] = combined

        if extra_flags:
            cmd.extend(extra_flags)

        return cmd

    def _result_model_name(self) -> str:
        """Return the concrete model label to record in CLIResult."""
        if self.model == "agy":
            return f"agy:{self.agy_model or DEFAULT_AGY_MODEL}"
        return self.model

    def _run_subprocess(
        self,
        cmd: list[str],
        env: Optional[dict] = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess with optional env override."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout if timeout is None else timeout,
            cwd=self.working_dir,
            env=env,
        )

    def _invoke_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> CLIResult:
        """Invoke local Ollama through the shared curl-based helper."""
        from mata_garuda.tools.ollama_tools import generate

        combined = prompt
        if system_prompt:
            combined = f"<system>\n{system_prompt}\n</system>\n\n{prompt}"

        start = time.monotonic()
        model_name = self.ollama_model or DEFAULT_OLLAMA_MODEL
        try:
            output = generate(
                model_name,
                combined,
                num_predict=int(os.environ.get("MATA_GARUDA_OLLAMA_NUM_PREDICT", "700")),
                timeout=self.timeout,
            )
        except Exception as exc:  # pragma: no cover - defensive local subprocess
            elapsed = time.monotonic() - start
            return CLIResult(
                stdout="",
                stderr=f"Ollama invocation failed: {type(exc).__name__}: {exc}",
                returncode=1,
                elapsed_seconds=round(elapsed, 2),
                model=f"ollama:{model_name}",
                token_used="local_ollama",
                command=["ollama", "run", model_name, "<prompt>"],
            )

        elapsed = time.monotonic() - start
        if output is None:
            return CLIResult(
                stdout="",
                stderr=f"Ollama returned no output for {model_name}",
                returncode=1,
                elapsed_seconds=round(elapsed, 2),
                model=f"ollama:{model_name}",
                token_used="local_ollama",
                command=["ollama", "run", model_name, "<prompt>"],
            )

        return CLIResult(
            stdout=output,
            stderr="",
            returncode=0,
            elapsed_seconds=round(elapsed, 2),
            model=f"ollama:{model_name}",
            token_used="local_ollama",
            command=["ollama", "run", model_name, "<prompt>"],
        )

    def _invoke_single(
        self,
        cmd: list[str],
        token_label: str,
        token_value: str = "",
        timeout_override: float | None = None,
    ) -> CLIResult:
        """Invoke CLI with a specific token. Returns CLIResult."""
        # Build env with token override
        # Empty string = use keychain (pop the var so CLI falls back to keychain)
        env = _oauth_cli_env(token_value)

        start = time.monotonic()
        try:
            result = self._run_subprocess(
                cmd,
                env=env,
                timeout=timeout_override,
            )
            elapsed = time.monotonic() - start

            return CLIResult(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                elapsed_seconds=round(elapsed, 2),
                model=self._result_model_name(),
                token_used=token_label,
                command=cmd,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return CLIResult(
                stdout="",
                stderr="Invocation timed out",
                returncode=-1,
                elapsed_seconds=round(elapsed, 2),
                model=self._result_model_name(),
                token_used=token_label,
                command=cmd,
            )
        except FileNotFoundError:
            return CLIResult(
                stdout="",
                stderr=f"Command not found: {cmd[0]}",
                returncode=-2,
                elapsed_seconds=0.0,
                model=self._result_model_name(),
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
        latches exhausted tokens, falls back to agy.

        Args:
            prompt: User message / query to send
            system_prompt: System instructions (agent persona, constraints)
            extra_flags: Additional CLI flags

        Returns:
            CLIResult with stdout, stderr, returncode, timing
        """
        if self.model == "ollama":
            logger.info(
                f"[CLIRuntime] Invoking local Ollama "
                f"({self.ollama_model or DEFAULT_OLLAMA_MODEL})"
            )
            return self._invoke_ollama(prompt, system_prompt)

        cmd = self._build_command(prompt, system_prompt, extra_flags)

        # Non-Claude models: single call, no fallback chain
        if self.model != "claude":
            logger.info(f"[CLIRuntime] Invoking {self.model} (no fallback chain)")
            return self._invoke_single(cmd, "default", "")

        # Claude: try each token in the chain
        token_chain = _get_token_chain()
        deadline = time.monotonic() + self.timeout
        last_result: CLIResult | None = None

        for position, (label, token) in enumerate(token_chain):
            # Latch: skip exhausted tokens instantly
            if label in _exhausted_tokens:
                logger.info(f"[CLIRuntime] SKIP {label} (exhausted latch)")
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            attempt_timeout = max(
                0.1,
                remaining / (len(token_chain) - position),
            )

            logger.info(f"[CLIRuntime] Trying Claude with {label}")
            result = self._invoke_single(
                cmd,
                label,
                token,
                timeout_override=attempt_timeout,
            )
            last_result = result

            # Account-specific exhaustion/auth failures and empty success all
            # rotate to the next subscription seat. A zero exit with no output
            # is not a successful LLM response.
            if _is_rate_limited(result.stdout, result.stderr):
                _exhausted_tokens.add(label)
                logger.warning(
                    f"[CLIRuntime] {label} EXHAUSTED (rate limited). "
                    f"Latched for this run."
                )
                continue
            if _is_auth_failed(result.stdout, result.stderr):
                _exhausted_tokens.add(label)
                logger.warning(
                    f"[CLIRuntime] {label} AUTH FAILED. Latched for this run."
                )
                continue
            if result.success:
                logger.info(
                    f"[CLIRuntime] Success via {label} in {result.elapsed_seconds}s "
                    f"({len(result.output)} chars)"
                )
                return result
            if result.returncode == -1:
                _exhausted_tokens.add(label)
                logger.warning(
                    f"[CLIRuntime] {label} TIMED OUT. Latched for this run."
                )
                continue
            if result.returncode == 0 and not result.output:
                _exhausted_tokens.add(label)
                logger.warning(
                    f"[CLIRuntime] {label} returned empty output. "
                    f"Latched for this run."
                )
                continue

            # Non-rate-limit failure: return the error, don't try next token
            logger.warning(
                f"[CLIRuntime] {label} failed (non-rate-limit), "
                f"exit={result.returncode}"
            )
            return result

        # All Claude tokens exhausted — fallback to agy.
        logger.warning(
            "[CLIRuntime] All Claude tokens exhausted. Falling back to agy."
        )
        fallback_model = os.environ.get(
            "MATA_GARUDA_CLAUDE_FALLBACK_MODEL",
            f"agy:{DEFAULT_AGY_MODEL}",
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return last_result or CLIResult(
                stdout="",
                stderr="Global invocation deadline exceeded",
                returncode=-1,
                elapsed_seconds=float(self.timeout),
                model=self._result_model_name(),
                token_used="deadline",
                command=cmd,
            )
        fallback = CLIRuntime(
            model=fallback_model,
            timeout=max(1, int(remaining)),
            working_dir=self.working_dir,
        )
        result = fallback.invoke(prompt, system_prompt, extra_flags)
        result.token_used = "agy_fallback"
        if result.success:
            logger.info(
                f"[CLIRuntime] agy fallback success in {result.elapsed_seconds}s"
            )
        else:
            logger.error("[CLIRuntime] agy fallback also failed")

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
