"""
RAG Proxy — forwards heavy-route requests from the api process to the rag process.

The rag process runs on Fly.io's private network at:
  rag.nuzantara-rag.internal:8080

Env vars:
  RAG_WORKER_URL: Internal URL of the rag process (default: http://rag.nuzantara-rag.internal:8080)
  RAG_PROXY_ENABLED: Set to 'false' to disable proxy (direct routing, monolith mode)
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger("zantara.backend")

# Heavy route prefixes — requests matching these are forwarded to the rag process
HEAVY_PREFIXES = (
    "/api/agent",
    "/api/agents",
    "/api/agentic-rag",
    "/api/autonomous-agents",
    "/api/autonomous-execution",
    "/api/kg-agentic",
    "/api/conversations",
    "/api/memory/lam",
    "/api/collective-memory",
    "/api/episodic-memory",
    "/api/crm/clients",
    "/api/crm/enhanced",
    "/api/crm/practices",
    "/api/ingest",
    "/api/legal-ingest",
    "/api/oracle",
    "/api/naga",
    "/api/intel",
    "/api/intel-scraper",
    "/api/intel-analytics",
    "/api/pricing",
    "/api/voice",
    "/api/whatsapp/chat",
    "/api/blog",
    "/api/dream",
    "/api/search",
    "/api/knowledge/visa",
    "/api/monitoring/rag",
    "/api/v1",
)

_proxy_client: Optional[httpx.AsyncClient] = None
_proxy_client_lock = asyncio.Lock()

_HOP_BY_HOP_RESPONSE = frozenset({
    "connection", "keep-alive", "transfer-encoding",
    "te", "trailers", "upgrade", "proxy-authenticate", "proxy-authorization",
})


def _filter_response_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_RESPONSE}


def get_rag_worker_url() -> str:
    return os.getenv("RAG_WORKER_URL", "http://rag.nuzantara-rag.internal:8080")


def is_proxy_enabled() -> bool:
    return os.getenv("RAG_PROXY_ENABLED", "true").lower() != "false"


def is_heavy_route(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in HEAVY_PREFIXES)


async def get_proxy_client() -> httpx.AsyncClient:
    global _proxy_client
    if _proxy_client is None or _proxy_client.is_closed:
        async with _proxy_client_lock:
            if _proxy_client is None or _proxy_client.is_closed:
                _proxy_client = httpx.AsyncClient(
                    base_url=get_rag_worker_url(),
                    timeout=httpx.Timeout(120.0, connect=5.0),
                    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
                )
    return _proxy_client


async def close_proxy_client() -> None:
    global _proxy_client
    if _proxy_client and not _proxy_client.is_closed:
        await _proxy_client.aclose()
        _proxy_client = None


async def proxy_request(request: Request) -> Response:
    """Forward a request to the rag process and return its response."""
    client = await get_proxy_client()

    # Build the outgoing request: same method, path, query, headers, body
    url = str(request.url.path)
    if request.url.query:
        url = f"{url}?{request.url.query}"

    # Forward all headers except hop-by-hop
    hop_by_hop = {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade", "host",
    }
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in hop_by_hop
    }
    client_host = request.client.host if request.client else "unknown"
    existing_xff = request.headers.get("x-forwarded-for")
    headers["x-forwarded-for"] = f"{existing_xff}, {client_host}" if existing_xff else client_host
    headers["x-forwarded-proto"] = "https"

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            follow_redirects=False,
        )
    except httpx.ConnectError as e:
        logger.error(f"RAG proxy connect error for {request.method} {url}: {e}")
        return Response(
            content=b'{"detail":"RAG worker unavailable"}',
            status_code=503,
            media_type="application/json",
        )
    except httpx.TimeoutException as e:
        logger.error(f"RAG proxy timeout for {request.method} {url}: {e}")
        return Response(
            content=b'{"detail":"RAG worker timeout"}',
            status_code=504,
            media_type="application/json",
        )

    # Return response — handle streaming for SSE/chunked responses
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return StreamingResponse(
            resp.aiter_bytes(),
            status_code=resp.status_code,
            headers=_filter_response_headers(resp.headers),
            media_type="text/event-stream",
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_filter_response_headers(resp.headers),
        media_type=content_type or None,
    )


def create_proxy_router() -> APIRouter:
    """
    Create a catch-all proxy router for heavy routes.
    Must be added AFTER all light routers (FastAPI matches in order).
    """
    router = APIRouter()

    @router.api_route(
        "/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def rag_proxy_endpoint(request: Request, full_path: str) -> Response:
        path = request.url.path
        if is_heavy_route(path):
            return await proxy_request(request)
        # Not a heavy route — return 404 (shouldn't happen if routing is correct)
        return Response(
            content=b'{"detail":"Not found"}',
            status_code=404,
            media_type="application/json",
        )

    return router
