# Phase 3B — Local Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the workspace widget (kita.balizero.com) to a local Python gateway that spawns Gemini CLI headless with MCP tool calling, with Ollama Gemma 4 + MCP tools as fallback.

**Architecture:** A ~300-line Python gateway on `localhost:8090` (TLS via mkcert) that accepts SSE requests from the Vercel-hosted widget, spawns `gemini -p -o stream-json -y` per request, and converts NDJSON to SSE. Fallback path calls Ollama `/api/chat` with tool definitions from `server_agent.py` via MCP SDK. The widget tries localhost first, falls back to Fly.io backend RAG if gateway is unreachable.

**Tech Stack:** Python 3.11+ (aiohttp or uvicorn), Gemini CLI v0.36+, Ollama, mkcert, MCP SDK (fastmcp), launchd

**Spec:** `docs/superpowers/specs/2026-04-08-phase3b-local-gateway-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `scripts/zantara-gateway/gateway.py` | HTTP gateway: CORS, auth, subprocess spawn, NDJSON→SSE, Ollama fallback with ReAct loop |
| `scripts/zantara-gateway/config.py` | Config loader: reads `~/.zantara-gateway/config.json`, validates, provides defaults |
| `scripts/zantara-gateway/mcp_client.py` | MCP tool client: connects to `server_agent.py` via stdio, lists tools, executes calls (used by Ollama fallback ReAct loop) |
| `scripts/zantara-gateway/test_gateway.py` | Tests for gateway logic (subprocess mock, SSE conversion, fallback) |
| `scripts/zantara-gateway/test_mcp_client.py` | Tests for MCP client (tool listing, execution) |
| `scripts/zantara-gateway/requirements.txt` | Dependencies: aiohttp, mcp |
| `scripts/install-node.sh` | Generic team member install script (extends damar-node pattern) |
| `apps/mouth/src/lib/gateway.ts` | Gateway client: try localhost, fallback to cloud, token management |
| `apps/mouth/src/lib/__tests__/gateway.test.ts` | Tests for gateway client logic |

### Modified files

| File | Change |
|------|--------|
| `apps/mouth/src/components/workspace/WorkspaceAssistant.tsx` | Replace direct fetch with `gateway.ts` dual-path client |
| `scripts/damar-node/install.sh` | Add gateway setup steps (mkcert, gateway.py, launchd plist) |

---

## Task 1: Gateway config loader

**Files:**
- Create: `scripts/zantara-gateway/config.py`
- Create: `scripts/zantara-gateway/requirements.txt`

- [ ] **Step 1: Create requirements.txt**

```
# scripts/zantara-gateway/requirements.txt
aiohttp>=3.11,<4
mcp>=1.0,<2
```

- [ ] **Step 2: Create config.py with defaults and validation**

```python
# scripts/zantara-gateway/config.py
"""
Gateway configuration loader.

Reads ~/.zantara-gateway/config.json. Falls back to sane defaults.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("zantara-gateway.config")

CONFIG_DIR = Path.home() / ".zantara-gateway"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class GatewayConfig:
    port: int = 8090
    role: str = "visa_specialist"
    agent_name: str = "Team Member"
    gateway_token: str = ""
    # Gemini CLI
    gemini_timeout: int = 60
    gemini_allowed_mcp: list[str] = field(default_factory=lambda: ["nuzantara"])
    # Ollama fallback
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = ""  # auto-detected from RAM
    ollama_max_tool_iterations: int = 3
    ollama_tool_fail_threshold: int = 2
    # CORS
    allowed_origins: list[str] = field(
        default_factory=lambda: ["https://kita.balizero.com"]
    )
    # TLS
    tls_cert: str = str(CONFIG_DIR / "cert.pem")
    tls_key: str = str(CONFIG_DIR / "key.pem")

    def has_tls(self) -> bool:
        return os.path.isfile(self.tls_cert) and os.path.isfile(self.tls_key)


def _detect_ollama_model() -> str:
    """Pick Gemma 4 variant based on system RAM."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        ram_gb = int(result.stdout.strip()) / (1024**3)
        if ram_gb >= 14:
            return "gemma4:e4b"
        return "gemma4:e2b"
    except Exception:
        return "gemma4:e2b"


def load_config() -> GatewayConfig:
    """Load config from JSON file, merge with defaults."""
    cfg = GatewayConfig()

    if CONFIG_FILE.is_file():
        try:
            raw = json.loads(CONFIG_FILE.read_text())
            cfg.port = raw.get("port", cfg.port)
            cfg.role = raw.get("role", cfg.role)
            cfg.agent_name = raw.get("agent_name", cfg.agent_name)
            cfg.gateway_token = raw.get("gateway_token", cfg.gateway_token)

            gemini = raw.get("gemini_cli", {})
            cfg.gemini_timeout = gemini.get("timeout_seconds", cfg.gemini_timeout)
            cfg.gemini_allowed_mcp = gemini.get(
                "allowed_mcp_servers", cfg.gemini_allowed_mcp
            )

            ollama = raw.get("ollama", {})
            cfg.ollama_url = ollama.get("url", cfg.ollama_url)
            cfg.ollama_model = ollama.get("model", "")
            cfg.ollama_max_tool_iterations = ollama.get(
                "max_tool_iterations", cfg.ollama_max_tool_iterations
            )
            cfg.ollama_tool_fail_threshold = ollama.get(
                "tool_fail_threshold", cfg.ollama_tool_fail_threshold
            )

            cors = raw.get("cors", {})
            cfg.allowed_origins = cors.get("allowed_origins", cfg.allowed_origins)

            tls = raw.get("tls", {})
            cfg.tls_cert = tls.get("cert", cfg.tls_cert)
            cfg.tls_key = tls.get("key", cfg.tls_key)

            logger.info("Config loaded from %s", CONFIG_FILE)
        except Exception as e:
            logger.warning("Failed to parse config: %s — using defaults", e)

    # Auto-detect Ollama model if not set
    if not cfg.ollama_model:
        cfg.ollama_model = _detect_ollama_model()

    if not cfg.gateway_token:
        logger.warning("No gateway_token set — auth disabled")

    return cfg
