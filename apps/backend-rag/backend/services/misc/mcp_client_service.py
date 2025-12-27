"""
MCP Client Service - Connette Nuzantara a MCP Servers esterni
Permette all'AI di usare tool MCP (brave-search, filesystem, etc.)
"""

import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClientService:
    """
    Client MCP per Nuzantara.
    Connette l'AI a server MCP esterni per estendere le capacità.
    """

    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self.available_tools: dict[str, dict] = {}
        self._initialized = False
        logger.info("🔌 MCPClientService created")

    async def initialize(self):
        """Inizializza connessioni ai server MCP configurati"""
        if self._initialized:
            return

        # Server MCP da connettere (quelli che non richiedono API key)
        # Server MCP da connettere (quelli che non richiedono API key)
        servers = {
            # "filesystem": {
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            # },
            # "memory": {
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-memory"],
            # },
            # "sequential-thinking": {
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            # },
        }

        for name, config in servers.items():
            try:
                await self._connect_server(name, config)
                logger.info(f"✅ MCP Server '{name}' connected")
            except Exception as e:
                logger.warning(f"⚠️ MCP Server '{name}' failed: {e}")

        self._initialized = True
        logger.info(f"🔌 MCPClientService initialized with {len(self.available_tools)} tools")

    async def _connect_server(self, name: str, config: dict):
        """Connette a un singolo server MCP"""
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env"),
        )

        # Crea sessione
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Inizializza
                await session.initialize()

                # Lista tool disponibili
                tools_response = await session.list_tools()

                for tool in tools_response.tools:
                    tool_name = f"mcp_{name}_{tool.name}"
                    self.available_tools[tool_name] = {
                        "server": name,
                        "original_name": tool.name,
                        "description": tool.description,
                        "schema": tool.inputSchema,
                    }
                    logger.debug(f"  📦 Tool registered: {tool_name}")

    def get_tools_for_gemini(self) -> list[dict]:
        """
        Restituisce i tool MCP in formato Gemini Function Calling.
        Da aggiungere agli altri tool di ZantaraTools.
        """
        gemini_tools = []

        for tool_name, tool_info in self.available_tools.items():
            gemini_tools.append(
                {
                    "name": tool_name,
                    "description": f"[MCP] {tool_info['description']}",
                    "parameters": tool_info["schema"],
                }
            )

        return gemini_tools

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Esegue un tool MCP.

        Args:
            tool_name: Nome del tool (es. "mcp_filesystem_read_file")
            params: Parametri del tool

        Returns:
            Risultato dell'esecuzione
        """
        if tool_name not in self.available_tools:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        tool_info = self.available_tools[tool_name]
        server_name = tool_info["server"]
        original_name = tool_info["original_name"]

        logger.info(f"🔧 Executing MCP tool: {tool_name} -> {server_name}/{original_name}")

        try:
            # Riconnetti al server per eseguire
            servers_config = {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                },
                "memory": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-memory"],
                },
                "sequential-thinking": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                },
            }

            config = servers_config.get(server_name)
            if not config:
                return {"success": False, "error": f"Server '{server_name}' not configured"}

            server_params = StdioServerParameters(
                command=config["command"],
                args=config["args"],
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Chiama il tool
                    result = await session.call_tool(original_name, params)

                    return {
                        "success": True,
                        "data": result.content,
                    }

        except Exception as e:
            logger.error(f"❌ MCP tool execution failed: {e}")
            return {"success": False, "error": str(e)}

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Verifica se un tool è un MCP tool"""
        return tool_name.startswith("mcp_")


# Singleton instance
_mcp_client: MCPClientService | None = None


def get_mcp_client() -> MCPClientService:
    """Get or create MCP client singleton"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClientService()
    return _mcp_client


async def initialize_mcp_client():
    """Initialize MCP client (call at startup)"""
    client = get_mcp_client()
    await client.initialize()
    return client
