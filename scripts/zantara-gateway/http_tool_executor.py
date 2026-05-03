# scripts/zantara-gateway/http_tool_executor.py
"""
HTTP Tool Executor — calls backend REST API directly, bypassing MCP stdio.

Used on hardware where MCP stdio client doesn't connect (Intel Macs).
Same endpoints, same auth, same data — just HTTP instead of stdio.
"""

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger("zantara-gateway.http-tools")

BACKEND_URL = "https://nuzantara-rag.fly.dev"

# Tool name → (method, path, param_mapping)
# param_mapping: how to transform tool args to API request
TOOL_ROUTES: dict[str, tuple[str, str]] = {
    # CRM
    "list_clients": ("GET", "/api/crm/clients/"),
    "get_client": ("GET", "/api/crm/clients/{client_id}"),
    "get_client_stats": ("GET", "/api/crm/clients/stats/overview"),
    "get_client_timeline": ("GET", "/api/crm/interactions/client/{client_id}/timeline"),
    "list_practices": ("GET", "/api/crm/practices/"),
    "get_practice": ("GET", "/api/crm/practices/{practice_id}"),
    "get_client_timeline": ("GET", "/api/crm/interactions/client/{client_id}/timeline"),
    "get_expiry_alerts": ("GET", "/api/crm/expiry-alerts"),
    "get_compliance_alerts": ("GET", "/api/crm/compliance-alerts"),
    "create_client": ("POST", "/api/crm/clients/"),
    "create_practice": ("POST", "/api/crm/practices/"),
    "update_practice_status": ("PATCH", "/api/crm/practices/{practice_id}"),
    "log_interaction": ("POST", "/api/crm/interactions"),
    # Visa & Knowledge
    "list_visa_types": ("GET", "/api/knowledge/visa-types"),
    "get_visa_details": ("GET", "/api/knowledge/visa-types/{visa_code}"),
    "search_kbli": ("GET", "/api/v1/kbli-notebook/search"),
    "ask_legal": ("POST", "/api/agentic-rag/query"),
    # Pricing
    "calculate_pricing": ("GET", "/api/pricing/calculate"),
    "get_all_prices": ("GET", "/api/pricing/all"),
    # Content & Intel
    "list_articles": ("GET", "/api/news"),
    "get_article": ("GET", "/api/news/{article_id}"),
    "compose_article": ("POST", "/api/news/compose"),
    "publish_article": ("POST", "/api/news/{article_id}/publish"),
    "search_intel": ("GET", "/api/intel/search"),
    "list_staging_items": ("GET", "/api/intel/staging/pending"),
    "approve_staging_item": ("POST", "/api/intel/staging/{item_id}/approve"),
    "publish_intel": ("POST", "/api/intel/publish"),
    "get_intel_metrics": ("GET", "/api/intel/metrics"),
    "get_critical_alerts": ("GET", "/api/intel/critical"),
    "get_intel_trends": ("GET", "/api/intel/trends"),
    # Comms
    "send_email": ("POST", "/api/notifications/send-email"),
    "send_whatsapp": ("POST", "/api/whatsapp/send"),
    "send_portal_message": ("POST", "/api/portal/messages"),
    # Federation
    "federation_send": ("POST", "/api/federation/send"),
}


class HTTPToolExecutor:
    """Executes tool calls via direct HTTP to backend Fly.io."""

    def __init__(self, backend_url: str = BACKEND_URL, api_key: str = ""):
        self._backend_url = backend_url.rstrip("/")
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_connections=10),
        )
        logger.info("HTTP tool executor ready (%d tools)", len(TOOL_ROUTES))

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def is_ready(self) -> bool:
        return self._client is not None and not self._client.is_closed

    # Priority tools for Gemini API (free tier can't handle 31+ declarations)
    # Split into READ (always) + WRITE (for daily operations)
    PRIORITY_TOOLS: dict[str, str] = {
        # READ — CRM
        "list_clients": "List CRM clients. Optional: search (string), limit (int, default 20).",
        "get_client": "Get client details. Args: client_id (string, required).",
        "get_client_stats": "Get statistics: total clients, by status, by team member.",
        "get_client_timeline": "Get interaction history for a client. Args: client_id (string).",
        "list_practices": "List practices/cases. Optional: status, assigned_to.",
        "get_practice": "Get practice details. Args: practice_id (string).",
        "get_expiry_alerts": "Get visas/documents expiring soon. Args: days_ahead (int, default 90).",
        "get_compliance_alerts": "Get compliance alerts for the team.",
        # READ — Pricing & Knowledge
        "calculate_pricing": "Calculate service price. Args: service_type (string).",
        "get_all_prices": "Get full pricing catalog for all Bali Zero services.",
        "list_visa_types": "List all available visa types in Indonesia.",
        "get_visa_details": "Get details of a specific visa. Args: visa_code (string).",
        # WRITE — CRM Operations
        "create_client": "Create a new client. Args: full_name, email, phone, nationality.",
        "create_practice": "Create a new practice/case. Args: client_id, service_type, notes.",
        "update_practice_status": "Update practice status. Args: practice_id, status, notes.",
        "log_interaction": "Log an interaction with a client. Args: client_id, type, notes.",
        # WRITE — Comms
        "send_email": "Send email. Args: to (email), subject, body.",
        "send_whatsapp": "Send WhatsApp message. Args: phone (string), message (string).",
        "send_portal_message": "Send message to client portal. Args: client_id, message.",
        # READ — Content & Intel
        "search_intel": "Search news and regulations. Args: query (string).",
        "list_articles": "List published articles on the website.",
    }

    def get_tool_definitions(self) -> list[dict]:
        """Return top 10 tool definitions for Gemini API free tier."""
        tools = []
        for name, desc in self.PRIORITY_TOOLS.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": {"type": "object", "properties": {}},
                },
            })
        return tools

    async def execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool by calling the backend REST API."""
        if not self._client:
            return json.dumps({"error": "HTTP executor not connected"})

        route = TOOL_ROUTES.get(name)
        if not route:
            return json.dumps({"error": f"Unknown tool: {name}"})

        method, path_template = route

        # Substitute path params from args
        path = path_template
        used_keys = set()
        for key, val in args.items():
            placeholder = "{" + key + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(val))
                used_keys.add(key)

        # Remaining args become query params (GET) or body (POST/PATCH)
        remaining = {k: v for k, v in args.items() if k not in used_keys}

        url = f"{self._backend_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
            headers["X-API-Key"] = self._api_key

        try:
            if method == "GET":
                resp = await self._client.get(url, params=remaining, headers=headers)
            elif method == "POST":
                resp = await self._client.post(url, json=remaining, headers=headers)
            elif method == "PATCH":
                resp = await self._client.patch(url, json=remaining, headers=headers)
            else:
                return json.dumps({"error": f"Unsupported method: {method}"})

            if resp.status_code >= 400:
                return json.dumps({"error": f"API {resp.status_code}", "body": resp.text[:500]})

            return resp.text[:5000]  # Truncate large responses

        except Exception as e:
            logger.warning("HTTP tool %s failed: %s", name, e)
            return json.dumps({"error": str(e)})
