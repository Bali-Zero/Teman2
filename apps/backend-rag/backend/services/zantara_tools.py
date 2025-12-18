"""
ZANTARA Tools - Python Native Tools for ZANTARA AI
Direct execution (no HTTP calls) - faster & more reliable
"""

import logging
from typing import Any

from services.collaborator_service import CollaboratorService
from services.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)


class ZantaraTools:
    """
    Native Python tools for Zantara AI
    - get_pricing: Official Bali Zero pricing (NO AI generation)
    - Team tools: Team roster, search, etc.
    - Memory tools: User memory operations
    """

    def __init__(self):
        self.pricing_service = get_pricing_service()
        self.collaborator_service = CollaboratorService()
        logger.info("✅ ZantaraTools initialized")

    async def execute_tool(
        self, tool_name: str, tool_input: dict[str, Any], _user_id: str = "system"
    ) -> dict[str, Any]:
        """
        Execute a Zantara tool

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool parameters
            user_id: User ID for context

        Returns:
            Tool execution result
        """
        try:
            logger.info(f"🔧 Executing ZantaraTool: {tool_name}")

            if tool_name == "get_pricing":
                return await self._get_pricing(tool_input)
            elif tool_name == "search_team_member":
                return await self._search_team_member(tool_input)
            elif tool_name == "get_team_members_list":
                return await self._get_team_members_list(tool_input)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"❌ Error executing {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    async def _get_pricing(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Get official Bali Zero pricing

        Args:
            params: {
                "service_type": str (visa|kitas|business_setup|tax_consulting|all)
                "query": str (optional - search query)
            }
        """
        try:
            service_type = params.get("service_type", "all")
            query = params.get("query")

            logger.info(f"💰 get_pricing: service_type={service_type}, query={query}")

            # If query provided, search specifically
            if query:
                result = self.pricing_service.search_service(query)
            else:
                result = self.pricing_service.get_pricing(service_type)

            # Check if pricing loaded successfully
            if not self.pricing_service.loaded:
                return {
                    "success": False,
                    "error": "Official prices not loaded",
                    "fallback_contact": {
                        "email": "info@balizero.com",
                        "whatsapp": "+62 813 3805 1876",
                    },
                }

            return {"success": True, "data": result}

        except Exception as e:
            logger.error(f"❌ get_pricing error: {e}")
            return {"success": False, "error": f"Pricing lookup failed: {str(e)}"}

    async def _search_team_member(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Search team member by name

        Args:
            params: {"query": str}
        """
        query = params.get("query", "").lower().strip()

        if not query:
            return {"success": False, "error": "Please provide a name to search for"}

        logger.info(f"👥 search_team_member: query={query}")

        profiles = self.collaborator_service.search_members(query)

        if not profiles:
            return {
                "success": True,
                "data": {
                    "message": f"No team member found matching '{query}'",
                    "suggestion": "Try searching by first name or department",
                },
            }

        results = [
            {
                "name": profile.name,
                "email": profile.email,
                "role": profile.role,
                "department": profile.department,
                "expertise_level": profile.expertise_level,
                "language": profile.language,
                "notes": profile.notes,
                "traits": profile.traits,
            }
            for profile in profiles
        ]

        return {"success": True, "data": {"count": len(results), "results": results}}

    async def _get_team_members_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Get full team roster, optionally filtered by department

        Args:
            params: {"department": str (optional)}
        """
        department = (
            params.get("department", "").lower().strip() if params.get("department") else None
        )

        logger.info(f"👥 get_team_members_list: department={department}")

        profiles = self.collaborator_service.list_members(department)

        roster = [
            {
                "name": profile.name,
                "email": profile.email,
                "role": profile.role,
                "department": profile.department,
                "expertise_level": profile.expertise_level,
                "language": profile.language,
                "traits": profile.traits,
                "notes": profile.notes,
            }
            for profile in profiles
        ]

        # Group by department for better readability
        by_department = {}
        for member in roster:
            dept = member["department"]
            if dept not in by_department:
                by_department[dept] = []
            by_department[dept].append(member)

        # Get team stats
        stats = self.collaborator_service.get_team_stats()

        return {
            "success": True,
            "data": {
                "total_members": len(roster),
                "by_department": by_department,
                "roster": roster,
                "stats": stats,
            },
        }

    def get_tool_definitions(self, _include_admin_tools: bool = False) -> list[dict[str, Any]]:
        """
        Get ZANTARA AI-compatible tool definitions

        Returns:
            List of tool definitions for ZANTARA AI (legacy Anthropic format for compatibility)
        """
        tools = [
            {
                "name": "get_pricing",
                "description": """Get OFFICIAL Bali Zero pricing for services.

⚠️ CRITICAL: ALWAYS use this tool for ANY pricing question. NEVER generate prices from memory.

This returns OFFICIAL prices from the database including:
- Visa prices (retrieved from database)
- Long-stay permit prices (retrieved from database)
- Business services (retrieved from database)
- Tax services (retrieved from database)
- All pricing data is stored in Qdrant/PostgreSQL and retrieved via this tool

MANDATORY USAGE:
- If user asks about ANY price → CALL THIS TOOL
- Examples that REQUIRE this tool:
  * "How much does [service] cost?"
  * "Berapa harga [service]?"
  * "What's the price for..."
  * "Quanto costa..."

DO NOT generate prices from memory - prices change and must be accurate. All pricing comes from the database.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "service_type": {
                            "type": "string",
                            "enum": [
                                "visa",
                                "kitas",
                                "business_setup",
                                "tax_consulting",
                                "legal",
                                "all",
                            ],
                            "description": "Type of service to get pricing for (use 'all' to see everything)",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional: specific search query (e.g. 'long-stay permit', 'company setup', 'visa')",
                        },
                    },
                    "required": ["service_type"],
                },
            },
            {
                "name": "search_team_member",
                "description": "Search for a Bali Zero team member by name. Returns contact info, role, expertise level.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Name to search for (e.g. 'Dea', 'Zero', 'Krisna')",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_team_members_list",
                "description": "Get full Bali Zero team roster, optionally filtered by department",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "department": {
                            "type": "string",
                            "description": "Optional: filter by department (technology, operations, creative, etc.)",
                        }
                    },
                },
            },
        ]

        logger.info(f"📋 Returning {len(tools)} ZantaraTool definitions")
        return tools


# Global singleton
_zantara_tools: ZantaraTools | None = None


def get_zantara_tools() -> ZantaraTools:
    """Get or create global ZantaraTools instance"""
    global _zantara_tools
    if _zantara_tools is None:
        _zantara_tools = ZantaraTools()
    return _zantara_tools
