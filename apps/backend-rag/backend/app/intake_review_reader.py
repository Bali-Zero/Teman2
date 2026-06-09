"""
Pro-side intake-review reader — standalone uvicorn app (Fix #1).

WHY THIS EXISTS (root cause proved 2026-06-09):
  The UI `kita.balizero.com/review` calls `GET /api/intake/review/queue`. On Fly the
  `api` process proxies `/api/intake/review*` to the `rag` process, which is wired to
  the Fly-managed Postgres — where `intake_queue=0`. But the intake worker runs on the
  *Pro* and writes proposals ONLY to the local Pro Postgres `nuzantara_dev` (89
  review_pending, 12 for adit). Producer (Pro) and consumer (Fly) read two different
  physical DBs, so the queue always showed empty.

  This module is the consumer that runs WHERE THE DATA IS: a minimal app on the Pro that
  mounts ONLY the `intake_review` router against the local `nuzantara_dev` pool, with the
  SAME `HybridAuthMiddleware` + `JWT_SECRET_KEY` so RBAC is byte-identical to Fly. The Fly
  `api` process proxies `/api/intake/review*` here over a Cloudflare Tunnel
  (see `rag_proxy.py` + `docs/runbooks/intake-review-pro-reader.md`).

LAW 2 (UU PDP): the intake queue is PII (KTP/passport/akta). It is NEVER persisted on Fly
  Postgres nor cached at Cloudflare. The reader runs on the Pro; only encrypted TLS transit
  passes through Fly/CF (accepted, same as `crm/clients`). Every response carries
  `Cache-Control: no-store, private` (P0#5) so no edge caches PII.

Run (via the LaunchAgent wrapper `scripts/intake_review_reader_run.sh`):
    uvicorn backend.app.intake_review_reader:app --host 127.0.0.1 --port 18795

Env (supplied by the 0600 env-file, NEVER in the plist — W65/P0-3 scar):
    JWT_SECRET_KEY          REQUIRED — must equal the Fly secret (validate cookie/Bearer JWT)
    API_KEYS                REQUIRED by settings — any value; this reader is JWT-only in practice
    INTAKE_REVIEW_DATABASE_URL / DATABASE_URL
                            LOCAL nuzantara_dev DSN (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
    INTAKE_REVIEW_BRIDGE_SECRET
                            shared secret; if set, an inbound `X-Bridge-Auth` header MUST match
    INTAKE_WRITER_ENABLED   forced to "0" by the wrapper — approvals stay dry-run (P2)
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("zantara.intake_review_reader")

# Loopback-only bind. cloudflared exposes it; it never listens on 0.0.0.0.
# IPv4 is explicit — the cloudflared ingress target MUST be http://127.0.0.1:18795
# (NOT localhost, which can resolve to ::1 → connection refused; Gemini P2).
READER_HOST = "127.0.0.1"
READER_PORT = 18795

# Service-to-service / spoofable headers a USER request must NOT carry inbound.
# The Cloudflare Tunnel + the Fly proxy add the trusted ones; we strip any that a
# user tries to forge so they cannot impersonate the service tier (Codex P2#2 / Gemini P1).
_INBOUND_STRIP_PREFIXES = ("cf-access-",)
_INBOUND_STRIP_EXACT = frozenset({"x-debug-key", "x-internal-key"})


def _local_dsn() -> str:
    """LOCAL Pro nuzantara_dev DSN — PII never leaves the Pro (Law 2)."""
    return (
        os.getenv("INTAKE_REVIEW_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
    )


class NoStorePIIMiddleware(BaseHTTPMiddleware):
    """P0#5 — stamp `Cache-Control: no-store, private` on every response.

    The queue carries OCR text + names (PII). Cloudflare (or any intermediary) MUST NOT
    cache it at the edge. Also strips spoofable service headers off the INBOUND request
    so a user cannot forge `CF-Access-*` / `X-Debug-Key` / `X-Internal-Key` to climb tiers.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Strip spoofable inbound headers BEFORE auth runs on them.
        scrubbed = [
            (k, v)
            for (k, v) in request.scope["headers"]
            if not (
                k.decode("latin-1").lower() in _INBOUND_STRIP_EXACT
                or k.decode("latin-1").lower().startswith(_INBOUND_STRIP_PREFIXES)
            )
        ]
        request.scope["headers"] = scrubbed

        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        return response


