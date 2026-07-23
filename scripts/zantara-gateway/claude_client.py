# scripts/zantara-gateway/claude_client.py
"""
Claude CLI client for the gateway — spawns claude -p per request.

Used for admin (Zero) who wants Sonnet 4.6 instead of Gemini.
Claude CLI has native MCP support via --mcp-config.
Multi-account fallback: TOKEN_1→2→3→legacy→keychain.

Backend selection (``ZANTARA_CLAUDE_BACKEND``, default ``subprocess``):
  - ``subprocess`` (default): spawns the ``claude`` CLI directly (unchanged
    behavior, see ``_stream_via_subprocess``).
  - ``sdk`` (pilot, opt-in): drives the Claude Agent SDK instead
    (``_stream_via_sdk``). Sanctioned precedent: ``scripts/wr3_dispatch_agent.py``
    already uses ``claude_agent_sdk`` — it is a CLI subprocess wrapper under
    the hood, Law 1 compliant (see ``scripts/lint/wr3_lint_cli_only.py``
    ``ALLOWED_OVERRIDE``). Falls back permanently to the subprocess backend
    on ImportError, rate-limit, or SDK-reported error — the pilot must never
    crash the gateway.
"""

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger("zantara-gateway.claude")

_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|too many requests|429|exhausted|quota|hit your limit|"
    r"capacity|overloaded",
    re.IGNORECASE,
)

# Log the "package not installed" fallback once, not on every request.
_sdk_import_warned = False


def _token_chain() -> list[tuple[str, str]]:
    """Build ordered list of (label, token_or_empty) for fallback."""
    chain: list[tuple[str, str]] = []
    for i in (1, 2, 3, 4, 5):
        tok = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok:
            chain.append((f"token_{i}", tok))
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and not any(t == legacy for _, t in chain):
        chain.append(("token_legacy", legacy))
    chain.append(("keychain", ""))
    return chain


def _build_subprocess_cmd(
    query: str, model: str, mcp_config: str, system_prompt: str
) -> list[str]:
    """Build the argv for the subprocess ``claude`` CLI backend.

    ``--max-budget-usd`` is the runaway-loop cap for this tool-armed headless
    call-site (``--max-turns`` does NOT exist as a CLI flag — verified
    empirically on claude 2.1.211; adding it would crash every invocation
    with "unknown option").
    """
    cmd = [
        "claude",
        "-p", query,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--no-session-persistence",
        "--max-budget-usd", os.environ.get("ZANTARA_CLAUDE_MAX_BUDGET_USD", "5"),
    ]

    if mcp_config:
        cmd.extend(["--mcp-config", mcp_config])

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # Low effort for faster responses when query is simple
    if len(query) < 100:
        cmd.extend(["--effort", "low"])

    return cmd


def _build_sdk_env() -> dict[str, str]:
    """Env vars for the SDK-spawned CLI subprocess.

    Strips ``ANTHROPIC_API_KEY`` unconditionally — same rule as
    ``claude_oauth_client._build_env`` (Golden Rule: never let the
    SDK's underlying CLI silently pick up a pay-as-you-go key).

    Seeds ``CLAUDE_CODE_OAUTH_TOKEN`` from the first non-empty entry of
    ``_token_chain()`` (TOKEN_1→2→3→legacy). Without this, a deployment
    that only sets the indexed ``CLAUDE_CODE_OAUTH_TOKEN_N`` vars (no
    legacy ``CLAUDE_CODE_OAUTH_TOKEN``) left the SDK-spawned CLI with no
    token at all — it fell through to keychain (or failed outright)
    instead of using the configured chain. If the chain resolves to the
    empty keychain sentinel (no token configured anywhere), the var is
    left untouched (current behavior, nothing invented).

    Rotation-on-exhaustion is deliberately NOT duplicated here: on
    rate-limit the SDK path already falls back to
    ``_stream_via_subprocess``, which walks the full chain itself
    (rotation-by-fallback, by design).
    """
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    _, token = _token_chain()[0]
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return env


