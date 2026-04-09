# scripts/zantara-gateway/claude_client.py
"""
Claude CLI client for the gateway — spawns claude -p per request.

Used for admin (Zero) who wants Sonnet 4.6 instead of Gemini.
Claude CLI has native MCP support via --mcp-config.
Multi-account fallback: TOKEN_1→2→3→legacy→keychain.
"""

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator

logger = logging.getLogger("zantara-gateway.claude")

_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|too many requests|429|exhausted|quota|hit your limit|"
    r"capacity|overloaded",
    re.IGNORECASE,
)


def _token_chain() -> list[tuple[str, str]]:
    """Build ordered list of (label, token_or_empty) for fallback."""
    chain: list[tuple[str, str]] = []
    for i in (1, 2, 3):
        tok = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok:
            chain.append((f"token_{i}", tok))
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and not any(t == legacy for _, t in chain):
        chain.append(("token_legacy", legacy))
    chain.append(("keychain", ""))
    return chain


async def stream_claude_cli(
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
    cmd = [
        "claude",
        "-p", query,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--no-session-persistence",
    ]

    if mcp_config:
        cmd.extend(["--mcp-config", mcp_config])

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # Low effort for faster responses when query is simple
    if len(query) < 100:
        cmd.extend(["--effort", "low"])

    # Try each token in the chain
    chain = _token_chain()
    for label, token in chain:
        env = os.environ.copy()
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

        logger.info("Spawning Claude CLI: model=%s, token=%s", model, label)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd or None,
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
