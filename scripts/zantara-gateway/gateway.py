# scripts/zantara-gateway/gateway.py
"""
Zantara Local Gateway — HTTP server for team member nodes.

Accepts chat requests from the browser widget, spawns Gemini CLI
for headless ReAct, falls back to Ollama Gemma 4 with gateway-managed
ReAct loop if Gemini CLI is unavailable.
"""

import asyncio
import json
import logging
import os
import shutil
import ssl
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Any

import httpx
from aiohttp import web

from acp_client import ACPGeminiClient
from claude_client import stream_claude_cli
from config import GatewayConfig, load_config
from gemini_api_client import stream_gemini_api
from http_tool_executor import HTTPToolExecutor
from mcp_client import MCPToolClient

logger = logging.getLogger("zantara-gateway")

# ── Pure functions (tested) ──────────────────────────────────────────────


def ndjson_line_to_sse(line: str) -> str | None:
    """Convert a single NDJSON line from Gemini CLI to an SSE event.

    Maps actual Gemini CLI stream-json format:
      type:"message", role:"assistant", delta:true → {"type":"token","data":"<content>"}
      type:"result"                                → [DONE]
      type:"tool_use"                              → {"type":"tool_call","data":{"name":"...","args":{...}}}
      type:"tool_result"                           → {"type":"tool_result","data":{"name":"...","result":"..."}}
      type:"init"                                  → None (skip)
      type:"message", role:"user"                  → None (skip, echo of input)

    Returns None for unknown types or invalid JSON.
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    event_type = obj.get("type", "")

    if event_type == "message":
        role = obj.get("role", "")
        if role == "assistant" and obj.get("delta"):
            content = obj.get("content", "")
            return f'data: {json.dumps({"type": "token", "data": content}, separators=(",", ":"))}\n\n'
        return None  # skip user messages and non-delta

    if event_type == "result":
        return "data: [DONE]\n\n"

    if event_type == "tool_use":
        raw_name = obj.get("tool_name", "")
        # Strip MCP server prefix: "mcp_nuzantara-mcp_check_health" → "check_health"
        name = raw_name
        for prefix in ("mcp_nuzantara-mcp_", "mcp_nuzantara_"):
            if raw_name.startswith(prefix):
                name = raw_name[len(prefix):]
                break
        args = obj.get("parameters", {})
        return f'data: {json.dumps({"type": "tool_call", "data": {"name": name, "args": args}}, separators=(",", ":"))}\n\n'

    if event_type == "tool_result":
        tool_id = obj.get("tool_id", "")
        output = obj.get("output", "")
        return f'data: {json.dumps({"type": "tool_result", "data": {"name": tool_id, "result": output}}, separators=(",", ":"))}\n\n'

    # init, unknown types → skip
    return None


def verify_gateway_token(configured: str, provided: str) -> bool:
    """Simple token comparison. Empty configured = auth disabled (dev mode)."""
    if not configured:
        return True
    return configured == provided


# ── Gemini CLI streaming ─────────────────────────────────────────────────


async def stream_gemini_cli(
    query: str, config: GatewayConfig
) -> AsyncIterator[str]:
    """Spawn Gemini CLI headless and yield SSE lines from its NDJSON output.

    Runs: gemini -p "{query}" -o stream-json -y
           --allowed-mcp-server-names {mcp_names}

    Raises RuntimeError if the process exits with non-zero code.
    """
    mcp_names = ",".join(config.gemini_allowed_mcp)
    cmd = [
        "gemini",
        "-p", query,
        "-o", "stream-json",
        "-y",
        "--allowed-mcp-server-names", mcp_names,
    ]

    logger.info("Spawning Gemini CLI: %s", " ".join(cmd[:4]) + " ...")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        async def _read_lines() -> AsyncIterator[str]:
            assert proc.stdout is not None
            while True:
                raw = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=config.gemini_timeout,
                )
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                sse = ndjson_line_to_sse(line)
                if sse:
                    yield sse

        async for sse_line in _read_lines():
            yield sse_line

    except asyncio.TimeoutError:
        logger.warning("Gemini CLI timeout after %ds", config.gemini_timeout)
        raise
    except asyncio.CancelledError:
        logger.info("Gemini CLI streaming cancelled")
        raise
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()

    if proc.returncode and proc.returncode != 0:
        stderr_out = ""
        if proc.stderr:
            stderr_out = (await proc.stderr.read()).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini CLI exited with code {proc.returncode}: {stderr_out[:500]}"
        )


# ── Ollama ReAct fallback ────────────────────────────────────────────────


async def stream_ollama_react(
    query: str,
    config: GatewayConfig,
    mcp: MCPToolClient,
) -> AsyncIterator[str]:
    """Call Ollama /api/chat with ReAct tool loop, streaming tokens as SSE.

    ReAct loop:
      1. Send query + tool definitions to Ollama
      2. If model calls a tool, execute via MCP, append result, re-send
      3. Repeat up to config.ollama_max_tool_iterations
      4. If tool calling fails consecutively >= threshold, drop tools (knowledge-only)
    """
    if not mcp.is_ready():
        logger.info("MCP not ready — Ollama running without tools")
        tools = []
    else:
        try:
            tools = await asyncio.wait_for(mcp.get_tool_definitions(), timeout=5)
        except Exception as e:
            logger.warning("MCP tools unavailable for Ollama fallback: %s", e)
            tools = []
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    consecutive_tool_failures = 0
    use_tools = bool(tools)

    async with httpx.AsyncClient(
        base_url=config.ollama_url, timeout=httpx.Timeout(120.0)
    ) as client:

        for iteration in range(config.ollama_max_tool_iterations + 1):
            payload: dict[str, Any] = {
                "model": config.ollama_model,
                "messages": messages,
                "stream": True,
                "think": False,  # Disable thinking tokens — they send empty content
            }

            if use_tools and tools:
                payload["tools"] = tools

            logger.info(
                "Ollama ReAct iter=%d, tools=%s, model=%s",
                iteration, use_tools, config.ollama_model,
            )

            assistant_content = ""
            tool_calls: list[dict[str, Any]] = []

            logger.info("Ollama POST /api/chat payload keys=%s", list(payload.keys()))
            async with client.stream(
                "POST", "/api/chat", json=payload
            ) as resp:
                logger.info("Ollama response status=%d", resp.status_code)
                resp.raise_for_status()

                async for raw_line in resp.aiter_lines():
                    if not raw_line.strip():
                        continue

                    logger.debug("Ollama chunk: %s", raw_line[:200])

                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    calls = msg.get("tool_calls")
                    done = chunk.get("done", False)

                    # Stream text tokens to client
                    if content:
                        assistant_content += content
                        sse_payload = json.dumps({"type": "token", "data": content})
                        yield f"data: {sse_payload}\n\n"

                    # Collect tool calls
                    if calls:
                        tool_calls.extend(calls)

                    if done:
                        break

            # If no tool calls, we're done
            if not tool_calls:
                yield "data: [DONE]\n\n"
                return

            # Process tool calls
            messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})

            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                tool_args = func.get("arguments", {})

                # Notify client about tool call
                sse_tc = json.dumps({"type": "tool_call", "name": tool_name, "args": tool_args})
                yield f"data: {sse_tc}\n\n"

                try:
                    result = await mcp.execute_tool(tool_name, tool_args)
                    consecutive_tool_failures = 0
                except Exception as e:
                    logger.warning("Tool %s failed: %s", tool_name, e)
                    result = f"Error: {e}"
                    consecutive_tool_failures += 1

                # Notify client about tool result
                sse_tr = json.dumps({"type": "tool_result", "name": tool_name, "result": result[:500]})
                yield f"data: {sse_tr}\n\n"

                messages.append({"role": "tool", "content": result})

            tool_calls = []

            # Drop tools if too many consecutive failures
            if consecutive_tool_failures >= config.ollama_tool_fail_threshold:
                logger.warning(
                    "Tool failure threshold reached (%d), switching to knowledge-only",
                    consecutive_tool_failures,
                )
                use_tools = False

        # If we exhausted iterations, send done
        yield "data: [DONE]\n\n"


# ── HTTP handlers ────────────────────────────────────────────────────────


async def _send_heartbeats(response: web.StreamResponse, interval: float = 3.0) -> None:
    """Send SSE comment heartbeats to keep the connection alive.

    Gemini CLI can be silent for 20+ seconds while loading MCP tools.
    Without heartbeats, the browser may close the idle connection.
    SSE comments (lines starting with ':') are ignored by EventSource parsers.
    """
    try:
        while True:
            await asyncio.sleep(interval)
            await response.write(b": keepalive\n\n")
    except (asyncio.CancelledError, ConnectionResetError):
        pass


async def handle_chat(request: web.Request) -> web.StreamResponse:
    """POST /v1/chat — SSE streaming chat endpoint.

    Validates X-Gateway-Token. Parses body (query, session_id, conversation_history).
    Prepends last 6 history messages to query. Returns SSE stream.
    Tries Gemini CLI first, falls back to Ollama on failure.
    """
    config: GatewayConfig = request.app["config"]
    mcp_client: MCPToolClient = request.app["mcp_client"]

    # Auth
    token = request.headers.get("X-Gateway-Token", "")
    if not verify_gateway_token(config.gateway_token, token):
        return web.json_response({"error": "Unauthorized"}, status=401)

    # Parse body
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    query = body.get("query", "").strip()
    if not query:
        return web.json_response({"error": "Missing 'query' field"}, status=400)

    history = body.get("conversation_history", [])

    # Prepend last 6 history messages for context
    if history:
        recent = history[-6:]
        context_lines = []
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_lines.append(f"[{role}]: {content}")
        context_block = "\n".join(context_lines)
        query = f"Recent conversation:\n{context_block}\n\nCurrent question: {query}"

    # SSE response — CORS headers MUST be set before prepare() for StreamResponse
    origin = request.headers.get("Origin", "")
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    if origin in config.allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Gateway-Token"
    await response.prepare(request)

    acp: ACPGeminiClient = request.app["acp_client"]
    streamed = False

    try:
        # ── Path 0: Gemini API direct (zero cold start, ~2-3s) ──
        if config.gemini_api_key:
            try:
                # Get tools: prefer MCP, fallback to HTTP executor
                api_tools = []
                api_execute = None
                http_exec: HTTPToolExecutor = request.app["http_executor"]
                if mcp_client.is_ready():
                    try:
                        api_tools = await mcp_client.get_tool_definitions()
                        api_execute = mcp_client.execute_tool
                    except Exception:
                        pass
                if not api_tools and http_exec.is_ready():
                    api_tools = http_exec.get_tool_definitions()
                    api_execute = http_exec.execute_tool

                async for sse_line in stream_gemini_api(
                    query,
                    api_key=config.gemini_api_key,
                    model=config.gemini_api_model,
                    system_prompt=(
                        f"You are Zantara, the AI assistant for {config.agent_name} at Bali Zero. "
                        "Bali Zero is a business services company in Bali (visa, company setup, tax, property) with 5000+ clients. "
                        "Always introduce yourself as Zantara. Respond in the user's language. Be concise. Use tools for real data."
                    ),
                    mcp_tools=api_tools,
                    mcp_execute=api_execute,
                ):
                    await response.write(sse_line.encode("utf-8"))
                    streamed = True
                if streamed:
                    await response.write_eof()
                    return response
            except Exception as e:
                logger.warning("Gemini API failed (%s), trying ACP", e)

        # ── Path 1: ACP persistent (instant, no cold start) ──
        if not streamed and acp.is_ready():
            try:
                first_token_received = False
                async for sse_line in acp.prompt_stream(query):
                    if not first_token_received:
                        first_token_received = True
                    await response.write(sse_line.encode("utf-8"))
                    streamed = True
                if streamed:
                    await response.write_eof()
                    return response
            except Exception as e:
                logger.warning("ACP failed (%s), trying CLI spawn", e)
                streamed = False  # Reset so CLI spawn can take over

        # ── Path 2: Gemini CLI spawn (cold start ~10s, with heartbeat) ──
        if not streamed:
            try:
                heartbeat_task = asyncio.create_task(_send_heartbeats(response))
                try:
                    async for sse_line in stream_gemini_cli(query, config):
                        await response.write(sse_line.encode("utf-8"))
                        streamed = True
                finally:
                    heartbeat_task.cancel()
                if streamed:
                    await response.write_eof()
                    return response
            except Exception as e:
                logger.warning("Gemini CLI spawn failed (%s), falling back to Ollama", e)

        # ── Path 3: Ollama fallback ──
        if not streamed:
            fallback_msg = json.dumps({"type": "system", "data": "Switching to local model..."})
            await response.write(f"data: {fallback_msg}\n\n".encode("utf-8"))
            try:
                async for sse_line in stream_ollama_react(query, config, mcp_client):
                    await response.write(sse_line.encode("utf-8"))
            except Exception as e2:
                logger.error("All paths failed: %s", e2)
                error_msg = json.dumps({"type": "error", "data": f"All AI backends unavailable: {e2}"})
                await response.write(f"data: {error_msg}\n\n".encode("utf-8"))
                await response.write(b"data: [DONE]\n\n")

    except ConnectionResetError:
        logger.info("Client disconnected")
    finally:
        try:
            await response.write_eof()
        except Exception:
            pass

    return response


async def handle_health(request: web.Request) -> web.Response:
    """GET /health — Check Gemini CLI availability and Ollama status."""
    config: GatewayConfig = request.app["config"]

    gemini_ok = shutil.which("gemini") is not None

    ollama_ok = False
    ollama_models: list[str] = []
    try:
        async with httpx.AsyncClient(
            base_url=config.ollama_url, timeout=httpx.Timeout(5.0)
        ) as client:
            resp = await client.get("/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
                data = resp.json()
                ollama_models = [
                    m.get("name", "") for m in data.get("models", [])
                ]
    except Exception:
        pass

    acp: ACPGeminiClient = request.app["acp_client"]
    acp_ready = acp.is_ready()
    status = "healthy" if (acp_ready or gemini_ok or ollama_ok) else "degraded"

    return web.json_response({
        "status": status,
        "acp_persistent": acp_ready,
        "gemini_cli": gemini_ok,
        "ollama": {
            "reachable": ollama_ok,
            "model": config.ollama_model,
            "models_available": ollama_models,
        },
    })


async def handle_config_endpoint(request: web.Request) -> web.Response:
    """GET /v1/config — Return gateway configuration info."""
    config: GatewayConfig = request.app["config"]
    mcp_client: MCPToolClient = request.app["mcp_client"]

    tools_count = 0
    try:
        tools = await mcp_client.get_tool_definitions()
        tools_count = len(tools)
    except Exception:
        pass

    return web.json_response({
        "role": config.role,
        "agent_name": config.agent_name,
        "tools_count": tools_count,
        "llm": {
            "primary": "gemini-cli",
            "fallback": config.ollama_model,
            "ollama_url": config.ollama_url,
        },
    })


# ── CORS middleware ──────────────────────────────────────────────────────


@web.middleware
async def cors_middleware(
    request: web.Request, handler: Any
) -> web.StreamResponse:
    """Set CORS headers for configured origins. Handle OPTIONS preflight."""
    config: GatewayConfig = request.app["config"]
    origin = request.headers.get("Origin", "")

    if request.method == "OPTIONS":
        resp = web.Response(status=204)
        if origin in config.allowed_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-Gateway-Token"
            )
            resp.headers["Access-Control-Max-Age"] = "86400"
        return resp

    resp = await handler(request)

    if origin in config.allowed_origins:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Gateway-Token"
        )

    return resp


# ── Lifecycle hooks ──────────────────────────────────────────────────────


async def on_startup(app: web.Application) -> None:
    """Start ACP + MCP clients in background — don't block HTTP server."""
    acp: ACPGeminiClient = app["acp_client"]
    mcp_client: MCPToolClient = app["mcp_client"]

    async def _connect_acp() -> None:
        try:
            await asyncio.wait_for(acp.connect(), timeout=90)
            logger.info("ACP persistent Gemini CLI connected (pid=%d)", acp._proc.pid)
        except Exception as e:
            logger.warning("ACP connect failed: %s — will use CLI spawn fallback", e)

    async def _connect_mcp() -> None:
        try:
            await asyncio.wait_for(mcp_client.connect(), timeout=90)
            tools = await mcp_client.get_tool_definitions()
            logger.info("MCP client connected, %d tools available", len(tools))
        except asyncio.TimeoutError:
            logger.warning("MCP client timed out — Ollama fallback without tools")
        except Exception as e:
            logger.warning("MCP client failed: %s — Ollama fallback without tools", e)

    # HTTP tool executor (instant, no subprocess)
    http_exec: HTTPToolExecutor = app["http_executor"]
    await http_exec.connect()

    # Launch ACP + MCP in background
    asyncio.create_task(_connect_acp())
    asyncio.create_task(_connect_mcp())