```

- [ ] **Step 3: Commit**

```bash
git add scripts/zantara-gateway/config.py scripts/zantara-gateway/requirements.txt
git commit -m "feat(gateway): add config loader with defaults and RAM-based model detection"
```

---

## Task 2: MCP tool client for Ollama fallback

**Files:**
- Create: `scripts/zantara-gateway/mcp_client.py`
- Create: `scripts/zantara-gateway/test_mcp_client.py`

- [ ] **Step 1: Write test for MCP tool listing**

```python
# scripts/zantara-gateway/test_mcp_client.py
"""Tests for MCP tool client."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_client import MCPToolClient


@pytest.fixture
def mock_mcp_session():
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=[
        MagicMock(name="list_clients", description="List CRM clients",
                  inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        MagicMock(name="get_client", description="Get client details",
                  inputSchema={"type": "object", "properties": {"client_id": {"type": "string"}}, "required": ["client_id"]}),
    ])
    session.call_tool.return_value = MagicMock(
        content=[MagicMock(text='[{"id": "c1", "name": "Test Client"}]')]
    )
    return session


def test_tool_definitions_to_ollama_format(mock_mcp_session):
    """Tool definitions should convert to Ollama/OpenAI function calling format."""
    client = MCPToolClient.__new__(MCPToolClient)
    client._session = mock_mcp_session
    client._tools_cache = None

    tools = asyncio.get_event_loop().run_until_complete(client.get_tool_definitions())

    assert len(tools) == 2
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "list_clients"
    assert "parameters" in tools[0]["function"]


def test_execute_tool_call(mock_mcp_session):
    """Execute a tool call via MCP session."""
    client = MCPToolClient.__new__(MCPToolClient)
    client._session = mock_mcp_session
    client._tools_cache = None

    result = asyncio.get_event_loop().run_until_complete(
        client.execute_tool("list_clients", {"limit": 10})
    )

    mock_mcp_session.call_tool.assert_called_once_with("list_clients", arguments={"limit": 10})
    assert "Test Client" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/zantara-gateway
python3 -m pytest test_mcp_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_client'`

- [ ] **Step 3: Implement MCP tool client**

```python
# scripts/zantara-gateway/mcp_client.py
"""
MCP Tool Client — connects to server_agent.py via stdio.

Used by the Ollama fallback ReAct loop to execute MCP tools.
Gemini CLI path does NOT use this — it connects to MCP directly.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("zantara-gateway.mcp")

# Default path to server_agent.py
_DEFAULT_SERVER = (
    Path.home() / "Desktop" / "nuzantara" / "apps" / "nuzantara-mcp"
    / "nuzantara_mcp" / "server_agent.py"
)
_DEFAULT_VENV_PYTHON = (
    Path.home() / "Desktop" / "nuzantara" / "apps" / "nuzantara-mcp"
    / ".venv" / "bin" / "python"
)


class MCPToolClient:
    """Connects to server_agent.py MCP server and exposes tool execution."""

    def __init__(
        self,
        role: str = "visa_specialist",
        agent_name: str = "Team Member",
        api_key: str = "",
        server_path: str = "",
        python_path: str = "",
    ):
        self._role = role
        self._agent_name = agent_name
        self._api_key = api_key or os.getenv("NUZANTARA_API_KEY", "")
        self._server_path = server_path or str(_DEFAULT_SERVER)
        self._python_path = python_path or str(_DEFAULT_VENV_PYTHON)
        self._session: ClientSession | None = None
        self._tools_cache: list[dict] | None = None
        self._cm = None  # context manager for stdio_client

    async def connect(self) -> None:
        """Start MCP server subprocess and establish session."""
        env = {
            **os.environ,
            "AGENT_ROLE": self._role,
            "AGENT_NAME": self._agent_name,
            "NUZANTARA_API_KEY": self._api_key,
            "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
            "PYTHONPATH": str(Path(self._server_path).parent.parent),
        }

        server_params = StdioServerParameters(
            command=self._python_path,
            args=[self._server_path],
            env=env,
        )

        self._cm = stdio_client(server_params)
        read, write = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.initialize()
        logger.info("MCP session established for role=%s", self._role)

    async def close(self) -> None:
        """Shut down MCP session and subprocess."""
        if self._session:
            # session doesn't need explicit close
            self._session = None
        if self._cm:
            await self._cm.__aexit__(None, None, None)
            self._cm = None

    async def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions in OpenAI/Ollama function calling format."""
        if self._tools_cache is not None:
            return self._tools_cache

        if not self._session:
            raise RuntimeError("MCP session not connected. Call connect() first.")

        result = await self._session.list_tools()
        tools = []
        for tool in result.tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                },
            })

        self._tools_cache = tools
        logger.info("Loaded %d MCP tool definitions", len(tools))
        return tools

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool call and return the text result."""
        if not self._session:
            raise RuntimeError("MCP session not connected. Call connect() first.")

        result = await self._session.call_tool(name, arguments=arguments)

        # Extract text from result content blocks
        texts = []
        for block in result.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else str(result.content)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/zantara-gateway