# Known SDK lifecycle message classes: these carry ``subtype`` too (e.g.
# ``SystemMessage(subtype="init")`` is the FIRST message of every query), but
# are NOT a ResultMessage. The old rule (``hasattr(message, "subtype")``)
# misclassified every one of these as a terminal error result, so the SDK
# path fell back to subprocess on the first message of every single query
# (P1-1) — the pilot never actually streamed a token via the SDK.
_SDK_LIFECYCLE_CLASS_NAMES = frozenset(
    {"SystemMessage", "TaskStartedMessage", "TaskUpdatedMessage", "TaskCompletedMessage"}
)

# Attributes that, together with ``subtype``, discriminate a real
# ResultMessage from a lifecycle message when duck-typing (no exact class
# name match available — e.g. unit tests against mock objects, or an SDK
# message class not named above).
_RESULT_DISCRIMINANT_ATTRS = ("total_cost_usd", "is_error", "result")


def _sdk_message_kind(message: object) -> str:
    """Classify an SDK message by duck-typed shape.

    Duck-typing (not ``isinstance`` against the real SDK classes) so the
    conversion logic is testable with plain mock objects when the
    ``claude_agent_sdk`` package itself is not installed.

    Returns one of:
      - ``"result"``: a real terminal ResultMessage (success or error subtype).
      - ``"assistant"``: an AssistantMessage carrying content blocks to stream.
      - ``"skip"``: a lifecycle message (SystemMessage, Task*Message, ...)
        that carries ``subtype`` but is NOT a result — must never be
        mistaken for a terminal error (see P1-1 note above).
      - ``"unknown"``: anything else; treated the same as ``"skip"`` by the
        caller (ignored, stream continues).
    """
    name = type(message).__name__

    if name == "ResultMessage":
        return "result"
    if name == "AssistantMessage":
        return "assistant"
    if name in _SDK_LIFECYCLE_CLASS_NAMES or name.startswith("Task"):
        return "skip"

    # Duck-typed fallback: a real ResultMessage exposes `subtype` TOGETHER
    # WITH at least one result-only attribute — never `subtype` alone.
    has_subtype = hasattr(message, "subtype")
    if has_subtype and any(hasattr(message, attr) for attr in _RESULT_DISCRIMINANT_ATTRS):
        return "result"
    if hasattr(message, "content"):
        return "assistant"
    if has_subtype:
        # subtype present but none of the result-discriminant attrs —
        # lifecycle-shaped message (e.g. SystemMessage), skip rather than
        # guess.
        return "skip"
    return "unknown"


def _sdk_block_kind(block: object) -> str:
    """Classify one content block of an assistant-like SDK message."""
    name = type(block).__name__
    if name == "ToolResultBlock" or hasattr(block, "tool_use_id"):
        return "tool_result"
    if name == "ToolUseBlock" or hasattr(block, "input"):
        return "tool_use"
    if name == "TextBlock" or hasattr(block, "text"):
        return "text"
    return "unknown"


