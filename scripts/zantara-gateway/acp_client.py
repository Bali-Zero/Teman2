# scripts/zantara-gateway/acp_client.py
"""
ACP (Agent Client Protocol) client for persistent Gemini CLI connection.

Instead of spawning a new Gemini CLI process per request (8-10s cold start),
this maintains a single persistent Gemini CLI process via ACP JSON-RPC over stdio.

Protocol verified: initialize → authenticate → session/new → session/prompt
Notifications: sessionUpdate=agent_message_chunk with content.type=text
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger("zantara-gateway.acp")

# JSON-RPC request ID counter
_next_id = 0


def _get_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


class ACPGeminiClient:
    """Persistent connection to Gemini CLI via ACP protocol."""

    def __init__(self, gemini_path: str = "gemini", cwd: str = "."):
        self._gemini_path = gemini_path
        self._cwd = cwd
        self._proc: asyncio.subprocess.Process | None = None
        self._session_id: str = ""
        self._ready = False
        self._lock = asyncio.Lock()  # serialize prompts

    def is_ready(self) -> bool:
        """True if ACP session is initialized and ready for prompts."""
        return self._ready and self._proc is not None and self._proc.returncode is None

    async def connect(self) -> None:
        """Spawn Gemini CLI in ACP mode and initialize session."""
        self._proc = await asyncio.create_subprocess_exec(
            self._gemini_path, "--acp",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("ACP process spawned: pid=%d", self._proc.pid)

        # 1. Initialize
        resp = await self._rpc("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {},
        }, timeout=10)
        if not resp or "error" in resp:
            raise RuntimeError(f"ACP initialize failed: {resp}")
        logger.info("ACP initialized")

        # 2. Authenticate (uses oauth-personal from ~/.gemini/settings.json)
        resp = await self._rpc("authenticate", {
            "methodId": "oauth-personal",
        }, timeout=10)
        if resp and "error" in resp:
            raise RuntimeError(f"ACP authenticate failed: {resp}")
        logger.info("ACP authenticated")

        # 3. Create session
        resp = await self._rpc("session/new", {
            "cwd": self._cwd,
            "mcpServers": [],  # uses servers from settings.json
        }, timeout=15)
        if not resp or "error" in resp:
            raise RuntimeError(f"ACP session/new failed: {resp}")
        self._session_id = resp.get("result", {}).get("sessionId", "")
        if not self._session_id:
            raise RuntimeError(f"ACP session/new returned no sessionId: {resp}")

        self._ready = True
        logger.info("ACP session ready: %s", self._session_id[:20])

    async def close(self) -> None:
        """Kill the persistent Gemini CLI process."""
        self._ready = False
        self._session_id = ""
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            logger.info("ACP process killed")
        self._proc = None

    async def prompt_stream(self, query: str) -> AsyncIterator[str]:
        """Send a prompt and yield SSE lines as they arrive.

        Yields SSE-formatted strings compatible with the widget:
          data: {"type":"token","data":"text"}\n\n
          data: {"type":"tool_call","data":{...}}\n\n
          data: [DONE]\n\n
        """
        if not self.is_ready():
            raise RuntimeError("ACP not ready. Call connect() first.")

        async with self._lock:  # one prompt at a time
            rid = _get_id()
            msg = {
                "jsonrpc": "2.0",
                "id": rid,
                "method": "session/prompt",
                "params": {
                    "sessionId": self._session_id,
                    "prompt": [{"type": "text", "text": query}],
                },
            }
            logger.info("ACP prompt sending: rid=%d query=%s", rid, query[:50])
            self._proc.stdin.write((json.dumps(msg) + "\n").encode())
            await self._proc.stdin.drain()
            logger.info("ACP prompt sent, reading response...")

            # Read until we get the response with our id
            try:
                while True:
                    raw = await asyncio.wait_for(
                        self._proc.stdout.readline(), timeout=120
                    )
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("ACP non-JSON line: %s", line[:100])
                        continue

                    # Response to our request — done
                    if obj.get("id") == rid:
                        yield "data: [DONE]\n\n"
                        return

                    method = obj.get("method", "")

                    # Notification — session/update (streaming chunks)
                    if method == "session/update":
                        sse = self._update_to_sse(obj.get("params", {}).get("update", {}))
                        if sse:
                            yield sse
                        continue

                    # Server request — requestPermission (auto-approve tool calls)
                    if method == "session/requestPermission":
                        req_id = obj.get("id")
                        if req_id is not None:
                            approve = {"jsonrpc": "2.0", "id": req_id, "result": {"outcome": {"outcome": "approved"}}}
                            self._proc.stdin.write((json.dumps(approve) + "\n").encode())
                            await self._proc.stdin.drain()
                            logger.debug("ACP auto-approved tool call")
                        continue

                    # Server request — readTextFile
                    if method == "session/readTextFile":
                        req_id = obj.get("id")
                        path = obj.get("params", {}).get("path", "")
                        content = ""
                        try:
                            with open(path) as f:
                                content = f.read()
                        except Exception:
                            pass
                        if req_id is not None:
                            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": content}}
                            self._proc.stdin.write((json.dumps(resp) + "\n").encode())
                            await self._proc.stdin.drain()
                        continue

                    # Server request — writeTextFile (deny in gateway context)
                    if method == "session/writeTextFile":
                        req_id = obj.get("id")
                        if req_id is not None:
                            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                            self._proc.stdin.write((json.dumps(resp) + "\n").encode())
                            await self._proc.stdin.drain()
                        continue

                    logger.debug("ACP unhandled: %s", line[:200])

            except asyncio.TimeoutError:
                logger.warning("ACP prompt timeout after 120s")
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("ACP prompt error: %s", e)
                yield f'data: {json.dumps({"type": "error", "data": str(e)})}\n\n'
                yield "data: [DONE]\n\n"

    async def _rpc(self, method: str, params: dict, timeout: float = 15) -> dict | None:
        """Send a JSON-RPC request and wait for the response."""
        rid = _get_id()
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        self._proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self._proc.stdin.drain()

        # Read lines until we get our response
        try:
            while True:
                raw = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=timeout
                )
                if not raw:
                    return None
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("id") == rid:
                    return obj
                # Skip notifications during init
        except asyncio.TimeoutError:
            logger.warning("ACP RPC timeout: method=%s", method)
            return None

    @staticmethod
    def _update_to_sse(update: dict) -> str | None:
        """Convert an ACP session/update notification to SSE format."""
        session_update = update.get("sessionUpdate", "")

        if session_update == "agent_message_chunk":
            content = update.get("content", {})
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text", "")
                if text:
                    return f'data: {json.dumps({"type": "token", "data": text}, separators=(",", ":"))}\n\n'

        if session_update == "tool_call_start":
            tool_name = update.get("toolName", "")
            return f'data: {json.dumps({"type": "tool_call", "data": {"name": tool_name}}, separators=(",", ":"))}\n\n'

        if session_update == "tool_call_end":
            tool_name = update.get("toolName", "")
            return f'data: {json.dumps({"type": "tool_result", "data": {"name": tool_name}}, separators=(",", ":"))}\n\n'

        return None
