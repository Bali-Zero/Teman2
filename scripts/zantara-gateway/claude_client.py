# scripts/zantara-gateway/claude_client.py
"""
Claude CLI client for the gateway — spawns claude -p per request.

Used for admin (Zero) who wants Sonnet 4.6 instead of Gemini.
Claude CLI has native MCP support via --mcp-config.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator

logger = logging.getLogger("zantara-gateway.claude")


async def stream_claude_cli(
    query: str,
    model: str = "sonnet",
    mcp_config: str = "",
    system_prompt: str = "",
    timeout: int = 120,
    cwd: str = "",
) -> AsyncIterator[str]:
    """Spawn Claude CLI headless and yield SSE lines.

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

    logger.info("Spawning Claude CLI: model=%s", model)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ},
        cwd=cwd or None,
    )

    try:
        seen_text = set()  # deduplicate partial messages
        while True:
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