python3 -m pytest test_mcp_client.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/zantara-gateway/mcp_client.py scripts/zantara-gateway/test_mcp_client.py
git commit -m "feat(gateway): add MCP tool client for Ollama fallback ReAct loop"
```

---

## Task 3: Core gateway — Gemini CLI path + NDJSON→SSE

**Files:**
- Create: `scripts/zantara-gateway/gateway.py`
- Create: `scripts/zantara-gateway/test_gateway.py`

- [ ] **Step 1: Write test for NDJSON to SSE conversion**

```python
# scripts/zantara-gateway/test_gateway.py
"""Tests for gateway core."""

import pytest
from gateway import ndjson_line_to_sse, verify_gateway_token

# ── NDJSON → SSE conversion ──

def test_text_delta_converts_to_token():
    line = '{"type":"textDelta","text":"Hello "}'
    result = ndjson_line_to_sse(line)
    assert result == 'data: {"type":"token","data":"Hello "}\n\n'


def test_done_converts_to_done():
    line = '{"type":"done"}'
    result = ndjson_line_to_sse(line)
    assert result == "data: [DONE]\n\n"


def test_tool_call_start_converts():
    line = '{"type":"toolCallStart","toolName":"list_clients","args":{"limit":5}}'
    result = ndjson_line_to_sse(line)
    assert '"type":"tool_call"' in result
    assert '"name":"list_clients"' in result


def test_unknown_type_returns_none():
    line = '{"type":"unknownEvent","data":"whatever"}'
    result = ndjson_line_to_sse(line)
    assert result is None


def test_invalid_json_returns_none():
    result = ndjson_line_to_sse("not json at all")
    assert result is None


# ── Auth ──

def test_valid_token():
    assert verify_gateway_token("abc123", "abc123") is True


def test_invalid_token():
    assert verify_gateway_token("abc123", "wrong") is False


def test_empty_configured_token_disables_auth():
    """If no token is configured, auth is disabled (dev mode)."""
    assert verify_gateway_token("", "anything") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/zantara-gateway
python3 -m pytest test_gateway.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement gateway.py**

