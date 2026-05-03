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
        self._ready = False  # set True after successful connect + init

    def is_ready(self) -> bool:
        """True if MCP session is fully initialized and can list/execute tools."""
        return self._ready

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
        self._ready = True
        logger.info("MCP session established for role=%s", self._role)

    async def close(self) -> None:
        """Shut down MCP session and subprocess."""
        if self._session:
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

        texts = []
        for block in result.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else str(result.content)
