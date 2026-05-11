"""KG Intelligence Tools — Bridge A: Pro MCP -> Mini mata-garuda KG.

Three tools: kg_intel_search, kg_intel_entity, kg_intel_health.
All admin-gated. Calls Mini via Tailscale (http://100.93.236.6:8990 by
default, override via MATA_GARUDA_KG_BASE_URL). Returns
{"error": "kg_unavailable", ...} on Tailscale flap (NEVER raises).

Doctrine: see apps/mata-garuda/CLAUDE.md §1.4 (Pillar 3 exception).
Spec: docs/superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md
"""
from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any, Optional

import httpx

from nuzantara_mcp.auth import require_role

logger = logging.getLogger("nuzantara-mcp.kg_intel")

KG_BASE_URL = os.getenv("MATA_GARUDA_KG_BASE_URL", "http://100.93.236.6:8990")
KG_TIMEOUT_S = float(os.getenv("MATA_GARUDA_KG_TIMEOUT_S", "3.0"))

# Test seam: tests inject httpx.MockTransport via this attribute.
_TRANSPORT_OVERRIDE: Optional[httpx.MockTransport] = None
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        kwargs: dict[str, Any] = {
            "base_url": KG_BASE_URL,
            "timeout": KG_TIMEOUT_S,
        }
        if _TRANSPORT_OVERRIDE is not None:
            kwargs["transport"] = _TRANSPORT_OVERRIDE
        _client = httpx.AsyncClient(**kwargs)
    return _client


async def _safe_get(path: str) -> dict[str, Any]:
    """GET path, return parsed JSON or graceful error dict."""
    try:
        client = _get_client()
        resp = await client.get(path)
        body: dict[str, Any]
        try:
            body = resp.json()
        except Exception:
            body = {"error": "internal_error", "detail": "non-json body"}
        if resp.status_code >= 400:
            # Surface structured error from Mini if present, else generic
            if "error" not in body:
                body = {"error": "internal_error", "detail": f"HTTP {resp.status_code}"}
            return body
        return body
    except httpx.ConnectError as exc:
        logger.warning("kg-bridge ConnectError: %s", exc)
        return {
            "error": "kg_unavailable",
            "detail": "Mata Garuda KG bridge unreachable (Tailscale flap or daemon down)",
        }
    except (httpx.TimeoutException, httpx.ReadError, httpx.RemoteProtocolError) as exc:
        logger.warning("kg-bridge transport error: %s", exc)
        return {"error": "kg_unavailable", "detail": f"transport error: {type(exc).__name__}"}
    except httpx.RequestError as exc:
        # Safety net for httpx subclasses we did not call out by name
        # (ProxyError, UnsupportedProtocol, LocalProtocolError, ...).
        # The "never raises" contract on _safe_get means every transport
        # failure must surface as kg_unavailable, not propagate.
        logger.warning("kg-bridge unexpected httpx error %s: %s", type(exc).__name__, exc)
        return {"error": "kg_unavailable", "detail": f"transport error: {type(exc).__name__}"}


def register(mcp: Any, _call: Any, _call_safe: Any) -> None:  # noqa: ARG001
    """Register kg_intel_* tools on the MCP server.

    The _call/_call_safe args from server.py are unused — this tool talks
    directly to Mini via Tailscale, not to the Fly backend.
    """

    @mcp.tool()
    @require_role("admin")
    async def kg_intel_search(query: str, limit: int = 20) -> dict[str, Any]:
        """
        Search mata-garuda KG entities by name substring.

        Returns entities whose canonical_name matches `query` case-insensitively.
        Operational metadata only — no OSINT body content.

        Args:
            query: Substring to match (case-insensitive). Empty string -> 400.
            limit: Max results (default 20, hard-capped at 100 server-side).

        Returns:
            {
              "query": str, "limit": int,
              "results": [{"name": str, "type": str, "source_count": int, "last_seen": iso8601}, ...]
            }
            Or {"error": "kg_unavailable" | "bad_request", "detail": str} on failure.

        Citation: when relaying any fact downstream, ALWAYS cite the
        observation.source_url returned by `kg_intel_entity`.
        """
        params = {"q": query, "limit": str(limit)}
        path = "/kg/search?" + urllib.parse.urlencode(params)
        return await _safe_get(path)

    @mcp.tool()
    @require_role("admin")
    async def kg_intel_entity(name: str, entity_type: str) -> dict[str, Any]:
        """
        Fetch full mata-garuda KG record for a named entity.

        Args:
            name: Canonical name (URL-decoded). Required.
            entity_type: One of {persons, organizations, locations, laws, topics}.

        Returns:
            {
              "name": str, "type": str, "source_count": int,
              "first_seen": iso8601, "last_seen": iso8601,
              "neighbor_names": [{"name": str, "type": str, "predicate": str, "confidence": float}, ...],
              "observation_count": int,
              "observations": [{"observed_at": iso8601, "source_url": str}, ...]
            }
            Or {"error": "entity_not_found" | "kg_unavailable" | "bad_request", "detail": str}.

        Citation: cite observation.source_url for every fact relayed.
        """
        encoded = urllib.parse.quote(name, safe="")
        path = f"/kg/entity/{encoded}?type={urllib.parse.quote(entity_type, safe='')}"
        return await _safe_get(path)

    @mcp.tool()
    @require_role("admin")
    async def kg_intel_health() -> dict[str, Any]:
        """
        Check mata-garuda KG bridge health.

        Returns:
            {"ok": bool, "entities_count": int, "relations_count": int,
             "observations_count": int, "schema_ok": bool, "kg_path": str}
            Or {"error": "kg_unavailable", "detail": str} if bridge unreachable.
        """
        return await _safe_get("/health")