def _convert_sdk_message(
    message: object, seen_text: set[str]
) -> tuple[list[str], bool, str | None]:
    """Convert one Claude Agent SDK message into subprocess-identical SSE lines.

    Mirrors the stream-json conversion in ``_stream_via_subprocess`` line for
    line, so the gateway consumer cannot tell which backend produced the
    stream (same ``data: {...}\\n\\n`` format, same ``seen_text`` dedup, same
    trailing ``[DONE]``).

    Returns ``(sse_lines, is_terminal, error_subtype)``: ``is_terminal`` is
    True once a result message arrives (caller stops iterating);
    ``error_subtype`` is set when that result was NOT ``"success"`` so the
    caller can fall back to the subprocess backend.
    """
    lines: list[str] = []
    kind = _sdk_message_kind(message)

    if kind == "assistant":
        for block in getattr(message, "content", None) or []:
            block_kind = _sdk_block_kind(block)
            if block_kind == "text":
                text = getattr(block, "text", "") or ""
                if text and text not in seen_text:
                    seen_text.add(text)
                    lines.append(
                        f'data: {json.dumps({"type": "token", "data": text}, separators=(",", ":"))}\n\n'
                    )
            elif block_kind == "tool_use":
                name = getattr(block, "name", "") or ""
                lines.append(
                    f'data: {json.dumps({"type": "tool_call", "data": {"name": name}}, separators=(",", ":"))}\n\n'
                )
            elif block_kind == "tool_result":
                name = getattr(block, "tool_name", "") or getattr(block, "name", "") or ""
                lines.append(
                    f'data: {json.dumps({"type": "tool_result", "data": {"name": name}}, separators=(",", ":"))}\n\n'
                )
        return lines, False, None

    if kind == "result":
        subtype = getattr(message, "subtype", "") or ""
        if subtype == "success":
            # The result carries the final text, but assistant blocks already
            # streamed it — only emit it if nothing was streamed yet (safety
            # net, mirrors the subprocess path's "already streamed it" note).
            result_text = getattr(message, "result", "") or ""
            if result_text and result_text not in seen_text:
                seen_text.add(result_text)
                lines.append(
                    f'data: {json.dumps({"type": "token", "data": result_text}, separators=(",", ":"))}\n\n'
                )
            lines.append("data: [DONE]\n\n")
            return lines, True, None
        return lines, True, subtype or "unknown_error"

    return lines, False, None


async def stream_claude_cli(
    query: str,
    model: str = "sonnet",
    mcp_config: str = "",
    system_prompt: str = "",
    timeout: int = 120,
    cwd: str = "",
) -> AsyncIterator[str]:
    """Spawn Claude CLI headless and yield SSE lines. Multi-account fallback:
    tries each token, retries on rate limit.

    Backend selection via ``ZANTARA_CLAUDE_BACKEND`` (``subprocess`` default,
    ``sdk`` pilot opt-in) — the SSE contract is identical either way, so the
    gateway consumer never needs to know which backend produced the stream.

    Claude CLI stream-json format:
      {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
      {"type":"result","subtype":"success","result":"..."}
    """
    backend = os.environ.get("ZANTARA_CLAUDE_BACKEND", "subprocess").strip().lower()

    if backend == "sdk":
        async for line in _stream_via_sdk(
            query,
            model=model,
            mcp_config=mcp_config,
            system_prompt=system_prompt,
            timeout=timeout,
            cwd=cwd,
        ):
            yield line
        return

    async for line in _stream_via_subprocess(
        query,
        model=model,
        mcp_config=mcp_config,
        system_prompt=system_prompt,
        timeout=timeout,
        cwd=cwd,
    ):
        yield line


