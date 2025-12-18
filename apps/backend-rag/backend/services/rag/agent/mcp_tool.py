"""
MCP Super Tool - Dà a Zantara i superpoteri MCP
Solo per admin (zero@balizero.com)

Permette a Zantara di:
- Cercare sul web in tempo reale (Brave Search)
- Leggere/scrivere file
- Salvare memoria persistente
- Ragionamento step-by-step
"""

import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from services.rag.agent.structures import BaseTool

logger = logging.getLogger(__name__)

# Admin autorizzati
ADMIN_EMAILS = {"zero@balizero.com"}


def is_mcp_admin(email: str | None) -> bool:
    """Verifica se l'utente è admin MCP"""
    if not email:
        return False
    return email.lower() in {e.lower() for e in ADMIN_EMAILS}


class MCPSuperTool(BaseTool):
    """
    Tool MCP che dà superpoteri a Zantara.
    Disponibile SOLO per admin.

    L'email viene passata tramite il parametro _user_email nell'execute.
    """

    # Configurazione server MCP
    MCP_SERVERS = {
        "brave_search": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": None},  # Viene letto da env
        },
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/tmp",
            ],
        },
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
        },
    }

    def __init__(self):
        logger.info("🦸 MCPSuperTool initialized (admin verification at runtime)")

    @property
    def name(self) -> str:
        return "mcp_super"

    @property
    def description(self) -> str:
        return """Super tool with special powers (ADMIN ONLY - zero@balizero.com). Use this for:
- web_search: Search the web in real-time for current information (news, updates, trends)
- read_file: Read a file from the server filesystem
- write_file: Write content to a file on the server
- save_memory: Save important information to persistent memory
- recall_memory: Recall previously saved information

IMPORTANT: Use web_search when user asks about current events, news, or needs real-time data.
Example: "mcp_super" with action="web_search", query="latest visa regulations bali 2025"
"""

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "web_search",
                        "read_file",
                        "write_file",
                        "save_memory",
                        "recall_memory",
                    ],
                    "description": "The action to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for web_search) or memory key (for memory operations)",
                },
                "path": {"type": "string", "description": "File path (for read_file/write_file)"},
                "content": {
                    "type": "string",
                    "description": "Content to write (for write_file) or value to save (for save_memory)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> str:
        """Esegue l'azione MCP richiesta"""

        # Get user email from kwargs (passed by orchestrator)
        user_email = kwargs.get("_user_email") or kwargs.get("_user_id")

        # Check admin
        if not is_mcp_admin(user_email):
            logger.warning(f"🚫 MCPSuperTool denied for non-admin: {user_email}")
            return "ERROR: This tool is only available for admin users (zero@balizero.com). If you are the admin, make sure you are logged in with the correct email."

        action = kwargs.get("action")
        query = kwargs.get("query", "")
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        logger.info(f"🦸 MCPSuperTool executing: {action} (admin: {user_email})")

        try:
            if action == "web_search":
                return await self._web_search(query)
            elif action == "read_file":
                return await self._read_file(path)
            elif action == "write_file":
                return await self._write_file(path, content)
            elif action == "save_memory":
                return await self._save_memory(query, content)
            elif action == "recall_memory":
                return await self._recall_memory(query)
            else:
                return f"ERROR: Unknown action '{action}'"
        except Exception as e:
            logger.error(f"❌ MCPSuperTool error: {e}")
            return f"ERROR: {str(e)}"

    async def _call_mcp(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Chiama un tool MCP"""
        config = self.MCP_SERVERS.get(server_name)
        if not config:
            return f"ERROR: Server '{server_name}' not configured"

        import os

        env = config.get("env", {})
        # Resolve environment variables
        resolved_env = {}
        for k, v in env.items():
            if v is None:
                resolved_env[k] = os.environ.get(k, "")
            else:
                resolved_env[k] = v

        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=resolved_env if resolved_env else None,
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)

                    # Extract text content
                    if hasattr(result, "content") and result.content:
                        texts = []
                        for item in result.content:
                            if hasattr(item, "text"):
                                texts.append(item.text)
                        return "\n".join(texts) if texts else str(result)
                    return str(result)
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            return f"ERROR calling MCP: {str(e)}"

    async def _web_search(self, query: str) -> str:
        """Cerca sul web con Brave Search"""
        if not query:
            return "ERROR: query is required for web_search"

        logger.info(f"🔍 Web search: {query}")
        result = await self._call_mcp("brave_search", "brave_web_search", {"query": query})
        return f"Web search results for '{query}':\n{result}"

    async def _read_file(self, path: str) -> str:
        """Legge un file"""
        if not path:
            return "ERROR: path is required for read_file"

        logger.info(f"📄 Reading file: {path}")
        result = await self._call_mcp("filesystem", "read_file", {"path": path})
        return f"Content of {path}:\n{result}"

    async def _write_file(self, path: str, content: str) -> str:
        """Scrive un file"""
        if not path or not content:
            return "ERROR: path and content are required for write_file"

        logger.info(f"📝 Writing file: {path}")
        result = await self._call_mcp(
            "filesystem", "write_file", {"path": path, "content": content}
        )
        return f"File written to {path}: {result}"

    async def _save_memory(self, key: str, value: str) -> str:
        """Salva in memoria persistente"""
        if not key or not value:
            return "ERROR: query (key) and content (value) are required for save_memory"

        logger.info(f"💾 Saving memory: {key}")
        result = await self._call_mcp("memory", "store", {"key": key, "value": value})
        return f"Memory saved with key '{key}': {result}"

    async def _recall_memory(self, key: str) -> str:
        """Recupera dalla memoria persistente"""
        if not key:
            return "ERROR: query (key) is required for recall_memory"

        logger.info(f"🧠 Recalling memory: {key}")
        result = await self._call_mcp("memory", "retrieve", {"key": key})
        return f"Memory for '{key}': {result}"
