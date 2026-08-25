"""
Public endpoints registry for HybridAuthMiddleware.

Single source of truth for every route that bypasses JWT/API-key auth.
Each entry MUST carry a category and a business justification — a route
cannot be made public without a documented reason.

Matching rules:
- `match == "exact"`: request path must equal prefix
- `match == "prefix"`: `request.path.startswith(prefix)` — use for path
  families like `/api/bridge/` or `/api/portal/invite/validate/`
- `match == "template"`: FastAPI-style path params match one path segment,
  e.g. `/api/items/{item_id}/upload` matches `/api/items/123/upload` only.

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
        if self.match == "template":
            prefix_parts = self.prefix.strip("/").split("/")
            path_parts = path.strip("/").split("/")
            if len(prefix_parts) != len(path_parts):
                return False
            return all(
                bool(actual)
                if expected.startswith("{") and expected.endswith("}")
                else actual == expected
                for expected, actual in zip(prefix_parts, path_parts, strict=True)
            )
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
    # Sprint 1.B 2026-05-02: per-channel health endpoint for Cell-side
    # heartbeat bridge. Cell on Pro polls these to write
    # ~/.organism/last_seen/channel.{name}.json sidecars.
    # Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
    PublicEndpoint(
        "/api/channels/whatsapp/health",
        Category.INFRA,
        "Channel health (whatsapp) — Cell heartbeat bridge poll target",
        match="exact",
    ),
    PublicEndpoint(
        "/api/channels/telegram/health",
        Category.INFRA,
        "Channel health (telegram) — Cell heartbeat bridge poll target",
        match="exact",
    ),
    PublicEndpoint(
        "/api/channels/instagram/health",
        Category.INFRA,
        "Channel health (instagram) — Cell heartbeat bridge poll target",
        match="exact",
    ),
    PublicEndpoint(
        "/api/channels/web/health",
        Category.INFRA,
        "Channel health (web) — Cell heartbeat bridge poll target",
        match="exact",
    ),
    PublicEndpoint(
        "/api/metrics/frontend",
        Category.INFRA,
        "Best-effort frontend browser metrics ingestion - no PII, no auth header",
        match="exact",
    ),
    # P1.2 asset upload proxy (2026-05-26): /api/assets/upload is auth-protected
    # via X-Asset-Upload-Token header (env ASSET_UPLOAD_TOKEN); only /health is
    # public for liveness probe of the asset upload service (Tigris config check).
    PublicEndpoint(
        "/api/assets/health",
        Category.INFRA,
        "Asset upload service health probe (Tigris config check, no creds exposed)",
        match="exact",
    ),
    # Intel Lake Wave 1 (2026-05-12, mig 168): unified intel pipeline ingest
    # endpoint. Public to bypass HybridAuthMiddleware — but enforces its own
    # X-Producer-Token header auth in the router (env INTEL_LAKE_PRODUCER_TOKEN).
    # See backend/app/routers/intel_lake.py and research/symbiosis/2026-05-12-intel-lake-design.md
    PublicEndpoint(
        "/api/intel/lake/observations",
        Category.INFRA,
        "Intel Lake observation ingest — X-Producer-Token auth in-router",
        match="exact",
    ),
    PublicEndpoint(
        "/api/intel/lake/observations-batch",
        Category.INFRA,
        "Intel Lake batched observation ingest — X-Producer-Token auth in-router",
        match="exact",
    ),
    # wa-mirror CRM write-back (2026-06-06): service-side lead promotion +
    # strategic_recap from the Pro-local wa-corpus to the Fly CRM. Public to bypass
    # HybridAuthMiddleware — but enforces its OWN X-CRM-Write-Key header auth +
    # WA_MIRROR_CRM_WRITE_ENABLED flag in-router (verify_crm_write_key). Uses a
    # DISTINCT scoped key from wa_mirror_internal_key (least-privilege — this key
    # authorizes ONLY phone-keyed lead upsert). See
    # backend/app/routers/crm_clients.py::upsert_client_by_phone.
    PublicEndpoint(
        "/api/crm/clients/upsert-by-phone",
        Category.INFRA,
        "wa-mirror CRM lead upsert — X-CRM-Write-Key + WA_MIRROR_CRM_WRITE_ENABLED auth in-router",
        match="exact",
    ),
    PublicEndpoint(
        "/api/crm/internal/clients/{client_id}/documents/upload",
        Category.INFRA,
        "wa-mirror intake document upload — X-CRM-Write-Key + WA_MIRROR_CRM_WRITE_ENABLED auth in-router",
        match="template",
    ),
    # BOT-V4 S2 broker transport (Codex re-verdict, finding 1): the Pro
    # broker daemon authenticates with the DEDICATED WA_BROKER_KEY via
    # require_wa_broker_key (constant-time, fail-closed when unconfigured,
    # rate-limited on failures). That key is NOT in the general API-key
    # list, so without these entries HybridAuthMiddleware read the
    # X-API-Key header, rejected the unknown key, and the documented
    # single-credential contract 401'd before the route's own gate ever
    # ran — the service only worked with two undocumented credentials.
    PublicEndpoint(
        "/api/wa-broker/claim",
        Category.INFRA,
        "codex broker claim — dedicated WA_BROKER_KEY auth in-router (require_wa_broker_key)",
        match="exact",
    ),
    PublicEndpoint(
        "/api/wa-broker/complete",
        Category.INFRA,
        "codex broker complete — dedicated WA_BROKER_KEY auth in-router (require_wa_broker_key)",
        match="exact",
    ),
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
        "/api/auth/request-magic-link",
        Category.AUTH,
        "Passwordless magic-link request (FASE 6) — must be public; an "
        "unauthenticated client asks for a sign-in link. Enumeration-safe.",
        match="exact",
    ),
    PublicEndpoint(
        "/api/auth/verify-magic/",
        Category.AUTH,
        "Passwordless magic-link verify (FASE 6) — must be public; consumes the "
        "single-use token and establishes the session. Prefix match: the token "
        "is a path param.",
    ),
    # 2026-05-28: removed "/api/workflow/" prefix entry. All workflow_queue routes
    # (/enqueue, /status/{job_id}, /chains) require Depends(get_current_user), so the
    # public declaration was dead+contradictory (middleware bypassed auth, route 401'd).
    # The "downstream guards audit" the old comment awaited is now done — guards exist.
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
    # Removed 2026-08-18 (Zero ruled REMOVE): /webhook/telegram and
    # telegram_webhook.py itself deleted — the route was structurally dead by
    # design (the `api` process it was mounted on always had
    # app.state.channel_router = None, so Depends(get_channel_router) 503'd
    # on every request; the live Telegram channel is Pro OpenClaw, per
    # CLAUDE.md §12). See .claude/skills/modus/PENDING-ARMS.md (closed lines).
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
        "/api/pricing/service",
        Category.PUBLIC_KNOWLEDGE,
        "Single-service price lookup by exact catalogue key. The public website "
        "must render prices from PricingTool rather than hardcoded literals "
        "(Golden Rule #11), and its visitors are anonymous — without this entry "
        "every client-facing price stays a hand-maintained copy that drifts from "
        "the SSOT. EXACT match on purpose: /api/pricing/all, /search and "
        "/scenario stay authenticated. The response carries catalogue rows only "
        "(key, name, price, category, validity, notes) — the same figures already "
        "published on balizero.com, no client or CRM data.",
        match="exact",
    ),
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
    # REMOVED 2026-08-12 (P0, measured live): "/api/dashboard/map/" was a PREFIX
    # entry, so every route the dashboard router ever mounts inherited public
    # access — including `GET /api/dashboard/map/clients/geo`, which ran
    # `SELECT id, full_name, email, phone, status, address FROM clients WHERE
    # status='active' LIMIT 500` with no principal and no ownership filter. An
    # anonymous request from the public internet answered HTTP 200 with 500
    # client rows (500 names, 274 phones, 164 emails, 110 addresses).
    #
    # The blanket prefix IS the defect, not just the one route: it also left
    # `POST /api/dashboard/map/analytics/log-lookup` writable anonymously with a
    # caller-supplied `user_email`, i.e. forgeable attribution. A router that can
    # reach the `clients` table must never sit behind a prefix entry — if a
    # specific route here genuinely needs to be public, add THAT path, never the
    # prefix, and never one that shares a router with client data.
    #
    # The three entries below are NOT new public access: they restore, per-route,
    # the posture the 2026-07-17 mutating-routes audit had already justified one
    # by one (`research/operations/2026-07-17-mutating-routes-authz-ledger.md`
    # lines 233-235, category `preview`). That audit read THIS router and cleared
    # these three as stateless compute — and never named `GET /clients/geo`,
    # because its scope was mutating methods only. The client book was invisible
    # to an audit that read the file it lives in: the scope was the METHOD, not
    # the DATA. Hence per-route entries — the granularity the audit's own
    # verdicts were written at, which the prefix silently over-delivered.
    PublicEndpoint(
        "/api/dashboard/map/validate-property",
        Category.PREVIEW,
        "Stateless KBLI/zoning compute for the property map — no DB read or "
        "write, no PII in or out (cleared per-route by the 2026-07-17 audit)",
        match="exact",
    ),
    PublicEndpoint(
        "/api/dashboard/map/gistaru-zone",
        Category.PREVIEW,
        "Stateless geo/zone lookup for the property map — no DB read or write "
        "(cleared per-route by the 2026-07-17 audit)",
        match="exact",
    ),
    PublicEndpoint(
        "/api/dashboard/map/analyze-investment",
        Category.PREVIEW,
        "Stateless investment compute — verified no DB write (cleared per-route "
        "by the 2026-07-17 audit). Its KBLI block degrades to state=ERROR in "
        "prod because the dataset is not in the image (kbli-navigator L2.11b)",
        match="exact",
    ),
    # `POST /api/dashboard/map/analytics/log-lookup` is DELIBERATELY absent: it
    # is the one route here that WRITES (CREATE TABLE IF NOT EXISTS + INSERT),
    # and it attributed each row to a `user_email` taken from the request body,
    # so anonymous access meant an unauthenticated writer could file lookups
    # under any employee's name. The 2026-07-17 audit cleared it as "telemetry
    # insert only, same shape as /api/metrics/frontend" — but that endpoint
    # carries no PII, and an email IS an identifier, so the shapes were never
    # the same. It now takes the acting email from the authenticated principal.
    # Measured before closing it (prod, 2026-08-12): 5 rows, 1 distinct email,
    # all written 2026-03-02 and none since — no live consumer to break.
)

_FUNNEL = (
    PublicEndpoint(
        "/api/lead/capture",
        Category.FUNNEL,
        "Anonymous WhatsApp handoff CTA (articles, KBLI Navigator, 4-apps). "
        "Writes lead_intents (source/context/utm/fingerprint only — no PII); "
        "payload capped at 8KB by the router. POST-only, exact path.",
        match="exact",
    ),
    PublicEndpoint(
        "/api/funnel/session/touch",
        Category.FUNNEL,
        "Pre-auth lead cookie bz_session touch — anonymous UUID, no PII. "
        "Required for cross-funnel session attribution.",
    ),
    PublicEndpoint(
        "/api/funnel/session/convert",
        Category.FUNNEL,
        "Lead→client conversion bridge called by portal login flow. Takes session_id + client_id.",
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
    # Visa Oracle v2 evaluate read-path (W1, routers/visa_oracle_evaluate.py).
    # Anonymous by design: the v2 interview runs pre-account. Canonical
    # ApplicantFacts in, mode=CURATED envelope out (SHADOW era), one full-fact
    # SHADOW visa_decisions audit row per call. Dedicated 30/min rate-limit
    # bucket, 32KB body cap, content-type enforcement, HMAC-fingerprint-only
    # logs, synthetic traffic_source classes gated by a server-side allowlist
    # env. Exact match only — the path is a single fixed POST.
    PublicEndpoint(
        "/api/visa-oracle/evaluate",
        Category.VISA_ORACLE,
        "Visa Oracle v2 evaluate read-path — anonymous canonical-facts evaluation, "
        "rate-limited 30/min, no PII persisted or logged (HMAC fingerprints only)",
        match="exact",
    ),
    # Visa Check v1 homepage funnel (routers/visa_check.py, mounted at /api/visa).
    # Anonymous, no PII (nationality/purpose/budget only), rate-limited per-IP
    # by RateLimitMiddleware via the "/api/" bucket (120 req/min). The hash IS
    # the access token for result pages. Registered 2026-07-23: the funnel was
    # dead in prod since 2026-04-25 (PR #108) because these routes were never
    # declared public — HybridAuth returned 401 to every anonymous call.
    # Exact/template matches only — no blanket "/api/visa/" prefix.
    PublicEndpoint(
        "/api/visa/check/start",
        Category.VISA_ORACLE,
        "Visa Check funnel branch selector — anonymous yes/no routing, no data persisted",
        match="exact",
    ),
    PublicEndpoint(
        "/api/visa/clock",
        Category.VISA_ORACLE,
        "Visa Check Clock submission — anonymous overstay-timeline wizard, no PII",
        match="exact",
    ),
    PublicEndpoint(
        "/api/visa/match",
        Category.VISA_ORACLE,
        "Visa Check Match submission — anonymous visa recommendation, no PII",
        match="exact",
    ),
    PublicEndpoint(
        "/api/visa/clock/{hash}",
        Category.VISA_ORACLE,
        "Visa Check Clock result page — shareable URL, the hash is the access token",
        match="template",
    ),
    PublicEndpoint(
        "/api/visa/match/{hash}",
        Category.VISA_ORACLE,
        "Visa Check Match result page — shareable URL, the hash is the access token",
        match="template",
    ),
    # GARUDA VOA magic-link auth (L4, routers/garuda_portal_auth.py, prefix
    # /api/visa/voa/auth — a disjoint sub-path of L2/L3's shared /api/visa/voa,
    # never a blanket prefix on that shared root). Anonymous by design: an
    # eligibility-check result owner has no account until this flow mints
    # one — see magic_link.py module docstring. Same defect class as the
    # "Visa Check funnel dead in prod" note above, caught here the same way:
    # a real end-to-end request through `main_api.app` (not a bare FastAPI()
    # + include_router() test double) returned 401 before this entry existed.
    # DISCOVERED, NOT FIXED HERE: `/api/visa/voa` itself (L2's
    # garuda_voa_public.py + L3's garuda_orders_router.py, both already
    # merged) has the SAME gap — no registry entry, so their public routes
    # 401 in production today too. Out of scope for this PR (cross-lane
    # files, and garuda_orders_router.py also mounts a staff-only
    # /api/visa/voa/staff/... route that a careless blanket prefix here
    # would need to carve out correctly) — flagged for the orchestrator.
    PublicEndpoint(
        "/api/visa/voa/auth/",
        Category.AUTH,
        "GARUDA VOA magic-link issue+exchange — anonymous by design, contract-frozen "
        "(products/garuda-voa/contracts/openapi.yaml), GARUDA_PUBLIC_ENABLED re-checked "
        "per-request by the handler itself",
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