async def _stream_via_sdk(
    query: str,
    model: str = "sonnet",
    mcp_config: str = "",
    system_prompt: str = "",
    timeout: int = 120,
    cwd: str = "",
) -> AsyncIterator[str]:
    """Pilot backend: stream via the Claude Agent SDK instead of a raw subprocess.

    Opt-in via ``ZANTARA_CLAUDE_BACKEND=sdk``. Falls back permanently to
    ``_stream_via_subprocess`` on ImportError (package not installed), on
    rate-limit, or on any SDK-reported error — the pilot must never crash
    the gateway.
    """
    global _sdk_import_warned
    try:
        from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions  # type: ignore
    except ImportError as e:
        if not _sdk_import_warned:
            logger.warning(
                "claude_agent_sdk not installed — falling back to subprocess backend: %s", e
            )
            _sdk_import_warned = True
        async for line in _stream_via_subprocess(
            query,
            model=model,
            mcp_config=mcp_config,
            system_prompt=system_prompt,
            timeout=timeout,
            cwd=cwd,
        ):
            yield line
        return

    # Only pass fields the caller actually set — let the SDK's own defaults
    # apply to system_prompt/mcp_servers otherwise (mcp_servers accepts
    # dict|str|Path; we hand it the same --mcp-config path the subprocess
    # backend uses).
    options_kwargs: dict[str, Any] = {
        "model": model,
        "max_turns": int(os.environ.get("ZANTARA_CLAUDE_MAX_TURNS", "30")),
        "max_budget_usd": float(os.environ.get("ZANTARA_CLAUDE_MAX_BUDGET_USD", "5")),
        "env": _build_sdk_env(),
        "include_partial_messages": True,
    }
    if system_prompt:
        options_kwargs["system_prompt"] = system_prompt
    if mcp_config:
        options_kwargs["mcp_servers"] = mcp_config
    # P3-a: the subprocess backend passes `cwd` to the spawned process; the
    # SDK path was dropping it on the floor.
    if cwd:
        options_kwargs["cwd"] = cwd
    # P3-c: mirror the subprocess backend's `--effort low` for short queries
    # — ClaudeAgentOptions accepts the same `effort` field.
    if len(query) < 100:
        options_kwargs["effort"] = "low"
    options = ClaudeAgentOptions(**options_kwargs)

    seen_text: set[str] = set()
    # P1-2: once any real content/tool event has been yielded to the caller,
    # a subprocess fallback would REPLAY the whole response from scratch
    # (duplicate SSE tokens + double spend). Past that point an error or
    # timeout gets a single `error` SSE event + `[DONE]` instead of a
    # fallback — never a replay.
    yielded_any = False

    try:
        # Manual iteration (not `async for`) so each individual message wait
        # can be bounded by `timeout` (P3-b) — an SDK subprocess hung
        # mid-stream must not hang the gateway forever.
        message_iter = sdk_query(prompt=query, options=options).__aiter__()
        while True:
            try:
                message = await asyncio.wait_for(message_iter.__anext__(), timeout=timeout)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                if yielded_any:
                    logger.warning(
                        "Claude SDK timeout after %ds (mid-stream) — emitting error event, no replay",
                        timeout,
                    )
                    yield f'data: {json.dumps({"type": "error", "data": "timeout"}, separators=(",", ":"))}\n\n'
                    yield "data: [DONE]\n\n"
                else:
                    logger.warning(
                        "Claude SDK timeout after %ds — falling back to subprocess", timeout
                    )
                    async for line in _stream_via_subprocess(
                        query,
                        model=model,
                        mcp_config=mcp_config,
                        system_prompt=system_prompt,
                        timeout=timeout,
                        cwd=cwd,
                    ):
                        yield line
                return

            lines, is_terminal, error_subtype = _convert_sdk_message(message, seen_text)
            for line in lines:
                yield line
            if lines:
                yielded_any = True

            if is_terminal:
                if error_subtype is not None:
                    if yielded_any:
                        logger.warning(
                            "Claude SDK result error (%s) after streaming — emitting error event, no replay",
                            error_subtype,
                        )
                        yield f'data: {json.dumps({"type": "error", "data": error_subtype}, separators=(",", ":"))}\n\n'
                        yield "data: [DONE]\n\n"
                    else:
                        logger.warning(
                            "Claude SDK result error (%s) — falling back to subprocess",
                            error_subtype,
                        )
                        async for line in _stream_via_subprocess(
                            query,
                            model=model,
                            mcp_config=mcp_config,
                            system_prompt=system_prompt,
                            timeout=timeout,
                            cwd=cwd,
                        ):
                            yield line
                return
    except asyncio.CancelledError:
        raise
    except Exception as e:  # SDK-specific exception types vary by version
        text = str(e)
        if yielded_any:
            logger.warning(
                "Claude SDK error after streaming — emitting error event, no replay: %s", text
            )
            yield f'data: {json.dumps({"type": "error", "data": text}, separators=(",", ":"))}\n\n'
            yield "data: [DONE]\n\n"
            return
        if _RATE_LIMIT_RE.search(text):
            logger.warning("Claude SDK rate-limited — falling back to subprocess: %s", text)
        else:
            logger.warning("Claude SDK error — falling back to subprocess: %s", text)
        async for line in _stream_via_subprocess(
            query,
            model=model,
            mcp_config=mcp_config,
            system_prompt=system_prompt,
            timeout=timeout,
            cwd=cwd,
        ):
            yield line


