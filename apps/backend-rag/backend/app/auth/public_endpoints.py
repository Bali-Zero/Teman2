"""
Public endpoints registry for HybridAuthMiddleware.

Single source of truth for every route that bypasses JWT/API-key auth.
Each entry MUST carry a category and a business justification — a route
cannot be made public without a documented reason.

Matching rules:
- `match == "exact"`: request path must equal prefix
- `match == "prefix"`: `request.path.startswith(prefix)` — use for path
  families like `/api/bridge/` or `/api/portal/invite/validate/`

Adding/removing entries:
1. Edit this file only — HybridAuthMiddleware reads the registry directly.
2. The middleware-config integration test (test_public_endpoints_registry.py)
   enforces:
     - every registered path MUST resolve to a mounted FastAPI route
     - every public-looking path in the FastAPI app MUST appear here
   → so drift in either direction surfaces in CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    INFRA = "infra"
    AUTH = "auth"
    WEBHOOK = "webhook"
    OAUTH_CALLBACK = "oauth_callback"
    CLIENT_PORTAL = "client_portal"
    PUBLIC_KNOWLEDGE = "public_knowledge"
    MARKETING = "marketing"
    PREVIEW = "preview"
    FUNNEL = "funnel"
    VISA_ORACLE = "visa_oracle"
    BRIDGE = "bridge"


@dataclass(frozen=True)
class PublicEndpoint:
    prefix: str
    category: Category
    reason: str
    match: str = "prefix"  # "prefix" | "exact"

    def matches(self, path: str) -> bool:
        if self.match == "exact":
            return path == self.prefix
        return path.startswith(self.prefix)


# Exact-match roots: `/` must not swallow every path via startswith.
_ROOT_EXACT = (
    PublicEndpoint(
        "/",
        Category.INFRA,
        "Root path for simple connectivity checks",
        match="exact",
    ),
    PublicEndpoint(
        "",
        Category.INFRA,
        "Defensive: empty path equivalent to root",
        match="exact",
    ),
)

_INFRA = (
    PublicEndpoint("/health", Category.INFRA, "Load-balancer and monitoring health checks"),
    PublicEndpoint("/health/", Category.INFRA, "Alternative health check path"),
    # Removed 2026-04-18: /api/health had no mounted router (health.py mounts
    # under /health, not /api/health). Entry was stale — external probes MUST
    # use /health.
)

_AUTH = (
    PublicEndpoint(
        "/api/auth/team/login",
        Category.AUTH,
        "Team member login — must be public for initial authentication",
    ),
    PublicEndpoint(
        "/api/auth/login",
        Category.AUTH,
        "User login endpoint — must be public for initial authentication",
    ),
    PublicEndpoint(
        "/api/auth/csrf-token",
        Category.AUTH,
        "CSRF token generation — must be public for CSRF protection flow",
    ),
    PublicEndpoint(
        "/api/workflow/",
        Category.AUTH,
        "Legacy workflow entrypoint — kept public pending audit of downstream guards",
    ),
)

_WEBHOOKS = (
    PublicEndpoint(
        "/webhook/whatsapp",
        Category.WEBHOOK,
        "Meta WhatsApp webhook — verified by WHATSAPP_VERIFY_TOKEN",
    ),
    # Removed 2026-04-18: /api/whatsapp/webhook alias_router intentionally
    # disabled (manifest comment: "legacy alias causes duplicate responses").
    PublicEndpoint(
        "/webhook/instagram",
        Category.WEBHOOK,
        "Meta Instagram webhook — verified by INSTAGRAM_VERIFY_TOKEN",
    ),
    # Removed 2026-04-18: /webhook/twitter webhook_router intentionally
    # disabled (manifest: "CRC broken, OAuth incomplete").
    PublicEndpoint(
        "/webhook/telegram",
        Category.WEBHOOK,
        "Telegram bot webhook (multi-channel architecture) — the single "
        "mounted path; /api/telegram/webhook and /api/webhook/telegram "
        "aliases were removed in 2026-04-18 registry audit.",
    ),
)

_OAUTH = (
    PublicEndpoint(
        "/api/integrations/zoho/callback",
        Category.OAUTH_CALLBACK,
        "Zoho OAuth callback — required by OAuth 2.0 flow",
    ),
    PublicEndpoint(
        "/api/integrations/google-drive/callback",
        Category.OAUTH_CALLBACK,
        "Google Drive OAuth callback — required by OAuth 2.0 flow",
    ),
    PublicEndpoint(
        "/api/integrations/google-drive/system/status",
        Category.OAUTH_CALLBACK,
        "OAuth status check — REVIEW: should require auth",
    ),
    PublicEndpoint(
        "/api/admin/drive/health",
        Category.OAUTH_CALLBACK,
        "Drive health check — public status for diagnostics",
    ),
    PublicEndpoint(
        "/admin/google-drive/callback-system",
        Category.OAUTH_CALLBACK,
        "Admin OAuth callback (public per OAuth 2.0 spec)",
    ),
    PublicEndpoint(
        "/admin/zoho/callback",
        Category.OAUTH_CALLBACK,
        "Admin Zoho OAuth callback (public per OAuth 2.0 spec)",
    ),
)

_CLIENT_PORTAL = (
    PublicEndpoint(
        "/api/portal/invite/validate/",
        Category.CLIENT_PORTAL,
        "Client invitation validation — token-based security",
    ),
    PublicEndpoint(
        "/api/portal/invite/complete",
        Category.CLIENT_PORTAL,
        "Client registration completion — token-based security",
    ),
    PublicEndpoint(
        "/api/hr/late-reply/",
        Category.CLIENT_PORTAL,
        "HR late check-in reply form — per-incident token-based security "
        "(secrets.compare_digest), GET form + POST submit, no PII collected. "
        "Token IS the auth.",
    ),
)

_PUBLIC_KNOWLEDGE = (
    PublicEndpoint(
        "/api/knowledge/visa",
        Category.PUBLIC_KNOWLEDGE,
        "Public visa types knowledge base — informational content for website visitors",
    ),
    PublicEndpoint(
        "/api/oracle/health",
        Category.PUBLIC_KNOWLEDGE,
        "Oracle health check — public status endpoint",
    ),
    PublicEndpoint(
        "/api/agent/health",
        Category.PUBLIC_KNOWLEDGE,
        "LangGraph agent layer health check — public monitoring endpoint",
    ),
    PublicEndpoint(
        "/api/channels/health-public",
        Category.PUBLIC_KNOWLEDGE,
        "Innervation Genoma channel liveness — Cell aggregator polls this "
        "endpoint via the http bridge_source type. Returns ONLY per-channel "
        "{status: up|degraded|down}, no DLQ/metrics/PII (defense-in-depth: "
        "the route handler itself is also no-auth; this entry exists so the "
        "hybrid_auth middleware lets the request through to the handler).",
        match="exact",
    ),
    PublicEndpoint(
        "/api/cell/metrics",
        Category.PUBLIC_KNOWLEDGE,
        "CELL ErrorRateSensor reads this internally — no user data exposed",
    ),
    PublicEndpoint(
        "/api/v1/kbli-notebook/",
        Category.PUBLIC_KNOWLEDGE,
        "KBLI Explorer — public business classification search, inspect, and chat",
    ),
    # Removed 2026-04-18: /api/webhook/chat and /api/webhook/chat/history —
    # no router implements these paths (grep 'webhook/chat' returned 0 hits).
    # Stale entries from a removed chat-webhook prototype.
)

_MARKETING = (
    PublicEndpoint(
        "/api/news",
        Category.MARKETING,
        "Public news/intel feed — approved articles for balizero.com homepage and blog",
    ),
    PublicEndpoint(
        "/api/blog/",
        Category.MARKETING,
        "Public blog articles and content",
    ),
    # Removed 2026-04-18: /api/vitals — no router implements this path.
    # Stale entry from a removed web-vitals prototype. If frontend performance
    # telemetry is re-introduced, add it under whatever real path lands.
    PublicEndpoint(
        "/api/blog/newsletter/subscribe",
        Category.MARKETING,
        "Newsletter subscription — public marketing endpoint",
    ),
    PublicEndpoint(
        "/api/blog/newsletter/confirm",
        Category.MARKETING,
        "Newsletter confirmation — token-based verification",
    ),
    PublicEndpoint(
        "/api/blog/newsletter/unsubscribe",
        Category.MARKETING,
        "Newsletter unsubscribe — token-based verification (legal requirement)",
    ),
    PublicEndpoint(
        "/api/blog/ask",
        Category.MARKETING,
        "AskZantara widget on blog articles — public Q&A feature",
    ),
)

_PREVIEW = (
    PublicEndpoint(
        "/preview/",
        Category.PREVIEW,
        "Article preview pages for Telegram approval — no indexing, public preview",
    ),
    PublicEndpoint(
        "/api/dashboard/map/",
        Category.PREVIEW,
        "Streamlit dashboard — KBLI validation, client geo, risk zones, stats",
    ),
)

_FUNNEL = (
    PublicEndpoint(
        "/api/funnel/session/touch",
        Category.FUNNEL,
        "Pre-auth lead cookie bz_session touch — anonymous UUID, no PII. "
        "Required for cross-funnel session attribution.",
    ),
    PublicEndpoint(
        "/api/funnel/session/convert",
        Category.FUNNEL,
        "Lead→client conversion bridge called by portal login flow. "
        "Takes session_id + client_id.",
    ),
    PublicEndpoint(
        "/api/analytics/funnel-event",
        Category.FUNNEL,
        "11 whitelisted funnel events (see packages/core/analytics/funnel-view.ts). "
        "No PII — session_id only.",
    ),
    PublicEndpoint(
        "/api/prime/zoning",
        Category.FUNNEL,
        "Prime Intelligence geospatial zoning API — public map intelligence layer",
    ),
    PublicEndpoint(
        "/api/prime/zones-geojson",
        Category.FUNNEL,
        "Zone polygon GeoJSON for 3D map rendering (public)",
    ),
    PublicEndpoint(
        "/api/prime/v2/resolve",
        Category.FUNNEL,
        "PRIME NEXUS: Layer 1 spatial resolution (public zone data)",
    ),
    PublicEndpoint(
        "/api/prime/v2/analyze",
        Category.FUNNEL,
        "PRIME NEXUS: Layer 2 investment analysis (public, rate-limited)",
    ),
    PublicEndpoint(
        "/api/prime/v2/density",
        Category.FUNNEL,
        "PRIME NEXUS: Competitor density per zone (public)",
    ),
    PublicEndpoint(
        "/api/prime/v2/predict",
        Category.FUNNEL,
        "PRIME NEXUS: Zone trend prediction (public)",
    ),
    PublicEndpoint(
        "/api/prime/v2/temporal",
        Category.FUNNEL,
        "PRIME NEXUS: Temporal activity (public — zone-level only)",
    ),
    PublicEndpoint(
        "/api/prime/v2/regulations",
        Category.FUNNEL,
        "PRIME NEXUS: Regulation feed per zone (public)",
    ),
    PublicEndpoint(
        "/api/prime/v2/proposal/",
        Category.FUNNEL,
        "PRIME NEXUS: Public proposal view (token-based)",
    ),
    PublicEndpoint(
        "/api/prime/v2/health",
        Category.FUNNEL,
        "PRIME NEXUS: Health check",
    ),
)

_VISA_ORACLE = (
    PublicEndpoint(
        "/api/v1/visa-oracle/recommend",
        Category.VISA_ORACLE,
        "Anonymous visa quiz recommendations — no user data, pure scoring logic",
    ),
    PublicEndpoint(
        "/api/v1/visa-oracle/chat",
        Category.VISA_ORACLE,
        "Anonymous visa Q&A chat — rate-limited by IP hash, no PII collected",
    ),
    PublicEndpoint(
        "/api/v1/visa-oracle/handoff",
        Category.VISA_ORACLE,
        "WhatsApp/Telegram handoff — builds deep-link URL + team notification",
    ),
    PublicEndpoint(
        "/api/v1/visa-oracle/visa-types",
        Category.VISA_ORACLE,
        "Visa types catalog — used by Next.js SSG at build time",
    ),
)

_BRIDGE = (
    PublicEndpoint(
        "/api/bridge/",
        Category.BRIDGE,
        "Pro<->Fly bidirectional bridge (Phase 1 Sinapsi). "
        "Bypass is intentional: router uses X-Bridge-Auth with hmac.compare_digest "
        "against BRIDGE_API_KEY and rejects unauthorized requests with 401/503.",
    ),
)


PUBLIC_ENDPOINTS: tuple[PublicEndpoint, ...] = (
    *_ROOT_EXACT,
    *_INFRA,
    *_AUTH,
    *_WEBHOOKS,
    *_OAUTH,
    *_CLIENT_PORTAL,
    *_PUBLIC_KNOWLEDGE,
    *_MARKETING,
    *_PREVIEW,
    *_FUNNEL,
    *_VISA_ORACLE,
    *_BRIDGE,
)


def is_public_path(path: str) -> bool:
    """Return True if `path` matches any registered public endpoint."""
    for ep in PUBLIC_ENDPOINTS:
        if ep.matches(path):
            return True
    return False


def find_entry(path: str) -> PublicEndpoint | None:
    """Return the registry entry that matches `path`, or None."""
    for ep in PUBLIC_ENDPOINTS:
        if ep.matches(path):
            return ep
    return None