```python
#!/usr/bin/env python3
# scripts/zantara-gateway/gateway.py
"""
Zantara Local Gateway — bridges browser widget to Gemini CLI.

Accepts HTTPS requests from kita.balizero.com, spawns Gemini CLI
in headless mode, converts NDJSON stream to SSE for the widget.
Fallback: Ollama Gemma 4 with MCP tool ReAct loop.

Usage:
    python gateway.py                # reads ~/.zantara-gateway/config.json
    python gateway.py --port 9090    # override port
"""

import asyncio
import json
import logging
import os
import signal
import ssl
import sys
from typing import AsyncIterator

from aiohttp import web

# Local imports
from config import GatewayConfig, load_config
from mcp_client import MCPToolClient

logger = logging.getLogger("zantara-gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# ── Globals ──

_config: GatewayConfig | None = None
_mcp_client: MCPToolClient | None = None


# ── NDJSON → SSE Conversion ──


def ndjson_line_to_sse(line: str) -> str | None:
    """Convert a single NDJSON line from Gemini CLI to an SSE event.

    Returns formatted SSE string, or None to skip the line.
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    event_type = obj.get("type", "")

    if event_type == "textDelta":
        text = obj.get("text", "")
        return f'data: {json.dumps({"type": "token", "data": text})}\n\n'

    if event_type == "done":
        return "data: [DONE]\n\n"

    if event_type == "toolCallStart":
        name = obj.get("toolName", "")
        args = obj.get("args", {})
        return f'data: {json.dumps({"type": "tool_call", "data": {"name": name, "args": args}})}\n\n'

    if event_type == "toolCallEnd":
        name = obj.get("toolName", "")
        return f'data: {json.dumps({"type": "tool_result", "data": {"name": name}})}\n\n'

    # Unknown event type — skip
    return None


def verify_gateway_token(configured: str, provided: str) -> bool:
    """Check if the provided token matches. Empty configured = auth disabled."""
    if not configured:
        return True
    return configured == provided


# ── Gemini CLI Subprocess ──


async def stream_gemini_cli(query: str, config: GatewayConfig) -> AsyncIterator[str]:
    """Spawn Gemini CLI headless and yield SSE lines from NDJSON output."""
    mcp_names = ",".join(config.gemini_allowed_mcp)
    cmd = [
        "gemini",
        "-p", query,
        "-o", "stream-json",
        "-y",
        "--allowed-mcp-server-names", mcp_names,
    ]

    logger.info("Spawning: %s", " ".join(cmd[:6]) + "...")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            sse = ndjson_line_to_sse(line)
            if sse:
                yield sse
    except asyncio.CancelledError:
        proc.kill()
        raise
    finally:
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()

    rc = proc.returncode
    if rc != 0:
        stderr_out = ""
        if proc.stderr:
            stderr_out = (await proc.stderr.read()).decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini CLI exited with code {rc}: {stderr_out[:500]}")

    yield "data: [DONE]\n\n"


# ── Ollama Fallback with ReAct Loop ──


async def stream_ollama_react(
    query: str,
    config: GatewayConfig,
    mcp: MCPToolClient,
) -> AsyncIterator[str]:
    """Call Ollama with MCP tools in a ReAct loop. Yield SSE lines."""
    import httpx

    tool_defs = await mcp.get_tool_definitions()
    messages = [{"role": "user", "content": query}]
    consecutive_failures = 0

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        for iteration in range(config.ollama_max_tool_iterations + 1):
            payload: dict = {
                "model": config.ollama_model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.3},
            }

            # Only include tools if we haven't hit the failure threshold
            if consecutive_failures < config.ollama_tool_fail_threshold and tool_defs:
                payload["tools"] = tool_defs

            accumulated_text = ""
            tool_calls: list[dict] = []

            async with client.stream(
                "POST",
                f"{config.ollama_url}/api/chat",
                json=payload,
            ) as resp:
                async for raw_line in resp.aiter_lines():
                    if not raw_line.strip():
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})

                    # Stream text tokens
                    content = msg.get("content", "")
                    if content:
                        accumulated_text += content
                        yield f'data: {json.dumps({"type": "token", "data": content})}\n\n'

                    # Collect tool calls
                    if msg.get("tool_calls"):
                        tool_calls.extend(msg["tool_calls"])

                    if chunk.get("done"):
                        break

            # No tool calls — we're done
            if not tool_calls:
                break

            # Execute tool calls via MCP
            messages.append({"role": "assistant", "content": accumulated_text, "tool_calls": tool_calls})

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})

                yield f'data: {json.dumps({"type": "tool_call", "data": {"name": name}})}\n\n'

                try:
                    result = await mcp.execute_tool(name, args)
                    messages.append({"role": "tool", "content": result})
                    consecutive_failures = 0
                    yield f'data: {json.dumps({"type": "tool_result", "data": {"name": name}})}\n\n'
                except Exception as e:
                    consecutive_failures += 1
                    logger.warning("Tool %s failed (%d/%d): %s", name, consecutive_failures, config.ollama_tool_fail_threshold, e)
                    messages.append({"role": "tool", "content": f"Error: {e}"})

            tool_calls = []

    yield "data: [DONE]\n\n"


# ── HTTP Handlers ──


async def handle_chat(request: web.Request) -> web.StreamResponse:
    """POST /v1/chat — main chat endpoint with SSE streaming."""
    config = request.app["config"]

    # Auth check
    token = request.headers.get("X-Gateway-Token", "")
    if not verify_gateway_token(config.gateway_token, token):
        return web.json_response({"error": "Unauthorized"}, status=401)

    # Parse body
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    query = body.get("query", "").strip()
    if not query:
        return web.json_response({"error": "query is required"}, status=400)

    # Add conversation history context if provided
    history = body.get("conversation_history", [])
    if history:
        context_parts = []
        for msg in history[-6:]:  # Last 6 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_parts.append(f"[{role}]: {content}")
        query = "\n".join(context_parts) + f"\n[user]: {query}"

    # SSE response
    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)

    # Try Gemini CLI first, fallback to Ollama
    try:
        async for sse_line in stream_gemini_cli(query, config):
            await resp.write(sse_line.encode("utf-8"))
    except Exception as e:
        logger.warning("Gemini CLI failed, falling back to Ollama: %s", e)
        try:
            mcp = request.app.get("mcp_client")
            if mcp:
                async for sse_line in stream_ollama_react(query, config, mcp):
                    await resp.write(sse_line.encode("utf-8"))
            else:
                await resp.write(
                    f'data: {json.dumps({"type": "token", "data": "Maaf, asisten tidak tersedia saat ini."})}\n\n'.encode()
                )
                await resp.write(b"data: [DONE]\n\n")
        except Exception as e2:
            logger.error("Ollama fallback also failed: %s", e2)
            await resp.write(
                f'data: {json.dumps({"type": "token", "data": "Asisten tidak tersedia. Silakan coba lagi nanti."})}\n\n'.encode()
            )
            await resp.write(b"data: [DONE]\n\n")

    await resp.write_eof()
    return resp


async def handle_health(request: web.Request) -> web.Response:
    """GET /health — gateway status."""
    import shutil

    config = request.app["config"]

    gemini_ok = shutil.which("gemini") is not None
    ollama_ok = False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{config.ollama_url}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return web.json_response({
        "status": "ok" if gemini_ok else "degraded",
        "gemini_cli": gemini_ok,
        "ollama": ollama_ok,
        "ollama_model": config.ollama_model,
        "role": config.role,
        "agent_name": config.agent_name,
        "version": "1.0.0",
    })


async def handle_config_endpoint(request: web.Request) -> web.Response:
    """GET /v1/config — public config for widget."""
    config = request.app["config"]
    mcp = request.app.get("mcp_client")
    tools_count = len(mcp._tools_cache) if mcp and mcp._tools_cache else 0

    return web.json_response({
        "role": config.role,
        "agent_name": config.agent_name,
        "tools_count": tools_count,
        "primary_llm": "gemini-cli",
        "fallback_llm": config.ollama_model,
    })


# ── CORS Middleware ──


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Add CORS headers for kita.balizero.com."""
    config = request.app["config"]

    # Preflight
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        resp = await handler(request)

    origin = request.headers.get("Origin", "")
    if origin in config.allowed_origins or not config.allowed_origins:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Gateway-Token"
        resp.headers["Access-Control-Max-Age"] = "86400"

    return resp


# ── App Lifecycle ──


async def on_startup(app: web.Application) -> None:
    """Initialize MCP client on startup."""
    config = app["config"]
    try:
        mcp = MCPToolClient(
            role=config.role,
            agent_name=config.agent_name,
        )
        await mcp.connect()
        app["mcp_client"] = mcp
        logger.info("MCP client connected (role=%s)", config.role)
    except Exception as e:
        logger.warning("MCP client failed to connect: %s — Ollama fallback disabled", e)
        app["mcp_client"] = None


async def on_shutdown(app: web.Application) -> None:
    """Clean up MCP client."""
    mcp = app.get("mcp_client")
    if mcp:
        await mcp.close()


def create_app(config: GatewayConfig | None = None) -> web.Application:
    """Create the aiohttp application."""
    if config is None:
        config = load_config()

    app = web.Application(middlewares=[cors_middleware])
    app["config"] = config

    app.router.add_post("/v1/chat", handle_chat)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/v1/config", handle_config_endpoint)

    # Catch-all OPTIONS for CORS preflight
    app.router.add_route("OPTIONS", "/{path:.*}", cors_middleware)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


def main() -> None:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Zantara Local Gateway")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    config = load_config()
    if args.port:
        config.port = args.port

    app = create_app(config)

    ssl_ctx = None
    if config.has_tls():
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(config.tls_cert, config.tls_key)
        logger.info("TLS enabled: %s", config.tls_cert)
    else:
        logger.warning("TLS disabled — mixed content may be blocked by browser")

    logger.info(
        "Starting Zantara Gateway on port %d (role=%s, agent=%s)",
        config.port, config.role, config.agent_name,
    )
    web.run_app(app, host="127.0.0.1", port=config.port, ssl_context=ssl_ctx)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/zantara-gateway
python3 -m pytest test_gateway.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/zantara-gateway/gateway.py scripts/zantara-gateway/test_gateway.py
git commit -m "feat(gateway): core gateway with Gemini CLI streaming and Ollama ReAct fallback"
```