async def on_shutdown(app: web.Application) -> None:
    """Stop ACP + MCP + HTTP clients on app shutdown."""
    acp: ACPGeminiClient = app["acp_client"]
    mcp_client: MCPToolClient = app["mcp_client"]
    http_exec: HTTPToolExecutor = app["http_executor"]
    try:
        await http_exec.close()
    except Exception:
        pass
    try:
        await acp.close()
        logger.info("ACP client closed")
    except Exception as e:
        logger.warning("ACP shutdown error: %s", e)
    try:
        await mcp_client.close()
        logger.info("MCP client closed")
    except Exception as e:
        logger.warning("MCP shutdown error: %s", e)


# ── App factory ──────────────────────────────────────────────────────────


def create_app(config: GatewayConfig | None = None) -> web.Application:
    """Create aiohttp Application with routes and middleware."""
    if config is None:
        config = load_config()

    mcp_client = MCPToolClient(
        role=config.role,
        agent_name=config.agent_name,
    )
    # Resolve MCP server command for ACP session
    mcp_cmd = shutil.which("nuzantara-mcp-server") or ""
    persona = (
        f"[SYSTEM PERSONA] You are Zantara, the AI assistant for {config.agent_name} at Bali Zero. "
        "Bali Zero is a business services company in Bali (visa, company setup, tax, property) with 5000+ clients. "
        "Always introduce yourself as Zantara, NEVER as Gemini or any other name. "
        "Respond in the user's language. Be concise and direct. Use tools for real data — never guess."
    )
    acp_client = ACPGeminiClient(
        gemini_path=shutil.which("gemini") or "gemini",
        cwd=str(Path.home() / "Desktop" / "nuzantara"),
        mcp_server_command=mcp_cmd,
        persona_primer=persona,
        mcp_server_env={
            "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
            "NUZANTARA_API_KEY": os.environ.get("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY"),
            "AGENT_ROLE": config.role,
            "AGENT_NAME": config.agent_name,
        } if mcp_cmd else None,
    )

    http_executor = HTTPToolExecutor(
        backend_url="https://nuzantara-rag.fly.dev",
        api_key=os.environ.get("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY"),
    )

    app = web.Application(middlewares=[cors_middleware])
    app["config"] = config
    app["mcp_client"] = mcp_client
    app["acp_client"] = acp_client
    app["http_executor"] = http_executor

    app.router.add_post("/v1/chat", handle_chat)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/v1/config", handle_config_endpoint)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


# ── Entry point ──────────────────────────────────────────────────────────


def main() -> None:
    """Load config, create SSL context if certs available, run app."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    config = load_config()
    app = create_app(config)

    ssl_ctx = None
    if config.has_tls():
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(config.tls_cert, config.tls_key)
        logger.info("TLS enabled with mkcert certificates")

    logger.info(
        "Starting Zantara Gateway on 127.0.0.1:%d (role=%s, agent=%s)",
        config.port, config.role, config.agent_name,
    )

    web.run_app(
        app,
        host="127.0.0.1",
        port=config.port,
        ssl_context=ssl_ctx,
    )


if __name__ == "__main__":
    main()
