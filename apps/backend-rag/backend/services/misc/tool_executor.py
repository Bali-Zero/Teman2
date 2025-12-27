"""
TOOL EXECUTOR SERVICE
Handles ZANTARA AI tool use execution
All tools are Python-native (ZantaraTools, GmailService, CalendarService, etc.)
+ MCP Client tools (filesystem, memory, brave-search, etc.)
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from services.mcp_client_service import MCPClientService
    from services.zantara_tools import ZantaraTools

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tools during AI conversations
    - ZantaraTools (Python): team data, memory, pricing - direct execution
    - MCP tools: filesystem, memory, brave-search, etc. via MCP protocol
    - All handlers migrated to Python services (no TypeScript backend)
    """

    def __init__(
        self,
        zantara_tools: Optional["ZantaraTools"] = None,
        mcp_client: Optional["MCPClientService"] = None,
    ):
        """
        Initialize tool executor

        Args:
            zantara_tools: ZantaraTools instance for direct Python tool execution
            mcp_client: MCPClientService instance for MCP tool execution
        """
        self.zantara_tools = zantara_tools
        self.mcp_client = mcp_client

        # ZantaraTools function names (Python - executed directly)
        self.zantara_tool_names = {
            "get_team_logins_today",
            "get_team_active_sessions",
            "get_team_member_stats",
            "get_team_overview",
            "get_team_members_list",  # Team roster (public)
            "search_team_member",  # Team search (public)
            "get_session_details",
            "end_user_session",
            "retrieve_user_memory",
            "search_memory",
            "get_pricing",
        }

        logger.info(
            f"🔧 ToolExecutor initialized (ZantaraTools: {'✅' if zantara_tools else '❌'}, MCP: {'✅' if mcp_client else '❌'})"
        )

    async def execute_tool_calls(self, tool_uses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Execute multiple tool calls from ZANTARA AI response

        Args:
            tool_uses: List of tool use blocks from ZANTARA AI API (legacy Anthropic format)

        Returns:
            List of tool results to send back to ZANTARA AI

        Example input (from ZANTARA AI - legacy Anthropic format):
        [
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "gmail_send",
                "input": {"to": "client@example.com", "subject": "Hello", "body": "..."}
            }
        ]

        Example output (to send back):
        [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": [{"type": "output_text", "text": "Email sent successfully"}]
            }
        ]
        """
        results = []

        for tool_use in tool_uses:
            # Handle both dict and ToolUseBlock objects
            if hasattr(tool_use, "id"):
                # Pydantic ToolUseBlock object (legacy Anthropic SDK format)
                tool_id = tool_use.id
                tool_name = tool_use.name
                tool_input = tool_use.input or {}
            else:
                # Dict format
                tool_id = tool_use.get("id")
                tool_name = tool_use.get("name")
                tool_input = tool_use.get("input", {})

            try:
                # Check if this is a ZantaraTools function (Python - direct execution)
                if tool_name in self.zantara_tool_names and self.zantara_tools:
                    logger.info(f"🔧 [ZantaraTools] Executing: {tool_name} (Python)")

                    # Execute ZantaraTools directly
                    result = await self.zantara_tools.execute_tool(
                        tool_name=tool_name, tool_input=tool_input, user_id="system"
                    )

                    if not result.get("success"):
                        error_message = result.get("error", "Unknown error")
                        logger.error(f"❌ [ZantaraTools] {tool_name} failed: {error_message}")
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "is_error": True,
                                "content": f"Error: {error_message}",
                            }
                        )
                        continue

                    # Extract data from ZantaraTools result
                    payload = result.get("data", result)
                    if isinstance(payload, dict | list):
                        content_text = json.dumps(payload, ensure_ascii=False)
                    else:
                        content_text = str(payload)

                    logger.info(f"✅ [ZantaraTools] {tool_name} executed successfully")
                    results.append(
                        {"type": "tool_result", "tool_use_id": tool_id, "content": content_text}
                    )

                # Check if this is an MCP tool
                elif self.mcp_client and self.mcp_client.is_mcp_tool(tool_name):
                    logger.info(f"🔌 [MCP] Executing: {tool_name}")

                    result = await self.mcp_client.execute_tool(
                        tool_name=tool_name, params=tool_input
                    )

                    if not result.get("success"):
                        error_message = result.get("error", "Unknown MCP error")
                        logger.error(f"❌ [MCP] {tool_name} failed: {error_message}")
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "is_error": True,
                                "content": f"Error: {error_message}",
                            }
                        )
                        continue

                    # Extract data from MCP result
                    payload = result.get("data", result)
                    if isinstance(payload, dict | list):
                        content_text = json.dumps(payload, ensure_ascii=False)
                    else:
                        content_text = str(payload)

                    logger.info(f"✅ [MCP] {tool_name} executed successfully")
                    results.append(
                        {"type": "tool_result", "tool_use_id": tool_id, "content": content_text}
                    )

                else:
                    # Tool not found - return error with available tools
                    available = sorted(self.zantara_tool_names)
                    if self.mcp_client:
                        available.extend(sorted(self.mcp_client.available_tools.keys()))
                    error_message = (
                        f"Tool '{tool_name}' not available. Available tools: {', '.join(available)}"
                    )
                    logger.warning(f"⚠️ Tool not found: {tool_name}")
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "is_error": True,
                            "content": error_message,
                        }
                    )

            except Exception as e:
                logger.error(f"❌ Tool execution failed for {tool_name}: {e}")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "is_error": True,
                        "content": f"Tool execution error: {str(e)}",
                    }
                )

        return results

    async def execute_tool(
        self, tool_name: str, tool_input: dict[str, Any], user_id: str = "system"
    ) -> dict[str, Any]:
        """
        Execute a single tool (for prefetch system)

        Args:
            tool_name: Tool name to execute
            tool_input: Tool parameters
            user_id: User ID for context

        Returns:
            {
                "success": bool,
                "result": Any,
                "error": str (if failed)
            }
        """
        try:
            # Check if this is a ZantaraTools function (Python - direct execution)
            if tool_name in self.zantara_tool_names and self.zantara_tools:
                logger.info(f"🔧 [ZantaraTools/Prefetch] Executing: {tool_name} (Python)")

                # Execute ZantaraTools directly
                result = await self.zantara_tools.execute_tool(
                    tool_name=tool_name, tool_input=tool_input, user_id=user_id
                )

                if not result.get("success"):
                    error_message = result.get("error", "Unknown error")
                    logger.error(f"❌ [ZantaraTools/Prefetch] {tool_name} failed: {error_message}")
                    return {"success": False, "error": error_message}

                # Extract data from ZantaraTools result
                payload = result.get("data", result)
                logger.info(f"✅ [ZantaraTools/Prefetch] {tool_name} executed successfully")
                return {"success": True, "result": payload}

            # Check if this is an MCP tool
            elif self.mcp_client and self.mcp_client.is_mcp_tool(tool_name):
                logger.info(f"🔌 [MCP/Prefetch] Executing: {tool_name}")

                result = await self.mcp_client.execute_tool(tool_name=tool_name, params=tool_input)

                if not result.get("success"):
                    error_message = result.get("error", "Unknown MCP error")
                    logger.error(f"❌ [MCP/Prefetch] {tool_name} failed: {error_message}")
                    return {"success": False, "error": error_message}

                payload = result.get("data", result)
                logger.info(f"✅ [MCP/Prefetch] {tool_name} executed successfully")
                return {"success": True, "result": payload}

            else:
                # Tool not found - return error with available tools
                available = sorted(self.zantara_tool_names)
                if self.mcp_client:
                    available.extend(sorted(self.mcp_client.available_tools.keys()))
                error_message = (
                    f"Tool '{tool_name}' not available. Available tools: {', '.join(available)}"
                )
                logger.warning(f"⚠️ [Prefetch] Tool not found: {tool_name}")
                return {"success": False, "error": error_message}

        except Exception as e:
            logger.error(f"❌ [Prefetch] Tool execution failed for {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    def get_all_tools_for_ai(self) -> list[dict]:
        """
        Get all available tools (ZantaraTools + MCP) in Gemini function calling format.
        Call this to get the tools list to pass to the AI.
        """
        tools = []

        # Add MCP tools if available
        if self.mcp_client:
            tools.extend(self.mcp_client.get_tools_for_gemini())
            logger.debug(f"📦 Added {len(self.mcp_client.available_tools)} MCP tools")

        return tools

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """
        Get ZANTARA AI-compatible tool definitions

        Returns:
            List of tool definitions for ZANTARA AI (legacy Anthropic format for compatibility)
        """
        tools = []

        # Load ZantaraTools (Python - always available)
        if self.zantara_tools:
            try:
                zantara_tool_defs = self.zantara_tools.get_tool_definitions(
                    include_admin_tools=False
                )
                tools.extend(zantara_tool_defs)
                logger.info(
                    f"📋 Loaded {len(zantara_tool_defs)} ZantaraTools (Python): {[t['name'] for t in zantara_tool_defs]}"
                )
            except Exception as e:
                logger.error(f"❌ Failed to load ZantaraTools: {e}")

        logger.info(f"📋 Total tools loaded for AI: {len(tools)}")
        return tools