async def _stream_via_subprocess(
    query: str,
    model: str = "sonnet",
    mcp_config: str = "",
    system_prompt: str = "",
    timeout: int = 120,
    cwd: str = "",
) -> AsyncIterator[str]:
    """Spawn Claude CLI headless and yield SSE lines.
    Multi-account fallback: tries each token, retries on rate limit.

    Claude CLI stream-json format:
      {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
      {"type":"result","subtype":"success","result":"..."}
    """
    cmd = _build_subprocess_cmd(query, model, mcp_config, system_prompt)

    # Try each token in the chain
    chain = _token_chain()
    for label, token in chain:
        env = os.environ.copy()
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

        logger.info("Spawning Claude CLI: model=%s, token=%s", model, label)

        # `limit` raises the StreamReader buffer above asyncio's 64KB default.
        # `claude -p --output-format stream-json --verbose --include-partial-messages`
        # emits the init/system NDJSON line carrying the full tool+MCP surface;
        # on a rich-MCP host it exceeds 64KB (measured 84053 bytes on Pro,
        # 2026-07-17), and `proc.stdout.readline()` below then dies with
        # `LimitOverrunError: Separator is found, but chunk is longer than
        # limit`, taking down the whole stream — including the SDK backend's
        # subprocess-fallback safety net. 1 MiB clears it with headroom.
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd or None,
            limit=1024 * 1024,
        )

        # Read first line to check for immediate rate-limit error
        try:
            first_line = await asyncio.wait_for(proc.stdout.readline(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning("Claude CLI %s: no output in 15s — trying next", label)
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            continue

        if first_line:
            decoded = first_line.decode("utf-8", errors="replace").strip()
            # Check stderr too
            stderr_data = b""
            if proc.stderr:
                try:
                    stderr_data = await asyncio.wait_for(proc.stderr.read(500), timeout=1)
                except asyncio.TimeoutError:
                    pass
            stderr_text = stderr_data.decode("utf-8", errors="replace")

            if _RATE_LIMIT_RE.search(decoded + stderr_text):
                logger.warning("Claude CLI %s rate-limited — trying next token", label)
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
                continue

        # Good — this token works, proceed with streaming
        break
    else:
        logger.error("All Claude tokens exhausted")
        yield "data: [DONE]\n\n"
        return

    try:
        seen_text = set()  # deduplicate partial messages

        # Process the first_line we already read during fallback check
        lines_to_process = [first_line] if first_line else []

        while True:
            if lines_to_process:
                raw = lines_to_process.pop(0)
            else:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")

            # Assistant message with content
            if msg_type == "assistant":
                message = obj.get("message", {})
                content_blocks = message.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        if text and text not in seen_text:
                            seen_text.add(text)
                            yield f'data: {json.dumps({"type": "token", "data": text}, separators=(",", ":"))}\n\n'

                # Tool use blocks
                for block in content_blocks:
                    if block.get("type") == "tool_use":
                        name = block.get("name", "")
                        yield f'data: {json.dumps({"type": "tool_call", "data": {"name": name}}, separators=(",", ":"))}\n\n'

            # Tool result
            elif msg_type == "tool_result":
                name = obj.get("tool_name", "")
                yield f'data: {json.dumps({"type": "tool_result", "data": {"name": name}}, separators=(",", ":"))}\n\n'

            # Final result
            elif msg_type == "result":
                # The result contains the final text, but we already streamed it
                yield "data: [DONE]\n\n"
                return

    except asyncio.TimeoutError:
        logger.warning("Claude CLI timeout after %ds", timeout)
        yield "data: [DONE]\n\n"
    except asyncio.CancelledError:
        raise
    finally:
        if proc.returncode is None:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