---

## Task 4: Manual smoke test — verify Gemini CLI NDJSON format

**Files:** None (verification only)

This task exists because the NDJSON format of `gemini -o stream-json` was not empirically verified during design. The gateway parser may need adjustment.

- [ ] **Step 1: Authenticate Gemini CLI if needed**

```bash
gemini auth login
# Select your @balizero.com account
```

- [ ] **Step 2: Run Gemini CLI headless and capture raw output**

```bash
gemini -p "say hello in Indonesian" -o stream-json 2>/dev/null | head -20
```

Observe the actual JSON field names. Note the exact `type` values for text, tool calls, and completion.

- [ ] **Step 3: Run with MCP tool call**

```bash
gemini -p "list my clients" -o stream-json -y --allowed-mcp-server-names nuzantara 2>/dev/null | head -40
```

Observe the NDJSON for tool call events. Note the field names.

- [ ] **Step 4: Update `ndjson_line_to_sse()` if needed**

If the actual field names differ from the spec (e.g., `partialText` instead of `textDelta`), update the conversion function in `gateway.py` and update the test in `test_gateway.py` to match.

- [ ] **Step 5: Re-run tests and commit if changes were made**

```bash
cd scripts/zantara-gateway
python3 -m pytest test_gateway.py -v
git add -A && git commit -m "fix(gateway): align NDJSON parser with actual Gemini CLI output format"
```

---

## Task 5: Frontend gateway client (dual-path)

**Files:**
- Create: `apps/mouth/src/lib/gateway.ts`
- Create: `apps/mouth/src/lib/__tests__/gateway.test.ts`

- [ ] **Step 1: Write test for gateway client**

```typescript
// apps/mouth/src/lib/__tests__/gateway.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getGatewayUrl, getGatewayToken, setGatewayToken, isGatewayConfigured } from "../gateway";

describe("gateway client", () => {
  beforeEach(() => {
    // Mock localStorage
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
      removeItem: (key: string) => store.delete(key),
    });
  });

  it("returns default gateway URL", () => {
    expect(getGatewayUrl()).toBe("https://127.0.0.1:8090");
  });

  it("stores and retrieves gateway token", () => {
    expect(isGatewayConfigured()).toBe(false);
    setGatewayToken("abc123");
    expect(getGatewayToken()).toBe("abc123");
    expect(isGatewayConfigured()).toBe(true);
  });

  it("returns empty string when no token set", () => {
    expect(getGatewayToken()).toBe("");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/mouth && npx vitest run src/lib/__tests__/gateway.test.ts
```

