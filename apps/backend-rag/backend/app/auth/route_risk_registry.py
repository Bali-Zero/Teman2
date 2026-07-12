"""Route risk registry — declared authorization level per mutating route.

Case OS Fase-1 authorization unification. Companion to ``public_endpoints.py``:
that file says "who can reach this WITHOUT auth"; this file says "what ROLE a
mutating route needs".

WHY THIS EXISTS
---------------
A prior audit (2026-07-12) found that of 346 mutating routes (POST/PUT/PATCH/
DELETE), ~65 had NO auth ``Depends`` resolver AND no in-body verifier call — they
were reachable by ANY authenticated team member, with zero role distinction. The
global ``hybrid_auth`` JWT middleware authenticates them team-wide, but nothing
distinguishes an intern from an admin on a "publish to the public site" or "run an
autonomous agent" call.

Gating them one-by-one is not the cure (a new nude route reintroduces the hole the
next day). The cure is a DECLARED convention enforced in CI: every mutating route
must resolve to one of — (a) an auth ``Depends``, (b) an in-body verifier call,
(c) membership in ``PUBLIC_ENDPOINTS``, or (d) an explicit entry here. A new
mutating route with none of those FAILS the build
(``test_route_authz_coverage.py``).

WHAT AN ENTRY DOES *NOT* DO (read this — it is not security theater by accident)
--------------------------------------------------------------------------------
An entry here is a *declaration + backlog item*, not runtime enforcement on its
own. It records the assessed risk level, whether it is safe to gate today without
breaking a live caller (``gating_safe``), and an owner. Runtime enforcement is a
SEPARATE, progressive step (shadow-log first, then block) tracked in the modus
PENDING-ARMS ledger — deliberately NOT flipped on here, because 24 of these routes
have live internal callers (MCP tools, cron, the M5 WR2 app, service-to-service
API-key flows) that would 401 the instant a naive gate went live. The registry is
what makes that progressive gating *safe and auditable* instead of a prod-breaking
big-bang.

To retire an entry: add the real ``Depends`` auth to the route (the gate then sees
(a) and the registry line becomes redundant — delete it). The 65 → 0 trajectory is
"replace declaration with real gate", never "add another R-label to stay green".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    """Assessed authorization level a mutating route requires."""

    R1_TEAM = "R1_TEAM"        # any authenticated team member (own-scope / low blast radius)
    R2_ELEVATED = "R2_ELEVATED"  # writes team-shared data (sheets, sessions, CRM, staging edits)
    R3_ADMIN = "R3_ADMIN"      # public-facing / destructive / autonomous / ingest-to-KB / spends money


@dataclass(frozen=True)
class RouteRisk:
    """A declared risk level for one mutating route.

    ``gating_safe`` = True means adding an auth ``Depends`` today would NOT 401 any
    known live caller (verified by adversarial audit 2026-07-12). False means a real
    internal caller (cron/MCP/M5-app/service) hits it without the credential a gate
    would demand — gate it only after that caller is migrated.
    """

    path: str
    methods: tuple[str, ...]
    level: RiskLevel
    gating_safe: bool
    owner: str
    note: str = ""

    def matches(self, path: str, method: str) -> bool:
        if method not in self.methods:
            return False
        # template match: {param} matches any single non-empty segment
        want = self.path.strip("/").split("/")
        got = path.strip("/").split("/")
        if len(want) != len(got):
            return False
        for w, g in zip(want, got, strict=True):
            if w.startswith("{") and w.endswith("}"):
                if not g:
                    return False
            elif w != g:
                return False
        return True


# ── Declared risk levels for the mutating routes that lack an auth Depends ──
# Generated from the adversarial classification workflow (classify → refute),
# 2026-07-12. Every row was read against real handler source; the verify pass
# corrected false "safe to gate" claims (e.g. /api/intel/search has live MCP
# callers → gating_safe=False).
ROUTE_RISKS: tuple[RouteRisk, ...] = (
    RouteRisk("/api/admin/crm-kg/backfill-drive-documents", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="backend/app/routers/admin_crm_kg.py:29-78 `trigger_backfill_drive_documents`. Non-dry-run mode spawns a background task calling `run_crm_drive_backfill(pool, limit up to 250, dry_r"),
    RouteRisk("/api/admin/crm-kg/build-mediated", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="backend/app/routers/admin_crm_kg.py:81-105 `trigger_build_mediated`. Background task calls `build_mediated_edges(pool)` which writes Tier-B mediated edges into the shared `crm_kg_e"),
    RouteRisk("/api/admin/crm-kg/garbage-collect", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="backend/app/routers/admin_crm_kg.py:108-133 `trigger_garbage_collect`. Background task calls `garbage_collect(pool)` which soft-deletes orphan nodes and HARD-DELETES old edges past"),
    RouteRisk("/api/admin/drive/backfill", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="NOT REFUTED. Classifier's claim stands: adding Depends(admin_auth) now cannot 401 any live caller because none exists. R3 level and gating_safe_now=true are both correct — this is "),
    RouteRisk("/api/admin/drive/poll", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="Included only as a contrast case / warning for whoever applies the gate next to this same router file: do NOT blanket-gate every route in admin_drive_health.py — /poll has a real u"),
    RouteRisk("/api/admin/drive/refresh", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="NOT REFUTED. No unauthenticated caller found to 401. Safe to gate now."),
    RouteRisk("/api/admin/drive/use-service-account", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="NOT REFUTED. No unauthenticated caller found to 401. Safe to gate now."),
    RouteRisk("/api/articles/compose", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="CONFIRMED, not refuted. Verified live at backend/app/routers/article_composer.py:300-459: only Depends(get_request_id) (bare uuid4 generator, article_composer.py:277-279), zero ide"),
    RouteRisk("/api/autonomous-agents/knowledge-graph/persist-sample", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="Verified safe to gate now: zero unauthenticated production traffic exists against this route today (no live caller found), so adding Depends(get_current_user) + _require_agent_admi"),
    RouteRisk("/api/dream/ai/generate", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="gating_safe_now still holds practically (the underlying LLM call is a stub either way, and the frontend already try/catches generate() failures — a 401 surfaces as the same generic"),
    RouteRisk("/api/dream/scrape", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="gating_safe_now is still plausible (cookie-forwarding client, graceful frontend degrade on non-2xx), but do not cite 'no repo evidence of a caller' as supporting reasoning going fo"),
    RouteRisk("/api/dream/state", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Adding a team-JWT Depends is safe from a 'won't break an existing caller' standpoint (client sends credentials:'include' cookies) and would at least restrict the blast radius to au"),
    RouteRisk("/api/funnel_email/fire-due", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="This route already has its own internal-key gate layered on top of the global JWT/API-key middleware — it does NOT need (and should NOT get) a require-admin/require-team Depends ad"),
    RouteRisk("/api/ingest/batch", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="UPHELD. No caller found repo-wide (verified by grep, not just absence of docstring). Safe to add an admin Depends -- nothing currently calls this."),
    RouteRisk("/api/ingest/file", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="UPHELD. No caller found. Safe to gate."),
    RouteRisk("/api/ingest/upload", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="UPHELD. No caller found. Safe to gate with require-team-or-admin."),
    RouteRisk("/api/intel/post-publish-queue", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="intel.py:551-586. Enqueues a slug into the post_publish_queue table for later async processing (translate+image+SEO) by the poller — no public-facing effect by itself, just a queue"),
    RouteRisk("/api/intel/post-publish-queue/done", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="intel.py:632-653. Marks queue slugs as 'done'/completed_at=NOW() in post_publish_queue — a service-to-service state-transition write on a shared operational table, not public-facin"),
    RouteRisk("/api/intel/post-publish-queue/failed", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="intel.py:656-679. Marks queue slugs as 'failed' with an error_message — same shape and same inline X-API-Key check (line 663-664) as /done. Shared pipeline-state write, not public-"),
    RouteRisk("/api/intel/post-publish-queue/step-done", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="intel.py:682-706. Marks a single processing step (translate/image/SEO) complete for a slug in post_publish_queue.completed_steps jsonb — fine-grained progress write on the same sha"),
    RouteRisk("/api/intel/search", ('POST',), RiskLevel.R1_TEAM, gating_safe=False, owner="session",
              note="REFUTED gating_safe_now. Verified intel_analytics.py:176-266 (zero Depends() today — read-only semantic search over shared Qdrant intel collections, R1 risk tier is correct on the "),
    RouteRisk("/api/intel/staging/bulk-approve/{type}", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="Verified intel.py:216-249. Zero Depends() on the handler. Bulk-archives N staging items as 'approved' (staging_service.archive_item), feeds intel_items_approved metrics — the queue"),
    RouteRisk("/api/intel/staging/bulk-reject/{type}", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Verified intel.py:252-285. Zero Depends(). Symmetric to bulk-approve but archives as 'rejected' (discard, not publish-cascade) — lower blast radius than a wrong bulk-approve, consi"),
    RouteRisk("/api/intel/staging/reject/{type}/{item_id}", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Verified intel.py:501-541. Zero Depends(). Single-item archive_item(..., 'rejected'). Confirmed caller via grep: apps/mouth/src/lib/api/intelligence.api.ts builds this exact endpoi"),
    RouteRisk("/api/intel/staging/{type}/{item_id}", ('PUT',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Verified intel.py:370-426. Zero Depends(). Partial-update of a staging item's title/content/category pre-publish — team-shared editorial content, only touches local staging JSON, n"),
    RouteRisk("/api/intel/staging/{type}/{item_id}/cover", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Verified intel.py:429-498. Zero Depends(). Decodes base64 image, writes to data/staging/{type}/covers/ + updates staging JSON. Team-shared editorial asset, filesystem-only write, n"),
    RouteRisk("/api/intel/store", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="Verified intel_analytics.py:269-290. Zero Depends() of any kind — confirmed no auth. Raw upsert into shared production Qdrant intel collection (client.upsert_documents) with caller"),
    RouteRisk("/api/legal/ingest", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="UPHELD. No caller found for this specific path. Adding Depends(verify_internal_api_key) here (matching the file's own established pattern on /parent-documents and /ingest-full) is "),
    RouteRisk("/api/legal/ingest-batch", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="UPHELD. No caller found. Safe to gate consistent with sibling routes in the same file."),
    RouteRisk("/api/legal/upload", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="gating_safe_now=true is UPHELD but for a different reason than the original: this route is not caller-less, it is caller-DORMANT with a broken caller that would need remediation re"),
    RouteRisk("/api/memory/lam/episodes", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="Since it's driven by internal agents/MCP tool calls rather than a human browser session, slapping a require-team-JWT Depends on the raw HTTP route risks breaking whatever internal "),
    RouteRisk("/api/memory/lam/episodes/{episode_id}", ('DELETE',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="Unknown caller identity (cron vs internal agent vs admin script) makes it unsafe to gate blind. Recommend R3_ADMIN Depends but FIRST trace who calls this in prod (check Fly logs / "),
    RouteRisk("/api/memory/lam/recall", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Safe to add Depends now, but the gate MUST accept the same Bearer API-key scheme the MCP `_call_safe` client already sends (backend/app/services/api_key_auth.py) — not only a user-"),
    RouteRisk("/api/naga/research", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="REFUTED. The original gating_note recommended 'require-admin or require-internal-service' — that would 401 the MCP tool's real live calls, since the MCP client explicitly does NOT "),
    RouteRisk("/api/oracle/feedback", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED. Safe to add require-authenticated-user given zero confirmed callers; do not require admin. Deprecation is a reasonable alternative given"),
    RouteRisk("/api/oracle/ingest", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="UPHELD. No caller found. The existing Depends(get_search_service) must not be mistaken for auth -- it provides zero protection today. Safe to add a real auth Depends alongside it."),
    RouteRisk("/api/performance/clear-cache", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED. No wired caller found — safe to add require-admin. Should stay R3/admin-only given the shared-process blast radius."),
    RouteRisk("/api/performance/clear-cache/embedding", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED. Safe to gate to admin."),
    RouteRisk("/api/performance/clear-cache/search", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED. Safe to gate to admin."),
    RouteRisk("/api/prime/v2/proposal", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="CONFIRMED, strengthened. Verified backend/app/routers/prime_v2.py:262-284: zero Depends in the router; calls prime_nexus_service.create_proposal() (backend/services/prime/prime_nex"),
    RouteRisk("/api/search", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED for the route-level gate: safe to add require-any-authenticated-user (not admin). Real gap is separate and NOT fixed by a route Depends: "),
    RouteRisk("/api/search/", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Identical to /api/search — same level-trust gap noted separately, same non-admin gating caveat."),
    RouteRisk("/api/sessions/cleanup", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Confirmed safe. No unauthenticated internal caller (frontend, cron, sibling Fly service) would 401 from adding require_team Depends."),
    RouteRisk("/api/sessions/create", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Confirmed safe to gate."),
    RouteRisk("/api/sessions/{session_id}", ('DELETE',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Confirmed safe to gate."),
    RouteRisk("/api/sessions/{session_id}", ('PUT',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Confirmed safe to gate with require_team now; ownership-check-per-session_id is a legitimate follow-up but correctly out of scope for this pass."),
    RouteRisk("/api/sessions/{session_id}/extend", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Confirmed safe to gate."),
    RouteRisk("/api/sessions/{session_id}/extend-custom", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Confirmed safe to gate. Unbounded ttl_hours remains a valid separate follow-up (not an authz-gate blocker)."),
    RouteRisk("/api/sessions/{session_id}/ttl", ('PUT',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="Confirmed safe to gate."),
    RouteRisk("/api/sheets/append", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="REFUTED: cannot assert 'safe to gate now' from a false premise. The confirmed caller sends `Authorization: Bearer <NUZANTARA_API_KEY>` + `X-API-Key: <NUZANTARA_API_KEY>` (server.py"),
    RouteRisk("/api/sheets/find", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="REFUTED for the same reason as append: the confirmed MCP caller authenticates via X-API-Key which HybridAuthMiddleware CAN satisfy get_current_user with, but only if the key value "),
    RouteRisk("/api/sheets/read", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="REFUTED: POST /read is exercised by the same live MCP caller as append/find/update-row/write — same X-API-Key-must-be-registered caveat applies, unverified live. GET /read has no c"),
    RouteRisk("/api/sheets/update-row", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="REFUTED for the same reason as append/find/read: confirmed live caller via X-API-Key, satisfiability of get_current_user depends on unverified server-side key registration. Verify "),
    RouteRisk("/api/sheets/write", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="REFUTED: same X-API-Key/get_current_user chain as the other 4 routes — NOT provably safe to gate without confirming the MCP caller's key is registered in prod. Given this is the hi"),
    RouteRisk("/api/team/clock-in", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Safe to add Depends(get_current_user) (any authenticated user) — the frontend already authenticates. Do NOT require admin (breaks the entire team clock-in flow). Flag corrected: th"),
    RouteRisk("/api/team/clock-out", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="Same as clock-in: safe to require any authenticated user; unsafe to require admin. This is closing a real gap, not formalizing an existing behavior."),
    RouteRisk("/api/v1/autonomous-execution/plans", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="Adding a JWT-only `Depends(get_current_user)` role gate would break the MCP caller, which authenticates via a service API key, not a browser session JWT. Per memory `discovery_case"),
    RouteRisk("/api/v1/autonomous-execution/plans/{plan_id}/execute", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="Same MCP service-key caller as /plans -- adding a JWT-role Depends would break it unless the API-key identity is first resolved/fixed to carry an appropriate role. Do not gate in i"),
    RouteRisk("/api/v1/autonomous-execution/plans/{plan_id}/steps/{step_id}/approve", ('POST',), RiskLevel.R3_ADMIN, gating_safe=False, owner="session",
              note="Two different caller shapes (Telegram webhook vs. admin dashboard vs. MCP service key) make this the riskiest one to gate blind: a JWT-only Depends would break both the Telegram we"),
    RouteRisk("/api/v1/image/generate", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="CONFIRMED. Read backend/app/routers/image_generation.py:30-74: zero Depends, builds Pollinations.ai URLs (free, no persistence, no cost) from a prompt — stateless. Same fail-closed"),
    RouteRisk("/api/v2/feedback/", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="REVISED from original: gating_safe_now=true still holds since no confirmed caller would break under require-authenticated-user, BUT the original note understated the risk — since N"),
    RouteRisk("/api/visa/check/start", ('POST',), RiskLevel.R1_TEAM, gating_safe=False, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED. Adding any Depends(get_current_user)/admin gate would 401 the anonymous public visa funnel — its entire purpose is unauthenticated visit"),
    RouteRisk("/api/visa/clock", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="Same public-funnel dependency as check/start — gating on team/admin role would break the public product. This route captures anonymous lead data by design; any hardening should be "),
    RouteRisk("/api/visa/match", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=False, owner="session",
              note="Same as /api/visa/clock — public-facing lead-gen tool, role gating would break anonymous visitor flow."),
    RouteRisk("/api/voice/elevenlabs/kbli-audit", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="CONFIRMED. Read backend/app/routers/voice.py:785-799 in full: the entire handler body unconditionally raises HTTPException(410, ...) — no service call, no state touch, no branch th"),
    RouteRisk("/internal/olympus/pulse", ('POST',), RiskLevel.R3_ADMIN, gating_safe=True, owner="session",
              note="CONFIRMED CORRECT AS ORIGINALLY CLASSIFIED, with the caveat that this repo-wide grep only covers what's checked into this codebase — if any external cron/script outside the repo (e"),
    RouteRisk("/media/generate-image", ('POST',), RiskLevel.R1_TEAM, gating_safe=True, owner="session",
              note="CONFIRMED. Read backend/app/routers/media.py:20-70 in full: zero Depends, calls ImageGenerationService(api_key='dummy') which is a stateless pollinations.ai proxy — no DB write, no"),
    RouteRisk("/media/upload", ('POST',), RiskLevel.R2_ELEVATED, gating_safe=True, owner="session",
              note="CONFIRMED with one correction to the rationale text: read backend/app/routers/media.py:73-109 in full — it does write an arbitrary unvalidated file (no content-type/size check) to "),
)


def risk_for(path: str, method: str) -> RouteRisk | None:
    """Return the declared RouteRisk for a path+method, or None if undeclared."""
    for r in ROUTE_RISKS:
        if r.matches(path, method):
            return r
    return None
