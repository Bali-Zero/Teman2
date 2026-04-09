# scripts/zantara-gateway/acp_client.py
"""
ACP (Agent Client Protocol) client for persistent Gemini CLI connection.

Architecture: a single reader task reads ALL lines from stdout and dispatches
them to the appropriate consumer via asyncio queues. This avoids the buffering
issue where _rpc() and prompt_stream() competed for stdout lines.

    ┌─────────────┐    stdin     ┌───────────────┐
    │  acp_client  │ ──────────► │  gemini --acp  │
    │  (Python)    │ ◄────────── │  (Node.js)     │
    └──────┬──────┘    stdout    └───────────────┘
           │
    _reader_loop task reads ALL lines from stdout
           │
    ┌──────▼──────┐
    │  _dispatch   │──► _rpc_responses[id] (asyncio.Future)
    │              │──► _notification_queue (asyncio.Queue for prompt_stream)
    │              │──► _server_requests (auto-respond: approve, readFile)
    └─────────────┘
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator

logger = logging.getLogger("zantara-gateway.acp")

_next_id = 0


def _get_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


class ACPGeminiClient:
    """Persistent connection to Gemini CLI via ACP protocol."""

    def __init__(
        self,
        gemini_path: str = "gemini",
        cwd: str = ".",
        mcp_server_command: str = "",
        mcp_server_args: list[str] | None = None,
        mcp_server_env: dict[str, str] | None = None,
        persona_primer: str = "",
    ):
        self._gemini_path = gemini_path
        self._cwd = cwd
        self._persona_primer = persona_primer
        # MCP server config in ACP format
        self._mcp_servers: list[dict] = []
        if mcp_server_command:
            env_list = [{"name": k, "value": v} for k, v in (mcp_server_env or {}).items()]
            self._mcp_servers = [{
                "name": "nuzantara",
                "command": mcp_server_command,
                "args": mcp_server_args or [],
                "env": env_list,
            }]
        self._proc: asyncio.subprocess.Process | None = None
        self._session_id: str = ""
        self._ready = False
        self._prompt_lock = asyncio.Lock()

        # Dispatcher state
        self._reader_task: asyncio.Task | None = None
        self._rpc_futures: dict[int, asyncio.Future] = {}
        self._notification_queue: asyncio.Queue[dict] = asyncio.Queue()

    def is_ready(self) -> bool:
        return self._ready and self._proc is not None and self._proc.returncode is None

    async def connect(self) -> None:
        """Spawn Gemini CLI in ACP mode, start reader, initialize session."""
        self._proc = await asyncio.create_subprocess_exec(
            self._gemini_path, "--acp",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("ACP process spawned: pid=%d", self._proc.pid)

        # Start the reader loop
        self._reader_task = asyncio.create_task(self._reader_loop())

        # Initialize
        resp = await self._rpc("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {},
        })
        if not resp or "error" in resp:
            raise RuntimeError(f"ACP initialize failed: {resp}")
        logger.info("ACP initialized")

        # Authenticate
        resp = await self._rpc("authenticate", {"methodId": "oauth-personal"})
        if resp and "error" in resp:
            raise RuntimeError(f"ACP authenticate failed: {resp}")
        logger.info("ACP authenticated")

        # Create session with MCP servers
        resp = await self._rpc("session/new", {
            "cwd": self._cwd,
            "mcpServers": self._mcp_servers,
        }, timeout=60)
        if not resp or "error" in resp:
            raise RuntimeError(f"ACP session/new failed: {resp}")
        self._session_id = resp.get("result", {}).get("sessionId", "")
        if not self._session_id:
            raise RuntimeError("No sessionId returned")

        self._first_prompt_sent = False
        self._ready = True
        logger.info("ACP session ready: %s", self._session_id[:20])

    async def close(self) -> None:
        self._ready = False
        self._session_id = ""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
        self._proc = None
        # Cancel pending futures
        for fut in self._rpc_futures.values():
            if not fut.done():
                fut.cancel()
        self._rpc_futures.clear()

    # ── Reader loop (single consumer of stdout) ──

    async def _reader_loop(self) -> None:
        """Read ALL lines from stdout and dispatch to appropriate consumer."""
        try:
            while True:
                raw = await self._proc.stdout.readline()
                if not raw:
                    logger.warning("ACP stdout closed")
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_id = obj.get("id")
                method = obj.get("method", "")

                # 1. RPC response (has id, has result or error, no method)
                if msg_id is not None and not method and ("result" in obj or "error" in obj):
                    fut = self._rpc_futures.get(msg_id)
                    if fut and not fut.done():
                        fut.set_result(obj)
                    continue

                # 2. Server request (has id AND method) — auto-respond
                if msg_id is not None and method:
                    await self._handle_server_request(msg_id, method, obj.get("params", {}))
                    continue

                # 3. Notification (has method, no id) — push to queue
                if method:
                    await self._notification_queue.put(obj)
                    continue

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("ACP reader loop error: %s", e)

    async def _handle_server_request(self, req_id: int, method: str, params: dict) -> None:
        """Auto-respond to server requests (permission, file reads, etc.)."""
        if "permission" in method.lower() or "Permission" in method:
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {
                "outcome": {"outcome": "approved"}
            }}
        elif "readTextFile" in method or "ReadTextFile" in method:
            path = params.get("path", "")
            content = ""
            try:
                content = Path(path).read_text()[:10000]
            except Exception:
                pass
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": content}}
        elif "writeTextFile" in method or "WriteTextFile" in method:
            # Deny writes in gateway context
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
        elif "createTerminal" in method or "CreateTerminal" in method:
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"terminalId": "gateway-noop"}}
        else:
            logger.debug("ACP auto-responding to unknown request: %s", method)
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}

        self._proc.stdin.write((json.dumps(resp) + "\n").encode())
        await self._proc.stdin.drain()

    # ── RPC (for init/auth/session) ──

    async def _rpc(self, method: str, params: dict, timeout: float = 30) -> dict | None:
        """Send JSON-RPC request and wait for response via future."""
        rid = _get_id()
        fut: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._rpc_futures[rid] = fut

        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        self._proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self._proc.stdin.drain()

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning("ACP RPC timeout: %s", method)
            return None
        finally:
            self._rpc_futures.pop(rid, None)

    # ── Prompt streaming (for chat) ──

    def _build_prompt(self, query: str) -> str:
        """Prepend persona primer to the first prompt of a session."""
        if not self._persona_primer or self._first_prompt_sent:
            return query
        self._first_prompt_sent = True
        return f"{self._persona_primer}\n\n---\n\n{query}"

    async def prompt_stream(self, query: str) -> AsyncIterator[str]:
        """Send prompt and yield SSE lines as agent responds."""
        if not self.is_ready():
            raise RuntimeError("ACP not ready")

        async with self._prompt_lock:
            # Drain any stale notifications
            while not self._notification_queue.empty():
                try:
                    self._notification_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            rid = _get_id()
            fut: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
            self._rpc_futures[rid] = fut

            msg = {
                "jsonrpc": "2.0",
                "id": rid,
                "method": "session/prompt",
                "params": {
                    "sessionId": self._session_id,
                    "prompt": [{"type": "text", "text": self._build_prompt(query)}],
                },
            }
            self._proc.stdin.write((json.dumps(msg) + "\n").encode())
            await self._proc.stdin.drain()
            logger.info("ACP prompt sent: %s", query[:50])

            # Read notifications until we get the response
            try:
                while True:
                    # Check if response arrived
                    if fut.done():
                        yield "data: [DONE]\n\n"
                        return

                    # Read next notification (with timeout)
                    try:
                        notif = await asyncio.wait_for(
                            self._notification_queue.get(), timeout=2.0
                        )
                    except asyncio.TimeoutError:
                        # No notification yet — check if response arrived
                        if fut.done():
                            yield "data: [DONE]\n\n"
                            return
                        continue

                    # Convert notification to SSE
                    sse = self._notif_to_sse(notif)
                    if sse:
                        yield sse

            except Exception as e:
                logger.error("ACP prompt_stream error: %s", e)
                yield f'data: {json.dumps({"type": "error", "data": str(e)})}\n\n'
                yield "data: [DONE]\n\n"
            finally:
                self._rpc_futures.pop(rid, None)

    @staticmethod
    def _notif_to_sse(notif: dict) -> str | None:
        """Convert ACP notification to SSE format for widget."""
        method = notif.get("method", "")
        if method != "session/update":
            return None

        update = notif.get("params", {}).get("update", {})
        su = update.get("sessionUpdate", "")

        if su == "agent_message_chunk":
            content = update.get("content", {})
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text", "")
                if text:
                    return f'data: {json.dumps({"type": "token", "data": text}, separators=(",", ":"))}\n\n'

        if su == "tool_call_start":
            name = update.get("toolName", "")
            return f'data: {json.dumps({"type": "tool_call", "data": {"name": name}}, separators=(",", ":"))}\n\n'

        if su == "tool_call_end":
            name = update.get("toolName", "")
            return f'data: {json.dumps({"type": "tool_result", "data": {"name": name}}, separators=(",", ":"))}\n\n'

        return None
