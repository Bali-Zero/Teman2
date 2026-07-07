"""
RAG Proxy — forwards heavy-route requests from the api process to the rag process.

The rag process runs on Fly.io's private network at:
  rag.nuzantara-rag.internal:8080

Env vars:
  RAG_WORKER_URL: Internal URL of the rag process (default: http://rag.nuzantara-rag.internal:8080)
  RAG_PROXY_ENABLED: Set to 'false' to disable proxy (direct routing, monolith mode)

Intake-review split (Fix #1, Law 2):
  INTAKE_REVIEW_WORKER_URL: Cloudflare-Tunnel URL of the Pro-side intake-review reader.
    When set, requests under the EXACT prefix `/api/intake/review` (and `/api/intake/review/...`)
    are routed HERE instead of the rag process — because the intake queue (PII) lives ONLY on
    the Pro's local Postgres. When UNSET/empty, this is inert: `/api/intake/review*` falls back
    to RAG_WORKER_URL (current behaviour), so this change is safe to ship before cloudflared exists.
  CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET: Cloudflare Access Service-Token headers added
    to the OUTBOUND request to the intake target so Cloudflare Access lets the Fly→Pro hop through.
"""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger("zantara.backend")

# Heavy route prefixes — requests matching these are forwarded to the rag process
HEAVY_PREFIXES = (
    "/api/agent",
    "/api/agents",
    "/api/agentic-rag",
    "/api/autonomous-agents",
    "/api/bali-zero/conversations",
    "/api/memory/lam",
    "/api/collective-memory",
    "/api/episodic-memory",
    "/api/crm/clients",
    "/api/crm/companies",
    "/api/crm/practices",
    # Pro-local HITL doc-review queue (Law 2 PII) — proxy to RAG like /api/crm/*
    "/api/intake/review",
    "/api/dashboard",
    "/api/ingest",
    "/api/intel",
    "/api/legal",
    "/api/oracle",
    "/api/naga",
    "/api/kg",
    "/api/monitoring",
    "/api/news",
    "/api/pricing",
    "/api/voice",
    "/api/blog",
    "/api/dream",
    "/api/search",
    "/api/knowledge/visa",
    "/api/v1",
    # NOTE: /webhook/whatsapp stays on api process (Meta sends webhooks to public HTTP service)
)

# Intake-review boundary (Fix #1). EXACT match so a future /api/intake/review-metrics
# does NOT get hijacked to the Pro tunnel (Codex P0#3). /api/intake/gate is NOT in
# HEAVY_PREFIXES at all → it stays on the api process.
_INTAKE_REVIEW_PREFIX = "/api/intake/review"

_proxy_client: httpx.AsyncClient | None = None
_proxy_client_lock = asyncio.Lock()

# Dedicated, persistent client for the intake-review target (Codex P0#2 — do NOT reuse the
# RAG-base_url client). Created lazily under the same lock; closed in close_proxy_client().
_intake_client: httpx.AsyncClient | None = None

_HOP_BY_HOP_RESPONSE = frozenset(
    {
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailers",
        "upgrade",
        "proxy-authenticate",
        "proxy-authorization",
        "content-length",  # Let Starlette recalculate — middleware may modify body
        "content-encoding",  # httpx auto-decompresses; forwarding gzip header with plain body breaks clients
    }
)


def _filter_response_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_RESPONSE}


def get_rag_worker_url() -> str:
    return os.getenv("RAG_WORKER_URL", "http://rag.nuzantara-rag.internal:8080")


def get_intake_review_worker_url() -> str | None:
    """Cloudflare-Tunnel URL of the Pro intake-review reader, or None if not configured.

    Empty/whitespace is treated as unset so an empty Fly secret falls back to RAG cleanly.
    """
    url = os.getenv("INTAKE_REVIEW_WORKER_URL", "").strip()
    return url or None


def is_proxy_enabled() -> bool:
    return os.getenv("RAG_PROXY_ENABLED", "true").lower() != "false"


def is_heavy_route(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in HEAVY_PREFIXES)


def is_intake_review_route(path: str) -> bool:
    """True only for the EXACT /api/intake/review boundary (Codex P0#3).

    Matches `/api/intake/review` and `/api/intake/review/<anything>` but NOT
    `/api/intake/review-metrics` or other siblings.
    """
    return path == _INTAKE_REVIEW_PREFIX or path.startswith(_INTAKE_REVIEW_PREFIX + "/")


async def get_proxy_client() -> httpx.AsyncClient:
    global _proxy_client
    if _proxy_client is None or _proxy_client.is_closed:
        async with _proxy_client_lock:
            if _proxy_client is None or _proxy_client.is_closed:
                _proxy_client = httpx.AsyncClient(
                    base_url=get_rag_worker_url(),
                    timeout=httpx.Timeout(
                        300.0, connect=10.0
                    ),  # 5min for agentic RAG with tool calls
                    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
                )
    return _proxy_client


