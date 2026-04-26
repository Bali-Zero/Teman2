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
import contextlib
import logging
import os
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass
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
    except Exception:  # noqa: BLE001 — OTEL must never break the host.
        return nullcontext()


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
    endpoint: str | None = None,
    request_id: str | None = None,
) -> ClaudeOAuthResponse:
    """Run ``claude -p`` with 3-token fallback and return the text completion.

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
        timeout_s: Per-attempt wall-clock timeout. The total cap is roughly
            ``timeout_s × len(tokens)``.
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

    tokens = _collect_tokens()
    start = time.monotonic()
    last_error = ""
    # Reported only at the end (success OR failure)
    _recorder_model = model or "claude-unknown"
    _recorder_input_tokens = max(1, len(prompt) // 4)
    _recorder_output_tokens = 0
    _recorder_success = False
    _recorder_error_class: str | None = None

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
            with contextlib.suppress(Exception):
                await proc.wait()
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
        _recorder_output_tokens = max(1, len(output) // 4)
        _recorder_success = True
        if _span_set is not None:
            _span_set.set_attribute("gen_ai.usage.output_tokens", _recorder_output_tokens)
            _span_set.set_attribute("nuzantara.claude_oauth.token_label", label)
            _span_set.set_attribute("nuzantara.claude_oauth.attempts", attempt)
        try:
            return ClaudeOAuthResponse(
                text=output,
                token_label=label,
                elapsed_s=elapsed,
                attempts=attempt,
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
            )

    err = ClaudeOAuthError(
        f"All {len(tokens)} OAuth attempts failed. Last error: {last_error}",
    )
    _recorder_error_class = type(err).__name__
    if _span_set is not None:
        try:
            from opentelemetry.trace import Status, StatusCode

            _span_set.set_attribute("nuzantara.claude_oauth.attempts", len(tokens))
            _span_set.set_attribute("error.message", last_error[:200])
            _span_set.set_status(Status(StatusCode.ERROR, "all OAuth tokens failed"))
        except Exception:  # noqa: BLE001 — never let OTEL break the host.
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
) -> None:
    """Record a Claude OAuth call to the cost ledger. Never raises."""
    try:
        from backend.services.llm_clients.pricing import calculate_cost
        from backend.services.observability import record_llm_call

        cost_usd = calculate_cost(input_tokens, output_tokens, model)
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
    except Exception as exc:  # noqa: BLE001 — never break the caller
        logger.warning("llm_cost recorder failed for claude_oauth: %s", exc)


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