class BridgeAuthMiddleware(BaseHTTPMiddleware):
    """Optional second application layer: require a shared `X-Bridge-Auth` secret.

    If `INTAKE_REVIEW_BRIDGE_SECRET` is set, every non-`/healthz` request must present a
    matching `X-Bridge-Auth` header (added by the Fly proxy). This is defence-in-depth
    BEHIND Cloudflare Access (CF-Access-Client-*), not a replacement for the user JWT —
    `get_current_user` still runs on the forwarded `Authorization`/cookie so RBAC is
    unchanged. If the secret is unset, this layer is inert (tunnel-not-yet-configured).
    """

    def __init__(self, app, *, secret: str | None) -> None:
        super().__init__(app)
        self._secret = secret

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if self._secret and request.url.path != "/healthz":
            presented = request.headers.get("x-bridge-auth")
            if not presented or presented != self._secret:
                logger.warning("intake_review_reader: bridge-auth rejected for %s", request.url.path)
                return JSONResponse(status_code=401, content={"detail": "bridge auth required"})
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build a SMALL dedicated pool to the LOCAL nuzantara_dev (Codex P1#1).

    NOT the full app-factory — no scheduler / eventbus / heavy services. min1/max3 with a
    server-side statement_timeout so a runaway query can never wedge the reader.
    """
    dsn = _local_dsn()
    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=3,
        command_timeout=10.0,
        server_settings={"statement_timeout": "8000"},  # 8s hard cap, ms
    )
    app.state.db_pool = pool
    logger.info("intake_review_reader: db pool ready (min1/max3, statement_timeout=8s)")
    try:
        yield
    finally:
        await pool.close()
        app.state.db_pool = None
        logger.info("intake_review_reader: db pool closed")


def create_app() -> FastAPI:
    """Minimal reader app: HybridAuthMiddleware + intake_review router ONLY.

    Imports are deferred into the function so that importing this module (e.g. for the
    import smoke-test) does not require the full backend settings to validate at import
    time — settings is read when the app is actually constructed under the wrapper env.
    """
    # P2: approvals stay dry-run regardless of inherited env. Set BEFORE importing the
    # router/writer so the writer reads it off — explicit, not relying on a default.
    os.environ.setdefault("INTAKE_WRITER_ENABLED", "0")

    from backend.app.routers import intake_review
    from backend.middleware.hybrid_auth import HybridAuthMiddleware

    app = FastAPI(
        title="Nuzantara Intake-Review Reader (Pro)",
        description="Pro-local reader for /api/intake/review/* (Law 2 PII stays on the Pro).",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Order (Starlette wraps in reverse → first-added is outermost):
    #   1. NoStorePIIMiddleware  — strip spoofable inbound headers + no-store on the way out
    #   2. BridgeAuthMiddleware  — optional shared-secret gate (defence-in-depth)
    #   3. HybridAuthMiddleware  — the SAME cookie/Bearer JWT auth as Fly → sets request.state.user
    app.add_middleware(NoStorePIIMiddleware)
    app.add_middleware(
        BridgeAuthMiddleware,
        secret=os.getenv("INTAKE_REVIEW_BRIDGE_SECRET") or None,
    )
    app.add_middleware(HybridAuthMiddleware)

    app.include_router(intake_review.router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz(request: Request) -> JSONResponse:
        """Liveness/readiness WITHOUT exposing queue data (P2).

        Checks: (1) a db pool exists and can be acquired, (2) JWT_SECRET_KEY is configured.
        Returns 200 only if both hold, else 503. Never touches intake tables.
        """
        pool = getattr(request.app.state, "db_pool", None)
        db_ok = False
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                db_ok = True
            except Exception as exc:  # healthz must report, not raise
                logger.warning("intake_review_reader healthz db check failed: %s", exc)

        jwt_ok = bool(os.getenv("JWT_SECRET_KEY"))
        ok = db_ok and jwt_ok
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ok" if ok else "degraded", "db": db_ok, "jwt": jwt_ok},
        )

    return app


app = create_app()