Expected: `Cannot find module '../gateway'`

- [ ] **Step 3: Implement gateway.ts**

```typescript
// apps/mouth/src/lib/gateway.ts
/**
 * Local Gateway Client — dual-path: localhost gateway first, cloud fallback.
 *
 * The gateway runs on the team member's Mac and proxies to Gemini CLI.
 * If the gateway is unreachable, falls back to the Fly.io backend RAG.
 */

const GATEWAY_URL_KEY = "zantara_gateway_url";
const GATEWAY_TOKEN_KEY = "zantara_gateway_token";
const DEFAULT_GATEWAY_URL = "https://127.0.0.1:8090";

const CLOUD_BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev";

export function getGatewayUrl(): string {
  if (typeof window === "undefined") return DEFAULT_GATEWAY_URL;
  return localStorage.getItem(GATEWAY_URL_KEY) || DEFAULT_GATEWAY_URL;
}

export function getGatewayToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(GATEWAY_TOKEN_KEY) || "";
}

export function setGatewayToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(GATEWAY_TOKEN_KEY, token);
}

export function setGatewayUrl(url: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(GATEWAY_URL_KEY, url);
}

export function isGatewayConfigured(): boolean {
  return getGatewayToken() !== "";
}

export function clearGatewayConfig(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(GATEWAY_TOKEN_KEY);
  localStorage.removeItem(GATEWAY_URL_KEY);
}

interface ChatRequest {
  query: string;
  session_id: string;
  conversation_history: { role: string; content: string }[];
  workspace_page?: string;
}

/**
 * Send a chat request — tries local gateway first, falls back to cloud.
 * Returns a Response with an SSE body stream.
 */
export async function sendChat(req: ChatRequest): Promise<Response> {
  const gatewayUrl = getGatewayUrl();
  const token = getGatewayToken();

  // Try local gateway if configured
  if (token) {
    try {
      const res = await fetch(`${gatewayUrl}/v1/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Gateway-Token": token,
        },
        body: JSON.stringify({
          query: req.query,
          session_id: req.session_id,
          conversation_history: req.conversation_history,
        }),
      });
      if (res.ok) return res;
      // Non-OK but reachable — log and fall through
      console.warn(`[gateway] Local returned ${res.status}, falling back to cloud`);
    } catch {
      // Unreachable — fall through to cloud
      console.warn("[gateway] Local gateway unreachable, using cloud backend");
    }
  }

  // Cloud fallback (existing behavior)
  return fetch(`${CLOUD_BACKEND}/api/agentic-rag/workspace-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      query: req.query,
      session_id: req.session_id,
      enable_vision: false,
      conversation_history: req.conversation_history,
      workspace_page: req.workspace_page,
    }),
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/mouth && npx vitest run src/lib/__tests__/gateway.test.ts
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/lib/gateway.ts apps/mouth/src/lib/__tests__/gateway.test.ts
git commit -m "feat(mouth): add dual-path gateway client (local first, cloud fallback)"
```

---

## Task 6: Wire WorkspaceAssistant.tsx to gateway client

**Files:**
- Modify: `apps/mouth/src/components/workspace/WorkspaceAssistant.tsx:94-115`

- [ ] **Step 1: Add gateway import and replace fetch call**

In `WorkspaceAssistant.tsx`, replace the direct fetch with the gateway client.

Replace lines 94-115 (the `try` block starting with `const history`):

```typescript
// OLD (remove):
// const res = await fetch(`${BACKEND}/api/agentic-rag/workspace-stream`, {
//   ...
// });

// NEW:
import { sendChat } from "@/lib/gateway";

// ... inside handleSend, replace the fetch call:
      const history = messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await sendChat({
        query: text,
        session_id: `ws_${userEmail.replace("@", "_")}`,
        conversation_history: history,
        workspace_page: pathname,
      });
```

Full change: add `import { sendChat } from "@/lib/gateway";` at the top imports, then replace the fetch call at line 104 with `sendChat(...)`. Remove the unused `BACKEND` const if no other code uses it. The SSE parsing logic (lines 119-152) stays exactly the same — both gateway and cloud return identical SSE format.

- [ ] **Step 2: Verify the import is added and the old fetch is removed**

Check that:
1. `import { sendChat } from "@/lib/gateway";` is in the imports
2. `const BACKEND = ...` line is removed (line 32-33)
3. `fetch(${BACKEND}/api/agentic-rag/workspace-stream, ...)` is replaced with `sendChat({...})`
4. `credentials: "include"` is NOT in the new call (it's inside `sendChat` for cloud path only)
5. SSE parsing code is unchanged

- [ ] **Step 3: Build check**

```bash
cd apps/mouth && npx next build 2>&1 | tail -20
```

Expected: Build succeeds with no type errors.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/components/workspace/WorkspaceAssistant.tsx
git commit -m "feat(mouth): wire WorkspaceAssistant to dual-path gateway client"
```

---

## Task 7: Install script for team member nodes

**Files:**
- Create: `scripts/install-node.sh`
- Modify: `scripts/damar-node/install.sh` (add gateway section)

- [ ] **Step 1: Create generic install-node.sh**

```bash
#!/usr/bin/env bash
# install-node.sh — Nuzantara Team Node Setup (generic)
# Usage: ROLE=visa_specialist NAME=Damar TOKEN=xxx bash install-node.sh

set -euo pipefail

ROLE="${ROLE:?ERROR: Set ROLE env var (e.g. visa_specialist)}"
NAME="${NAME:?ERROR: Set NAME env var (e.g. Damar)}"
TOKEN="${TOKEN:?ERROR: Set TOKEN env var (provided by admin)}"

PROJECT_DIR="$HOME/Desktop/nuzantara"
GATEWAY_DIR="$HOME/.zantara-gateway"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[nuz-node]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Nuzantara Federation — Node Setup: $NAME"
echo "║  Role: $ROLE"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── 1. Homebrew ──────────────────────────────────────
log "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
ok "Homebrew ready"

# ─── 2. Node.js + Gemini CLI ─────────────────────────
log "Installing Node.js + Gemini CLI..."
brew install node 2>/dev/null || true
npm install -g @google/gemini-cli 2>/dev/null || warn "Try manual: npm i -g @google/gemini-cli"
ok "Gemini CLI: $(gemini --version 2>/dev/null | head -1 || echo 'check manually')"

# ─── 3. Python ────────────────────────────────────────
log "Setting up Python..."
brew install python@3.11 2>/dev/null || true
ok "Python: $(python3 --version)"

# ─── 4. Ollama + Gemma 4 ─────────────────────────────
log "Installing Ollama + Gemma 4..."
brew install ollama 2>/dev/null || true
RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}')
if [ "$RAM_GB" -ge 14 ]; then
    GEMMA_MODEL="gemma4:e4b"
else
    GEMMA_MODEL="gemma4:e2b"
fi
ollama pull "$GEMMA_MODEL" 2>/dev/null || warn "Run manually: ollama pull $GEMMA_MODEL"
ok "Ollama model: $GEMMA_MODEL (RAM: ${RAM_GB}GB)"

# ─── 5. mkcert ────────────────────────────────────────
log "Setting up TLS (mkcert)..."
brew install mkcert 2>/dev/null || true
mkcert -install 2>/dev/null || true
mkdir -p "$GATEWAY_DIR"
if [ ! -f "$GATEWAY_DIR/cert.pem" ]; then
    mkcert -cert-file "$GATEWAY_DIR/cert.pem" \
           -key-file "$GATEWAY_DIR/key.pem" \
           localhost 127.0.0.1
fi
ok "TLS certificates ready"

# ─── 6. Clone/update repo ────────────────────────────
log "Setting up repo..."
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR" && git pull --ff-only || warn "Git pull failed — manual sync needed"
else
    git clone https://github.com/Balizero1987/Teman2.git "$PROJECT_DIR"
fi
ok "Repo: $PROJECT_DIR"

# ─── 7. MCP server venv ──────────────────────────────
log "Setting up MCP server..."
cd "$PROJECT_DIR/apps/nuzantara-mcp"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q fastmcp httpx pydantic 2>/dev/null || true
ok "MCP server venv ready"

# ─── 8. Gateway ──────────────────────────────────────
log "Installing gateway..."
cp "$PROJECT_DIR/scripts/zantara-gateway/gateway.py" "$GATEWAY_DIR/"
cp "$PROJECT_DIR/scripts/zantara-gateway/config.py" "$GATEWAY_DIR/"
cp "$PROJECT_DIR/scripts/zantara-gateway/mcp_client.py" "$GATEWAY_DIR/"

# Install gateway dependencies
python3 -m pip install -q aiohttp mcp httpx 2>/dev/null || true

GATEWAY_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
cat > "$GATEWAY_DIR/config.json" << GWCONFIG
{
  "port": 8090,
  "role": "$ROLE",
  "agent_name": "$NAME",
  "gateway_token": "$GATEWAY_TOKEN",
  "gemini_cli": {
    "allowed_mcp_servers": ["nuzantara"],
    "timeout_seconds": 60
  },
  "ollama": {
    "model": "$GEMMA_MODEL",
    "url": "http://localhost:11434",
    "max_tool_iterations": 3,
    "tool_fail_threshold": 2
  },
  "cors": {
    "allowed_origins": ["https://kita.balizero.com"]
  },
  "tls": {
    "cert": "$GATEWAY_DIR/cert.pem",
    "key": "$GATEWAY_DIR/key.pem"
  }
}
GWCONFIG
ok "Gateway configured"

# ─── 9. Gemini CLI config ────────────────────────────
log "Configuring Gemini CLI..."
mkdir -p "$HOME/.gemini"
cat > "$HOME/.gemini/settings.json" << GSETTINGS
{
  "security": {
    "auth": {"selectedType": "oauth-personal"},
    "enablePermanentToolApproval": true,
    "folderTrust": {"enabled": true}
  },
  "general": {
    "previewFeatures": true,
    "enableAutoUpdate": true
  },
  "mcpServers": {
    "nuzantara": {
      "command": "$PROJECT_DIR/apps/nuzantara-mcp/.venv/bin/python",
      "args": ["$PROJECT_DIR/apps/nuzantara-mcp/nuzantara_mcp/server_agent.py"],
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_API_KEY": "$TOKEN",
        "AGENT_ROLE": "$ROLE",
        "AGENT_NAME": "$NAME",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
GSETTINGS
ok "Gemini CLI configured"

# ─── 10. launchd auto-start ──────────────────────────
log "Setting up auto-start..."
PLIST="$HOME/Library/LaunchAgents/com.balizero.zantara-gateway.plist"
cat > "$PLIST" << PLIST_CONTENT
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.balizero.zantara-gateway</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(which python3)</string>
    <string>$GATEWAY_DIR/gateway.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$GATEWAY_DIR/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$GATEWAY_DIR/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>NUZANTARA_API_KEY</key>
    <string>$TOKEN</string>
  </dict>
</dict>
</plist>
PLIST_CONTENT

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
ok "Gateway auto-start enabled"

# ─── 11. Git auto-sync (hourly) ──────────────────────
CRON_CMD="cd $PROJECT_DIR && git pull --ff-only --quiet 2>/dev/null"
(crontab -l 2>/dev/null | grep -v "nuzantara.*pull"; echo "0 * * * * $CRON_CMD") | crontab -
ok "Hourly git sync enabled"

# ─── Done ─────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Setup complete!                              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Login to Gemini CLI:"
echo "   gemini auth login"
echo "   → Select ${NAME}@balizero.com"
echo ""
echo "2. Test gateway:"
echo "   curl -k https://127.0.0.1:8090/health"
echo ""
echo "3. Open kita.balizero.com and configure:"
echo "   Gateway token: $GATEWAY_TOKEN"
echo ""
echo "4. Test in widget:"
echo "   Ask: 'Tampilkan daftar pratik aktif'"
echo ""
warn "IMPORTANT: Login with ${NAME}@balizero.com when prompted!"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/install-node.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/install-node.sh
git commit -m "feat: add generic team node install script with gateway setup"
```

---

## Task 8: End-to-end smoke test on Pro

**Files:** None (manual testing)

- [ ] **Step 1: Install gateway dependencies on Pro**

```bash
cd /Users/nuzantara/Desktop/nuzantara/scripts/zantara-gateway
pip install aiohttp mcp httpx
```

- [ ] **Step 2: Create test config**

```bash
mkdir -p ~/.zantara-gateway
# Generate self-signed cert (mkcert)
brew install mkcert && mkcert -install
mkcert -cert-file ~/.zantara-gateway/cert.pem -key-file ~/.zantara-gateway/key.pem localhost 127.0.0.1

cat > ~/.zantara-gateway/config.json << 'EOF'
{
  "port": 8090,
  "role": "admin",
  "agent_name": "Zero",
  "gateway_token": "test-token-123",
  "gemini_cli": {"allowed_mcp_servers": ["nuzantara-mcp"], "timeout_seconds": 60},
  "ollama": {"model": "gemma4:26b", "url": "http://localhost:11434"},
  "cors": {"allowed_origins": ["https://kita.balizero.com"]},
  "tls": {"cert": "~/.zantara-gateway/cert.pem", "key": "~/.zantara-gateway/key.pem"}
}
EOF
```

- [ ] **Step 3: Start gateway**

```bash
cd scripts/zantara-gateway
python gateway.py
```

Expected: `Starting Zantara Gateway on port 8090 (role=admin, agent=Zero)`

- [ ] **Step 4: Test health endpoint**

```bash
curl -sk https://127.0.0.1:8090/health | python3 -m json.tool
```

Expected: `{"status": "ok", "gemini_cli": true, "ollama": true, ...}`

- [ ] **Step 5: Test chat endpoint with SSE**

```bash
curl -sk -N -X POST https://127.0.0.1:8090/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Token: test-token-123" \
  -d '{"query": "say hello in Indonesian", "session_id": "test", "conversation_history": []}'
```

Expected: SSE stream with `data: {"type":"token","data":"..."}` lines ending with `data: [DONE]`

- [ ] **Step 6: Test with MCP tool call**

```bash
curl -sk -N -X POST https://127.0.0.1:8090/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Token: test-token-123" \
  -d '{"query": "tampilkan daftar klien", "session_id": "test", "conversation_history": []}'
```

Expected: SSE stream includes `tool_call` events for `list_clients`, then a text response with client data.

- [ ] **Step 7: Test CORS**

```bash
curl -sk -X OPTIONS https://127.0.0.1:8090/v1/chat \
  -H "Origin: https://kita.balizero.com" \
  -H "Access-Control-Request-Method: POST" \
  -v 2>&1 | grep -i "access-control"
```

Expected: `Access-Control-Allow-Origin: https://kita.balizero.com`

- [ ] **Step 8: Deploy frontend and test in browser**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git push origin main  # triggers Vercel deploy
```

Then: Open `kita.balizero.com`, log in as admin, open workspace widget (Cmd+J), configure gateway token in the widget, and test a query.

- [ ] **Step 9: Commit any fixes from testing**

```bash
git add -A && git commit -m "fix(gateway): adjustments from smoke testing"
```
