"""Claude via Max plan OAuth (subprocess to ``claude -p``).

Project policy (``memory/feedback_claude_oauth_only.md``): all Claude
integrations must use the Max plan OAuth token, never ``ANTHROPIC_API_KEY``.
The Python SDK ``anthropic.Anthropic`` has no OAuth-token mode — this module
is the substitute: it shells out to the ``claude`` CLI which reads
``CLAUDE_CODE_OAUTH_TOKEN`` from the environment.

Pattern mirrored from ``scripts/cron-agent.sh`` tier-2 handler (same 4-token
fallback + rate-limit detection + empty-output guard). Kept intentionally
minimal — no streaming, no tool-use — because the only 3 backend consumers
(``article_composer``, ``coreference``, ``multi_ai_adapter.ClaudeAdapter``)
all do the same thing: one-shot prompt → one-shot text completion.

Never import this from a module that also imports ``anthropic``. The whole
point is to not need the SDK.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shutil
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)


def _start_claude_cli_span(model_name: str, prompt_len_tokens: int) -> Any:
    """Open an OTEL span for the upcoming `claude` CLI invocation.

    This is the only LLM path in the codebase that's not patchable by an
    OpenInference instrumentor (it shells out to a CLI). The span flows
    to the same Langfuse project as everything else because the Langfuse
    SDK registers itself as the global OTEL tracer provider during
    `init_observability()`. When OTEL is not installed or no provider is
    registered, this returns a `nullcontext` and emits nothing — the
    function is purely additive.

    Returns a context manager. Callers should:
        with _start_claude_cli_span(...) as span:
            ...subprocess work...
            span.set_attribute("gen_ai.usage.output_tokens", N)  # if span
    """
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("nuzantara.claude_oauth")
        return tracer.start_as_current_span(
            "claude_cli.invoke",
            attributes={
                # OTEL gen_ai semantic conventions:
                # https://opentelemetry.io/docs/specs/semconv/gen-ai/
                "gen_ai.system": "claude-cli",
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": model_name,
                # Estimated tokens (CLI doesn't report metadata).
                "gen_ai.usage.input_tokens": prompt_len_tokens,
            },
        )
    except Exception:
        return nullcontext()


DEFAULT_TIMEOUT_S: Final[int] = 120
DEFAULT_TOTAL_TIMEOUT_S: Final[int] = 300
RATE_LIMIT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"rate.limit|too many requests|429|exhausted|quota|hit your limit|capacity|overloaded",
    re.IGNORECASE,
)
_MAX_DIAGNOSTIC_CHARS: Final[int] = 512
_MAX_DIAGNOSTIC_LINES: Final[int] = 6
_DIAGNOSTIC_FRAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?:"
    r"(?:error|fatal)(?:\[[^\]]+\])?\s*[:\-]|"
    r"you(?:'ve| have)\s+hit\s+(?:your\s+)?(?:weekly|usage)\s+limit\b|"
    r"(?:weekly|usage)\s+(?:limit|quota)\s+(?:reached|exceeded|exhausted)\b|"
    r"quota\s+(?:exceeded|exhausted)\b|"
    r"(?:http(?:\s+status)?\s*)?401(?:\s|:|$)|"
    r"unauthorized\b|"
    r"auth(?:entication)?\s+(?:failed|error|required|expired)\b|"
    r"oauth\s+(?:failed|error|required|expired)\b|"
    r"token_revoked\b|"
    r"refresh_token(?:_reused|_revoked|_expired)?\b"
    r")",
    re.IGNORECASE,
)
_AUTH_DIAGNOSTIC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:"
    r"token_revoked|refresh_token(?:_reused|_revoked|_expired)?|"
    r"401|unauthorized|"
    r"auth(?:entication)?\s+(?:failed|error|required|expired)|"
    r"oauth\s+(?:failed|error|required|expired)"
    r")\b",
    re.IGNORECASE,
)
_QUOTA_DIAGNOSTIC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:"
    r"out of extra usage|"
    r"(?:weekly|usage)\s+(?:limit|quota)|"
    r"quota\s+(?:exceeded|exhausted)|"
    r"rate[ -]?limit(?:ed| exceeded)?|"
    r"too many requests|429"
    r")\b",
    re.IGNORECASE,
)
_PROVIDER_ENV_EXACT: Final[frozenset[str]] = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_QUOTA_PROJECT",
        "CLOUD_ML_REGION",
    }
)
_PROVIDER_ENV_PREFIXES: Final[tuple[str, ...]] = (
    "AWS_",
    "BEDROCK_",
    "ANTHROPIC_BEDROCK_",
    "VERTEX_",
    "ANTHROPIC_VERTEX_",
)
CLAUDE_CLI_CANDIDATES: Final[tuple[Path, ...]] = (
    Path("/opt/homebrew/bin/claude"),
    Path.home() / ".local/bin" / "claude",
    Path.home() / ".npm-global/bin" / "claude",
    Path("/usr/local/bin/claude"),
)
# Model slug allowlist-by-shape: the value is forwarded to ``--model``, so
# reject anything that isn't a plain ``claude-*`` slug (blocks argv/flag
# smuggling via the model field). All current call-site slugs pass:
# ``claude-sonnet-4-6``, ``claude-haiku-4-5``, ``claude-haiku-4-5-20251001``.
_ALLOWED_MODEL_RE: Final[re.Pattern[str]] = re.compile(r"^claude-[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
# Pure text-completion never needs tools. Block the destructive/exfil ones
# defense-in-depth so an untrusted prompt (e.g. a raw user query routed
# through ``surface_router``) can never reach a tool — replaces the unsafe
# ``--permission-mode bypassPermissions`` this client used to carry.
_DISALLOWED_TOOLS: Final[tuple[str, ...]] = (
    "Bash",
    "Edit",
    "Write",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
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
    # Populated ONLY when ``json_schema`` is passed to :func:`complete_async`
    # and the CLI returned a well-formed ``--output-format json`` envelope with
    # a ``structured_output`` object. ``None`` on the default text path (keeps
    # the dataclass backward-compatible for positional/keyword construction).
    structured: dict[str, Any] | None = None


def _collect_tokens() -> list[tuple[str, str]]:
    """Return ordered list of ``(token, label)`` pairs to try.

    Order:
    1. ``CLAUDE_CODE_OAUTH_TOKEN_1/2/3/4`` in numeric order (skip empties),
    2. Legacy ``CLAUDE_CODE_OAUTH_TOKEN`` if not already covered,
    3. Sentinel ``("", "keychain")`` — runs the CLI with the env var *unset*
       so it falls back to the macOS keychain-stored token.
    """
    collected: list[tuple[str, str]] = []
    seen: set[str] = set()

    for i in (1, 2, 3, 4):
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

    Strips every alternate Anthropic provider credential/selector so the CLI
    cannot silently escape the Max OAuth path through a direct API key,
    Bedrock, or Vertex. Numbered seat tokens are also removed; the child sees
    only the selected ``CLAUDE_CODE_OAUTH_TOKEN``.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in _PROVIDER_ENV_EXACT
        and not key.startswith(_PROVIDER_ENV_PREFIXES)
        and not key.startswith("CLAUDE_CODE_OAUTH_TOKEN_")
    }
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    else:
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


def _classify_cli_diagnostic(text: str) -> str | None:
    """Return a safe diagnostic class for a short, clearly framed CLI error.

    Claude may occasionally exit 0 while printing a quota/auth diagnostic.
    Scanning arbitrary successful content for words such as "quota" causes
    false positives, so this gate only examines bounded, low-line-count text
    that starts like a CLI error. The returned value is a fixed class suitable
    for logs; raw output is never returned.
    """
    sample = (text or "").strip()
    if (
        not sample
        or len(sample) > _MAX_DIAGNOSTIC_CHARS
        or len(sample.splitlines()) > _MAX_DIAGNOSTIC_LINES
    ):
        return None

    compact = " ".join(sample.split())
    if _DIAGNOSTIC_FRAME_PATTERN.search(compact) is None:
        return None
    if _AUTH_DIAGNOSTIC_PATTERN.search(compact):
        return "authentication"
    if _QUOTA_DIAGNOSTIC_PATTERN.search(compact):
        return "quota"
    return None


async def _kill_and_reap(proc: Any) -> None:
    """Terminate a timed-out child and wait for it so no zombie remains."""
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()


def _resolve_claude_cli() -> str:
    """Return an executable `claude` path for launchd-safe subprocess calls.

    LaunchAgents often run with a minimal PATH. Resolve the binary once from
    the current PATH, then fall back to the install locations used on Pro/Mini.
    Returning the bare command keeps the old FileNotFoundError behavior when
    the CLI is genuinely absent.
    """
    resolved = shutil.which("claude")
    if resolved:
        return resolved

    for candidate in CLAUDE_CLI_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return "claude"


# Cap the serialized schema length so a pathological schema can never blow past
# the OS argv limit (`ARG_MAX`) — keeps the structured path from silently
# producing an E2BIG OSError mid-cron. 16 KiB is generous for any realistic
# Pydantic-derived schema (review D6).
_MAX_SCHEMA_BYTES: Final[int] = 16 * 1024

# Cached result of "does this `claude` binary support --json-schema?". None =
# not yet probed. Probed once per process via `_cli_supports_json_schema`.
_JSON_SCHEMA_SUPPORTED: bool | None = None


def _cli_supports_json_schema(claude_cli: str, timeout_s: float = 10) -> bool:
    """Return True iff the resolved `claude` CLI advertises ``--json-schema``.

    Probed once and memoized (review D4): a CLI that predates the flag answers
    "unknown option" with a non-zero exit, which the retry loop would otherwise
    misread as a generic error and burn every token before failing. We check
    ``--help`` up front and route to the plain text path when absent, instead of
    trial-and-erroring on real model calls.
    """
    global _JSON_SCHEMA_SUPPORTED
    if _JSON_SCHEMA_SUPPORTED is not None:
        return _JSON_SCHEMA_SUPPORTED
    try:
        import subprocess

        out = subprocess.run(
            [claude_cli, "--help"],
            capture_output=True,
            text=True,
            timeout=max(0.001, min(10, timeout_s)),
        )
        _JSON_SCHEMA_SUPPORTED = "--json-schema" in (out.stdout + out.stderr)
    except Exception:
        # If we can't even probe, assume unsupported and fall back to text.
        _JSON_SCHEMA_SUPPORTED = False
    return _JSON_SCHEMA_SUPPORTED


def _serialize_schema(json_schema: dict[str, Any]) -> str:
    """Compact-serialize a JSON Schema for the ``--json-schema`` argv value.

    Compact separators minimize argv length. Never log the value (it may carry
    field descriptions). Raises ValueError if it exceeds ``_MAX_SCHEMA_BYTES``
    so the caller can fall back to the text path rather than hit E2BIG.
    """
    import json as _json

    blob = _json.dumps(json_schema, separators=(",", ":"))
    if len(blob.encode("utf-8")) > _MAX_SCHEMA_BYTES:
        raise ValueError(
            f"json_schema too large for argv ({len(blob)} chars > {_MAX_SCHEMA_BYTES})"
        )
    return blob


def _parse_json_envelope(
    stdout: str,
) -> tuple[str, dict[str, Any] | None, dict[str, int] | None, bool]:
    """Parse JSON stdout into ``(text, structured, usage, is_error)``.

    Defensive per review D2/D5:
    - Accepts a single JSON object OR newline-delimited events; in the NDJSON
      case the last object with ``type == "result"`` wins (ignores log/event
      noise — NO generic balanced-brace scan).
    - ``structured`` comes from the ``structured_output`` field (the actual
      answer); ``text`` is the human-prose ``result`` field (NOT the answer —
      do not feed it to a schema validator).
    - ``usage`` are the REAL token counts (``usage.input_tokens`` /
      ``usage.output_tokens``) for the cost ledger.
    - Preserves the envelope's explicit ``is_error`` bit so an exit-0 error
      cannot be mistaken for a successful structured response.
    - Returns ``("", None, None, False)`` for unparseable input so the caller
      routes it through the existing empty-output gate.
    """
    import json as _json

    envelope: dict[str, Any] | None = None
    text = (stdout or "").strip()
    if not text:
        return "", None, None, False

    # Fast path: whole stdout is one JSON object.
    try:
        obj = _json.loads(text)
        if isinstance(obj, dict):
            envelope = obj
    except _json.JSONDecodeError:
        # NDJSON / events: take the last well-formed object whose type=="result".
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "result":
                envelope = obj
                break
            if isinstance(obj, dict) and envelope is None:
                envelope = obj  # last-resort: any object

    if envelope is None:
        return "", None, None, False

    structured = envelope.get("structured_output")
    if not isinstance(structured, dict):
        structured = None

    result_text = envelope.get("result")
    text_out = result_text if isinstance(result_text, str) else ""

    usage_raw = envelope.get("usage") or {}
    usage: dict[str, int] | None = None
    if isinstance(usage_raw, dict):
        it = usage_raw.get("input_tokens")
        ot = usage_raw.get("output_tokens")
        if isinstance(it, int) and isinstance(ot, int):
            usage = {"input_tokens": it, "output_tokens": ot}

    is_error = envelope.get("is_error") is True
    if not is_error and structured is None:
        # Diagnostic: an envelope arrived but carried no structured_output. The
        # caller will retry; only log the public envelope type, never payload.
        logger.warning(
            "claude --json-schema envelope had no structured_output (type=%s)",
            envelope.get("type"),
        )

    return text_out, structured, usage, is_error


async def complete_async(
    prompt: str,
    *,
    model: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S,
    endpoint: str | None = None,
    request_id: str | None = None,
    json_schema: dict[str, Any] | None = None,
) -> ClaudeOAuthResponse:
    """Run ``claude -p`` with 4-token fallback and return the text completion.

    When ``json_schema`` is provided AND the CLI supports ``--json-schema``,
    the call switches to ``--output-format json --json-schema <schema>`` and
    the parsed ``structured_output`` is returned in ``ClaudeOAuthResponse.
    structured``. When ``json_schema`` is None (default) the behavior is the
    original plain-text path, byte-for-byte. If the CLI lacks the flag, the
    schema is silently dropped and the text path runs (caller validates).

    Every call — successful or not — is recorded through
    :func:`backend.services.observability.record_llm_call` with provider
    ``claude_oauth``. Since the CLI does not report usage metadata we
    estimate tokens as ``len(text) // 4`` (industry rule-of-thumb).

    Args:
        prompt: The user prompt (system-prompt handling is deferred to the
            CLI — pass everything inline for now).
        model: Optional model id forwarded as ``claude -p --model <id>``.
            Accepts any slug the CLI accepts (``claude-opus-4-7``,
            ``claude-sonnet-4-6``, ``claude-haiku-4-5``, …).
        timeout_s: Per-seat wall-clock timeout.
        total_timeout_s: Hard wall-clock budget for the entire fallback call.
            Every seat receives ``min(timeout_s, remaining_global_budget)``.
        endpoint: Caller identifier for cost attribution. Strongly
            recommended.
        request_id: HTTP correlation id if available.

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
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if total_timeout_s <= 0:
        raise ValueError("total_timeout_s must be positive")

    tokens = _collect_tokens()
    start = time.monotonic()
    deadline = start + total_timeout_s
    last_error = ""
    attempts_made = 0
    # Reported only at the end (success OR failure)
    _recorder_model = model or "claude-unknown"
    _recorder_input_tokens = max(1, len(prompt) // 4)
    _recorder_output_tokens = 0
    _recorder_success = False
    _recorder_error_class: str | None = None
    # Provenance of the token counts reported to the cost ledger (review D7):
    # "cli_envelope" = real counts parsed from --output-format json,
    # "estimated" = len//4 rule-of-thumb (the legacy default).
    _recorder_usage_source = "estimated"

    # OTEL span wraps the whole retry loop so the dashboard sees one
    # invocation per logical call (with attempts as an attribute), not
    # one per token-fallback attempt — matches the granularity the
    # other LLM clients emit through their auto-instrumentors.
    # Started here, ended in the success-path `finally` and in the
    # all-tokens-failed path below; both code paths set output_tokens
    # and success attributes on _span before the manager exits.
    # Note: in the unlikely path of `ClaudeOAuthNotAvailable` raised
    # from `create_subprocess_exec`, the span context is leaked. The
    # leak is harmless when OTEL is disabled (nullcontext) and
    # surfaces as a long-running span when enabled — acceptable for
    # Phase 0; a follow-up can migrate this to a proper async with.
    _otel_span_ctx = _start_claude_cli_span(_recorder_model, _recorder_input_tokens)
    _span = _otel_span_ctx.__enter__()
    _span_set: Any = _span if hasattr(_span, "set_attribute") else None
    claude_cli = _resolve_claude_cli()

    # Decide ONCE whether this call runs the structured path. Conditions (all
    # must hold): caller passed a schema, the CLI advertises --json-schema, and
    # the schema serializes within the argv cap. Any failure → text path
    # (the binding/caller still validates locally). Keeps the schema branch
    # fully isolated from the unchanged text branch (review D3).
    schema_blob: str | None = None
    if json_schema is not None:
        # Probe the CLI's --help off the event loop: the first call shells out
        # synchronously (memoized after), and a blocking subprocess.run inside a
        # coroutine would freeze sibling tasks on a shared loop (panel: both LLMs
        # flagged the cron-headless risk). asyncio.to_thread keeps the loop free.
        supports = _JSON_SCHEMA_SUPPORTED
        if supports is None:
            probe_budget_s = deadline - time.monotonic()
            if probe_budget_s <= 0:
                supports = False
                last_error = "global_deadline"
            else:
                try:
                    supports = await asyncio.wait_for(
                        asyncio.to_thread(
                            _cli_supports_json_schema,
                            claude_cli,
                            probe_budget_s,
                        ),
                        timeout=probe_budget_s,
                    )
                except asyncio.TimeoutError:
                    supports = False
                    last_error = "global_deadline"
        if supports:
            try:
                schema_blob = _serialize_schema(json_schema)
            except ValueError as exc:
                logger.warning("json_schema dropped, falling back to text: %s", exc)
        else:
            logger.info("claude CLI lacks --json-schema; using text path")
    use_schema = schema_blob is not None

    for attempt, (token, label) in enumerate(tokens, start=1):
        remaining_global_s = deadline - time.monotonic()
        if remaining_global_s <= 0:
            last_error = "global_deadline"
            logger.warning(
                "claude OAuth global deadline exhausted after %d attempt(s)",
                attempts_made,
            )
            break
        attempts_made = attempt
        seat_deadline = min(deadline, time.monotonic() + timeout_s)

        # No bypassPermissions: tools are explicitly disallowed and the
        # default permission mode fails-closed on any tool the model still
        # attempts. The `--` sentinel guarantees the (possibly untrusted)
        # prompt is parsed as an operand, never as a flag.
        cmd: list[str] = [
            claude_cli,
            "-p",
            "--disallowedTools",
            *_DISALLOWED_TOOLS,
        ]
        if model:
            if not _ALLOWED_MODEL_RE.match(model):
                raise ValueError(f"model not allowed: {model!r}")
            cmd.extend(["--model", model])
        # Structured-output flags go BEFORE the `--` sentinel so the prompt
        # operand stays last and unambiguous (review D6).
        if use_schema:
            cmd.extend(["--output-format", "json", "--json-schema", schema_blob])  # type: ignore[list-item]
        cmd.append("--")
        cmd.append(prompt)

        env = _build_env(token)

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=max(0.0, seat_deadline - time.monotonic()),
            )
        except FileNotFoundError as exc:
            raise ClaudeOAuthNotAvailable(
                "`claude` CLI not found in PATH. Install: https://claude.ai/code",
            ) from exc
        except asyncio.TimeoutError:
            if time.monotonic() >= deadline:
                last_error = "global_deadline"
                logger.warning("claude OAuth global deadline exhausted during CLI launch")
                break
            last_error = f"{label}: launch_timeout"
            logger.warning("%s: CLI launch timed out, trying next", label)
            continue

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=max(0.0, seat_deadline - time.monotonic()),
            )
        except asyncio.TimeoutError:
            await _kill_and_reap(proc)
            if time.monotonic() >= deadline:
                last_error = "global_deadline"
                logger.warning("claude OAuth global deadline exhausted during CLI attempt")
                break
            last_error = f"{label}: attempt_timeout"
            logger.warning("%s: CLI attempt timed out, trying next", label)
            continue

        exit_code = proc.returncode or 0
        output = (stdout_b.decode(errors="replace") or "").strip()
        stderr = (stderr_b.decode(errors="replace") or "").strip()

        # Scanning a SUCCESS JSON envelope for rate-limit words would
        # false-positive on legitimate content ("quota"/"capacity" inside
        # structured_output). But that risk only exists on a *successful* run
        # (exit 0): when exit_code != 0 the stdout is an error, not a real
        # structured answer, so scanning it is safe AND necessary — the CLI can
        # emit a rate-limit error on stdout. So isolate-to-stderr ONLY on
        # exit 0; on failure scan both (review D5, panel cross-check Gemini+DeepSeek).
        rl_scan = stderr if (use_schema and exit_code == 0) else f"{output}\n{stderr}"

        if exit_code != 0 and RATE_LIMIT_PATTERN.search(rl_scan):
            last_error = f"{label}: rate limited"
            logger.warning("%s: rate limited, trying next", label)
            continue

        # Parse the structured envelope up front so an error/empty envelope
        # routes through the same empty-output gate as the text path.
        parsed_text = output
        parsed_structured: dict[str, Any] | None = None
        parsed_usage: dict[str, int] | None = None
        structured_error = False
        if use_schema and exit_code == 0:
            (
                parsed_text,
                parsed_structured,
                parsed_usage,
                structured_error,
            ) = _parse_json_envelope(output)
            if structured_error:
                diagnostic_class = _classify_cli_diagnostic(parsed_text) or "structured_error"
                last_error = f"{label}: {diagnostic_class}"
                logger.warning(
                    "%s: CLI structured error (%s), trying next",
                    label,
                    diagnostic_class,
                )
                continue
            # Structured path only "succeeds" if we got a structured_output.
            # Missing envelope → empty so the token loop retries, and the
            # caller's text fallback can run on a clean separate call.
            effective_output = parsed_text if parsed_structured is not None else ""
        else:
            effective_output = output

        if exit_code == 0 and not use_schema:
            diagnostic_class = _classify_cli_diagnostic(output)
            if diagnostic_class is None:
                diagnostic_class = _classify_cli_diagnostic(stderr)
            if diagnostic_class is not None:
                last_error = f"{label}: {diagnostic_class}"
                logger.warning(
                    "%s: CLI diagnostic (%s), trying next",
                    label,
                    diagnostic_class,
                )
                continue

        if not effective_output and exit_code in (0, 143) and parsed_structured is None:
            last_error = f"{label}: empty_output"
            logger.warning("%s: empty CLI output, trying next", label)
            continue

        if exit_code != 0:
            last_error = f"{label}: cli_exit_{exit_code}"
            logger.warning("%s: CLI failed (exit=%d), trying next", label, exit_code)
            continue

        elapsed = time.monotonic() - start
        logger.info("claude -p success via %s (%.2fs, attempt %d)", label, elapsed, attempt)
        # Prefer REAL token counts from the structured envelope; else estimate.
        if parsed_usage is not None:
            _recorder_input_tokens = parsed_usage["input_tokens"]
            _recorder_output_tokens = parsed_usage["output_tokens"]
            _recorder_usage_source = "cli_envelope"
        else:
            # Estimate on the FULL stdout stream, not parsed_text: in the schema
            # path parsed_text is only the short prose ``result`` while the real
            # payload lives in structured_output — estimating on parsed_text
            # would under-bill the ledger by orders of magnitude (panel: Gemini
            # CRITICO / DeepSeek MEDIO). On the text path output == parsed_text,
            # so this stays byte-identical to the original behavior.
            _recorder_output_tokens = max(1, len(output) // 4)
            _recorder_usage_source = "estimated"
        _recorder_success = True
        if _span_set is not None:
            _span_set.set_attribute("gen_ai.usage.input_tokens", _recorder_input_tokens)
            _span_set.set_attribute("gen_ai.usage.output_tokens", _recorder_output_tokens)
            _span_set.set_attribute("nuzantara.claude_oauth.token_label", label)
            _span_set.set_attribute("nuzantara.claude_oauth.attempts", attempt)
        try:
            return ClaudeOAuthResponse(
                text=parsed_text,
                token_label=label,
                elapsed_s=elapsed,
                attempts=attempt,
                structured=parsed_structured,
            )
        finally:
            _otel_span_ctx.__exit__(None, None, None)
            await _record_claude_oauth_call(
                model=_recorder_model,
                input_tokens=_recorder_input_tokens,
                output_tokens=_recorder_output_tokens,
                success=_recorder_success,
                latency_ms=int((time.monotonic() - start) * 1000),
                endpoint=endpoint,
                request_id=request_id,
                error_class=_recorder_error_class,
                usage_source=_recorder_usage_source,
            )

    err = ClaudeOAuthError(
        f"Claude OAuth failed after {attempts_made} attempt(s). "
        f"Last error class: {last_error or 'unknown'}",
    )
    _recorder_error_class = type(err).__name__
    if _span_set is not None:
        try:
            from opentelemetry.trace import Status, StatusCode

            _span_set.set_attribute("nuzantara.claude_oauth.attempts", attempts_made)
            _span_set.set_attribute("error.message", last_error[:200])
            _span_set.set_status(Status(StatusCode.ERROR, "all OAuth tokens failed"))
        except Exception:
            pass
    _otel_span_ctx.__exit__(type(err), err, err.__traceback__)
    await _record_claude_oauth_call(
        model=_recorder_model,
        input_tokens=_recorder_input_tokens,
        output_tokens=_recorder_output_tokens,
        success=False,
        latency_ms=int((time.monotonic() - start) * 1000),
        endpoint=endpoint,
        request_id=request_id,
        error_class=_recorder_error_class,
        usage_source=_recorder_usage_source,
    )
    raise err


async def _record_claude_oauth_call(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    success: bool,
    latency_ms: int,
    endpoint: str | None,
    request_id: str | None,
    error_class: str | None,
    usage_source: str = "estimated",
) -> None:
    """Record a Claude OAuth call to the cost ledger. Never raises.

    ``usage_source`` ("cli_envelope" | "estimated") records whether the token
    counts are real (parsed from the ``--output-format json`` envelope) or the
    ``len // 4`` estimate (review D7). It is logged, NOT pushed into
    ``record_llm_call``'s schema — that DB contract is shared and must not drift
    from a single side (superscar #9).
    """
    try:
        from backend.services.llm_clients.pricing import calculate_cost
        from backend.services.observability import record_llm_call

        cost_usd = calculate_cost(input_tokens, output_tokens, model)
        if usage_source == "cli_envelope":
            logger.debug(
                "claude_oauth cost-ledger: real tokens in=%d out=%d (cli_envelope)",
                input_tokens,
                output_tokens,
            )
        await record_llm_call(
            provider="claude_oauth",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            success=success,
            latency_ms=latency_ms,
            endpoint=endpoint,
            request_id=request_id,
            error_class=error_class,
        )
    except Exception as exc:
        logger.warning("llm_cost recorder failed for claude_oauth: %s", exc)


def complete(
    prompt: str,
    *,
    model: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S,
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

    return asyncio.run(
        complete_async(
            prompt,
            model=model,
            timeout_s=timeout_s,
            total_timeout_s=total_timeout_s,
        )
    )