async def get_intake_client() -> httpx.AsyncClient:
    """Persistent client for the intake-review target (Golden Rule #10 — never per-request).

    Timeouts (connect=3, read=30): a SHORT connect (3s) still fail-fasts when the Pro is
    offline — an unreachable tunnel fails at connect, so a Pro outage can't exhaust the Fly
    worker pool and take down the WHOLE api (Gemini P0 / Codex P1#3). But the READ budget must
    cover the full round-trip over the Cloudflare Tunnel on the Pro's mobile/hotspot uplink:
    the detail/blob endpoints (which load the document blob + candidate clients) routinely take
    >5s end-to-end, so a 5s read budget mapped EVERY detail open to a spurious 503 "reader
    offline" while /queue (a fast PG read) stayed 200. 30s read covers the slow link without
    re-opening the worker-pool-exhaustion risk (connect, not read, is the offline guard).
    Bounded base_url to the tunnel host.
    """
    global _intake_client
    if _intake_client is None or _intake_client.is_closed:
        async with _proxy_client_lock:
            if _intake_client is None or _intake_client.is_closed:
                base = get_intake_review_worker_url()
                _intake_client = httpx.AsyncClient(
                    base_url=base or "",
                    timeout=httpx.Timeout(30.0, connect=3.0),
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                )
    return _intake_client


async def close_proxy_client() -> None:
    global _proxy_client, _intake_client
    if _proxy_client and not _proxy_client.is_closed:
        await _proxy_client.aclose()
        _proxy_client = None
    if _intake_client and not _intake_client.is_closed:
        await _intake_client.aclose()
        _intake_client = None


def _build_forward_headers(request: Request) -> dict:
    """Strip hop-by-hop headers and append X-Forwarded-* — shared by both targets."""
    hop_by_hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
    headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}
    client_host = request.client.host if request.client else "unknown"
    existing_xff = request.headers.get("x-forwarded-for")
    headers["x-forwarded-for"] = f"{existing_xff}, {client_host}" if existing_xff else client_host
    headers["x-forwarded-proto"] = "https"
    return headers


async def proxy_intake_review_request(request: Request) -> Response:
    """Forward an /api/intake/review* request to the Pro reader via Cloudflare Tunnel.

    Maps EVERY failure (connect refused, read timeout, any 5xx from CF/tunnel, unexpected
    error) to an explicit 503 JSONResponse — NEVER forwards the raw upstream error and NEVER
    hangs on the 300s RAG timeout (Codex P0#4 / Gemini P0 / DeepSeek). This keeps a Pro
    outage scoped to /review instead of DoS-ing the whole API.
    """
    base = get_intake_review_worker_url()
    if not base:
        # Inert until the tunnel is configured — fall back to the RAG path.
        return await proxy_request(request)

    client = await get_intake_client()

    url = str(request.url.path)
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = _build_forward_headers(request)

    # Cloudflare Access Service-Token headers so the Fly→Pro hop passes CF Access.
    # User Cookie/Authorization is already forwarded by _build_forward_headers, so the
    # Pro reader's get_current_user is unchanged → RBAC identical.
    cf_id = os.getenv("CF_ACCESS_CLIENT_ID", "").strip()
    cf_secret = os.getenv("CF_ACCESS_CLIENT_SECRET", "").strip()
    if cf_id and cf_secret:
        headers["CF-Access-Client-Id"] = cf_id
        headers["CF-Access-Client-Secret"] = cf_secret

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            follow_redirects=True,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        logger.error(f"intake-review proxy connect error for {request.method} {url}: {e}")
        return JSONResponse(status_code=503, content={"detail": "intake review reader offline"})
    except httpx.TimeoutException as e:
        logger.error(f"intake-review proxy timeout for {request.method} {url}: {e}")
        return JSONResponse(status_code=503, content={"detail": "intake review reader offline"})
    except httpx.HTTPError as e:
        logger.error(f"intake-review proxy transport error for {request.method} {url}: {e}")
        return JSONResponse(status_code=503, content={"detail": "intake review reader offline"})

    # Map a Cloudflare/tunnel-level 5xx (502/503/504 from the edge, not the app) to our 503
    # so the UI sees a consistent "reader offline" instead of a raw CF error page.
    if resp.status_code in (502, 503, 504):
        logger.error(
            f"intake-review proxy upstream {resp.status_code} for {request.method} {url} — treating as offline"
        )
        return JSONResponse(status_code=503, content={"detail": "intake review reader offline"})

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_filter_response_headers(resp.headers),
        media_type=resp.headers.get("content-type") or None,
    )


async def proxy_request(request: Request) -> Response:
    """Forward a request to the rag process and return its response."""
    client = await get_proxy_client()

    # Build the outgoing request: same method, path, query, headers, body
    url = str(request.url.path)
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = _build_forward_headers(request)

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            follow_redirects=True,
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
    async def rag_proxy_endpoint(request: Request, full_path: str = "") -> Response:
        _ = full_path  # Required by FastAPI's catch-all path converter.
        path = request.url.path
        # Intake-review (PII, Law 2) → Pro reader via Cloudflare Tunnel when configured.
        # Checked BEFORE the generic heavy-route path so the exact boundary wins.
        if is_intake_review_route(path) and get_intake_review_worker_url():
            return await proxy_intake_review_request(request)
        if is_heavy_route(path):
            return await proxy_request(request)
        # Not a heavy route — return 404 (shouldn't happen if routing is correct)
        return Response(
            content=b'{"detail":"Not found"}',
            status_code=404,
            media_type="application/json",
        )

    return router
