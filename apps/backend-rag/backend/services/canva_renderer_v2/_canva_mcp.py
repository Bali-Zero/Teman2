"""Canva MCP client wrapper over mcp SDK 1.12.4 streamable HTTP transport.

Provides:
- CanvaMcpClient async context manager — manages ClientSession lifecycle.
- import_design_from_url() — wraps mcp call_tool + parses design_id.
- move_item_to_folder() — best-effort, non-fatal on failure.
- Transient-vs-permanent error classifier for orchestrator backoff logic.

OAuth handled by OrchestratorTokenStorage passed to OAuthClientProvider.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from backend.services.canva_renderer_v2._token_storage import OrchestratorTokenStorage

logger = logging.getLogger(__name__)

CANVA_MCP_URL = "https://mcp.canva.com/mcp"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


class CanvaImportError(RuntimeError):
    """Raised by import_design_from_url on permanent failure."""


def is_transient_error(exc: Exception) -> bool:
    """Classify an exception as transient (retry-able) or permanent.

    Returns True for HTTP 408/425/429/5xx and httpx network/timeout errors.
    Returns False for all other exceptions (e.g. 400, 401, 403, 404).
    """
    status = getattr(exc, "status_code", None)
    if status in TRANSIENT_HTTP_STATUS:
        return True
    if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
        return True
    return False


_DESIGN_ID_RE = re.compile(r"DA[A-Za-z0-9_-]{6,}")


def parse_design_id(result: Any) -> str:
    """Extract design_id from mcp call_tool response payload.

    Tolerates 2 shapes:
    1. {"content": [{"text": '{"design_id": "..."}'}]} — JSON-in-text
    2. {"content": [{"text": "https://www.canva.com/design/DA.../edit"}]} — URL embed
    """
    content = (
        result.get("content")
        if isinstance(result, dict)
        else getattr(result, "content", None)
    )
    if not content:
        raise CanvaImportError(f"MCP result missing content: {result!r}")

    first = content[0]
    text = (
        first.get("text")
        if isinstance(first, dict)
        else getattr(first, "text", None)
    )
    if not text:
        raise CanvaImportError(f"MCP result text empty: {first!r}")

    # Try JSON first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "design_id" in parsed:
            return parsed["design_id"]
    except json.JSONDecodeError:
        pass

    # Fall back to regex over URL or raw text
    m = _DESIGN_ID_RE.search(text)
    if m:
        return m.group(0)
    raise CanvaImportError(f"design_id not found in MCP response: {text[:200]!r}")


class CanvaMcpClient:
    """Async context manager wrapping mcp.ClientSession against Canva HTTP MCP.

    Usage::

        async with CanvaMcpClient() as client:
            design_id, edit_url = await client.import_design_from_url(url, title="My PDF")

    OAuth tokens are loaded from OrchestratorTokenStorage (env WR2_CANVA_TOKEN_FILE +
    WR2_CANVA_HMAC_KEY). Interactive re-auth raises CanvaImportError — the cron path
    cannot open a browser; run scripts/wr2_bootstrap_canva_oauth.py on Pro to refresh.
    """

    def __init__(self, server_url: str = CANVA_MCP_URL) -> None:
        self.server_url = server_url
        self._session: ClientSession | None = None
        self._stream_cm = None
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CanvaMcpClient":
        storage = OrchestratorTokenStorage()
        info = await storage.get_client_info()
        oauth = OAuthClientProvider(
            server_url=self.server_url,
            client_metadata=OAuthClientMetadata(
                client_name="WR2 Pipeline Orchestrator",
                redirect_uris=[AnyUrl(u) for u in info.redirect_uris],
                grant_types=info.grant_types,
                response_types=info.response_types,
                token_endpoint_auth_method=info.token_endpoint_auth_method,
                scope=info.scope,
            ),
            storage=storage,
            redirect_handler=self._reject_interactive,
            callback_handler=self._reject_interactive,
        )
        # Short-lived launchd-tick orchestrator (≤5min lifetime); this is the
        # single MCP session for the entire run, closed in __aexit__ — no leak.
        self._http_client = httpx.AsyncClient(  # golden-rule-10-exempt: short-lived cron process, single session, explicit aclose() in __aexit__
            auth=oauth, follow_redirects=True, timeout=60.0
        )
        self._stream_cm = streamable_http_client(
            self.server_url, http_client=self._http_client
        )
        (read, write, _) = await self._stream_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session is not None:
            await self._session.__aexit__(exc_type, exc, tb)
        if self._stream_cm is not None:
            await self._stream_cm.__aexit__(exc_type, exc, tb)
        if self._http_client is not None:
            await self._http_client.aclose()

    @staticmethod
    async def _reject_interactive(*args: Any, **kwargs: Any) -> None:
        raise CanvaImportError(
            "OAuth interactive flow required — refresh token revoked. "
            "Run scripts/wr2_bootstrap_canva_oauth.py on Pro."
        )

    async def import_design_from_url(
        self, url: str, *, title: str
    ) -> tuple[str, str]:
        """Import a PDF URL into Canva and return (design_id, edit_url).

        Raises CanvaImportError on permanent failure (bad URL, auth error, etc.).
        Raises transient exceptions (classified by is_transient_error) on retry-able errors.
        """
        if self._session is None:
            raise RuntimeError("CanvaMcpClient not entered — use async with")
        # Canva MCP `import-design-from-url` requires {url, name, user_intent}
        # (verified empirically 2026-05-13: title→name corrected from wrong
        # arg shape after MCP -32602 invalid_type undefined for `name`).
        result = await self._session.call_tool(
            "import-design-from-url",
            arguments={
                "url": url,
                "name": title,
                "user_intent": "Import WR2 carousel PDF into Canva for editing",
            },
        )
        # mcp SDK 1.12.4+ returns CallToolResult object; normalise to dict-like shape
        if hasattr(result, "__dict__") and not isinstance(result, dict):
            result_data: Any = {"content": result.content}
        else:
            result_data = result
        design_id = parse_design_id(result_data)
        edit_url = f"https://www.canva.com/design/{design_id}/edit"
        return design_id, edit_url

    async def move_item_to_folder(self, item_id: str, folder_id: str) -> None:
        """Move a Canva item into a folder. Best-effort: logs on failure, never raises."""
        if self._session is None:
            raise RuntimeError("CanvaMcpClient not entered — use async with")
        # Canva MCP `move-item-to-folder` requires {item_id, to_folder_id,
        # user_intent} (NOT folder_id — verified 2026-05-13 same wave as
        # import-design-from-url arg-name fix).
        try:
            await self._session.call_tool(
                "move-item-to-folder",
                arguments={
                    "item_id": item_id,
                    "to_folder_id": folder_id,
                    "user_intent": "Organize WR2 rendered carousel into WR2 Drafts folder",
                },
            )
        except Exception as e:  # noqa: BLE001 — intentional best-effort
            logger.warning("move-item-to-folder failed (non-fatal): %s", e)
