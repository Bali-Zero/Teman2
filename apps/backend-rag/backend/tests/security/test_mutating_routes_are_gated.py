"""CI gate: every mutating route that BYPASSES HybridAuthMiddleware must be
an explicitly, individually documented intentional exception.

SCOPE — this is narrower than, and complementary to, ``test_route_authz_coverage.py``
--------------------------------------------------------------------------------
``test_route_authz_coverage.py`` (Case OS Fase-1, PR #2304) answers "does this
mutating route have SOME authorization posture" — and it treats an auth
``Depends``, an in-body verifier, membership in ``PUBLIC_ENDPOINTS``, OR an
explicit ``ROUTE_RISKS`` backlog entry as all equally "compliant". A route can
pass that test today while still being fully reachable by ANY authenticated
team member with zero role distinction (that is what ``ROUTE_RISKS`` records —
a declared, owned, NOT-YET-fixed gap).

This file asks a different, narrower question: does ``backend/middleware/hybrid_auth.py``
require ANY credential at all to reach this mutation? A route is public (zero
credential required, full stop) if and only if its path matches an entry in
``backend/app/auth/public_endpoints.py::PUBLIC_ENDPOINTS`` — that registry is
the ONLY way to bypass the fail-closed gate (besides the hardcoded
docs/metrics infra paths and the CORS ``OPTIONS`` preflight, neither of which
carries a mutating verb). ``PUBLIC_ENDPOINTS`` entries are mostly PREFIX
matches written for the read-side of a router (e.g. "public blog articles");
because the match is not HTTP-method-scoped, any mutating route registered
under that same prefix silently inherits the public bypass too, whether or
not anyone intended that. Empirically (2026-07-17 sweep), two prefixes did
exactly this: ``/api/blog/`` swept in ``PATCH /preferences`` + ``POST /log``,
and ``/api/news`` swept in ``POST /`` (create), ``POST /bulk``,
``POST /{news_id}/image``, and ``PATCH /{news_id}/status`` — none of which
have ANY auth dependency in the router either. See the ledger
(``research/operations/2026-07-17-mutating-routes-authz-ledger.md``) for the
full accounting and the PENDING-ARMS lines for those six.

INTENTIONALLY_PUBLIC_MUTATIONS is the durable defense: a NEW mutating route
that lands under an existing public prefix (or a new PUBLIC_ENDPOINTS entry
that happens to cover an existing mutating route) fails this test the moment
it is not also added here with a reviewed justification. Unlike
``ROUTE_RISKS``, an entry here is not a "backlog to fix later" — it is a
closed decision that this specific (method, path) is MEANT to require zero
credential.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pytest
from fastapi import FastAPI

from backend.app.auth.public_endpoints import find_entry
from backend.app.setup.route_walk import iter_leaf_routes
from backend.app.setup.router_registration import include_routers

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class IntentionalPublicMutation:
    """One deliberately-public mutating route + why zero credential is safe."""

    method: str
    path: str
    justification: str


# Verified live 2026-07-17 against the real app (345 unique mutating
# (method, path) pairs, 46 of them public). Every row below was checked
# against its PUBLIC_ENDPOINTS entry AND/OR its router handler source in this
# sweep — not copied from the registry's own `reason` text blind.
INTENTIONALLY_PUBLIC_MUTATIONS: tuple[IntentionalPublicMutation, ...] = (
    # ── Auth flows: must be reachable BEFORE the caller has a credential ──
    IntentionalPublicMutation(
        "POST", "/api/auth/login",
        "Login endpoint — cannot require the credential it is issuing.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/auth/team/login",
        "Team member login — same as above, initial authentication step.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/auth/request-magic-link",
        "Passwordless magic-link request (FASE 6) — enumeration-safe by design "
        "per public_endpoints.py; an unauthenticated client asks for a link.",
    ),
    # ── Signed/verified webhooks: identity SHOULD be proven by signature, not
    #    JWT — architecturally these three routes are correctly public. BUT
    #    a 2026-07-17 adversarial-review pass (Codex, independently re-verified
    #    by this session reading the handler source) found the ACTUAL
    #    verification depth does not match what each entry's PUBLIC_ENDPOINTS
    #    reason text claims. Kept in this allowlist (being public is the right
    #    design), but see the ledger's "claimed-vs-actual" section + PENDING-ARMS
    #    — the verification gap is the real, separate, higher-priority issue.
    IntentionalPublicMutation(
        "POST", "/webhook/whatsapp",
        "Meta WhatsApp webhook. VERIFIED 2026-07-17: whatsapp_chat.py "
        "_verify_whatsapp_signature DOES check X-Hub-Signature-256 HMAC-SHA256 "
        "when WHATSAPP_APP_SECRET is set — BUT its own docstring says "
        "'True if signature is valid OR verification is disabled (no app "
        "secret configured)': a silent fail-open if that env var is ever "
        "unset. Config-dependent, not exploitable in this repo's default "
        "state, but a landmine — see PENDING-ARMS.",
    ),
    IntentionalPublicMutation(
        "POST", "/webhook/instagram",
        "Meta Instagram webhook. VERIFIED 2026-07-17: instagram_chat.py's "
        "GET handshake DOES check INSTAGRAM_VERIFY_TOKEN, but the POST "
        "handler (webhook_router.post, line 167) has ZERO signature check — "
        "no X-Hub-Signature-256 HMAC verification of the actual message "
        "payload at all. The registry reason overclaims — see PENDING-ARMS.",
    ),
    IntentionalPublicMutation(
        "POST", "/webhook/telegram",
        "Telegram bot webhook. VERIFIED 2026-07-17: telegram_webhook.py's "
        "POST handler (line 252) has NO secret-token check (Telegram's own "
        "X-Telegram-Bot-Api-Secret-Token mechanism is never verified) — any "
        "caller can POST a forged update, including callback_query with an "
        "'intel:' prefix that reaches intel-voting logic. See PENDING-ARMS.",
    ),
    # ── Bridge (Pro<->Fly): X-Bridge-Auth hmac.compare_digest in-router ──
    IntentionalPublicMutation(
        "POST", "/api/bridge/ingest/article",
        "Pro<->Fly bridge (Phase 1 Sinapsi) — X-Bridge-Auth hmac.compare_digest "
        "against BRIDGE_API_KEY, rejects unauthorized with 401/503 in-router.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/bridge/ingest/enrichment",
        "Same bridge HMAC auth as ingest/article.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/bridge/intake-gate/doc-counts",
        "Same bridge HMAC auth as ingest/article.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/bridge/wa-media/ack",
        "Same bridge HMAC auth as ingest/article.",
    ),
    # ── wa-mirror / Intel Lake: scoped X-*-Key headers checked in-router ──
    IntentionalPublicMutation(
        "POST", "/api/crm/clients/upsert-by-phone",
        "wa-mirror CRM lead upsert — X-CRM-Write-Key + "
        "WA_MIRROR_CRM_WRITE_ENABLED checked in-router (crm_clients.py).",
    ),
    IntentionalPublicMutation(
        "POST", "/api/crm/internal/clients/{client_id}/documents/upload",
        "wa-mirror intake document upload — same X-CRM-Write-Key gate as "
        "upsert-by-phone.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/intel/lake/observations",
        "Intel Lake ingest — X-Producer-Token checked in-router "
        "(env INTEL_LAKE_PRODUCER_TOKEN).",
    ),
    IntentionalPublicMutation(
        "POST", "/api/intel/lake/observations-batch",
        "Same X-Producer-Token gate as observations.",
    ),
    # ── HR: per-incident token IS the auth (secrets.compare_digest) ──
    IntentionalPublicMutation(
        "POST", "/api/hr/late-reply/{incident_id}",
        "Late check-in reply form — per-incident token via "
        "secrets.compare_digest, no PII collected. Token IS the auth.",
    ),
    # ── Client portal: token-based, pre-account by design ──
    IntentionalPublicMutation(
        "POST", "/api/portal/invite/complete",
        "Client registration completion — the invite token is the "
        "credential; there is no account yet to authenticate as.",
    ),
    # ── Funnel / lead-gen: anonymous-by-design, no PII beyond session_id ──
    IntentionalPublicMutation(
        "POST", "/api/lead/capture",
        "Anonymous WhatsApp handoff CTA — writes lead_intents "
        "(source/context/utm/fingerprint only, no PII), 8KB cap in-router.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/funnel/session/touch",
        "Pre-auth lead cookie touch — anonymous UUID, no PII.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/funnel/session/convert",
        "Lead->client conversion bridge invoked by the portal login flow "
        "itself (session_id + client_id only).",
    ),
    IntentionalPublicMutation(
        "POST", "/api/analytics/funnel-event",
        "11 whitelisted funnel events (packages/core/analytics/funnel-view.ts) "
        "— session_id only, no PII.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/prime/v2/analyze",
        "PRIME NEXUS Layer 2 — explicitly declared 'public, rate-limited' "
        "investment analysis over public zone data.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/prime/v2/resolve",
        "PRIME NEXUS Layer 1 — explicitly declared public spatial "
        "resolution over public zone data.",
    ),
    # ── Anonymous product quizzes: stateless scoring / IP-hash rate limit ──
    IntentionalPublicMutation(
        "POST", "/api/v1/visa-oracle/recommend",
        "Anonymous visa quiz — pure scoring logic, no user data persisted.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/v1/visa-oracle/chat",
        "Anonymous visa Q&A — rate-limited by IP hash, no PII collected.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/v1/visa-oracle/handoff",
        "WhatsApp/Telegram handoff link builder — no state mutation beyond "
        "a notification.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/v1/kbli-notebook/chat",
        "KBLI Explorer — public business-classification chat, no PII.",
    ),
    # ── Marketing: explicit registry rows, standard opt-in/opt-out shape ──
    IntentionalPublicMutation(
        "POST", "/api/blog/ask",
        "AskZantara widget on public blog articles — public Q&A feature, "
        "explicit registry row (shadowed by the broader /api/blog/ prefix "
        "match, but the specific row documents deliberate intent).",
    ),
    IntentionalPublicMutation(
        "POST", "/api/blog/newsletter/subscribe",
        "Public marketing opt-in — explicit registry row.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/blog/newsletter/confirm",
        "Double opt-in confirmation — DOES check a real confirmation_token "
        "column server-side (newsletter.py ~line 300-310), unlike its "
        "unsubscribe sibling below.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/blog/newsletter/unsubscribe",
        "Opt-out — legal requirement to stay reachable without a session. "
        "VERIFIED 2026-07-17: the registry reason says 'token-based "
        "verification' but UnsubscribeRequest.token (newsletter.py:141) is "
        "accepted in the schema and NEVER read by the handler (newsletter.py "
        ":394-431) — it looks up by raw subscriberId/email only, no proof of "
        "ownership. Low severity (unsubscribe-only, no PII read/write beyond "
        "a flag), common industry pattern (CAN-SPAM one-click), but the "
        "'token-based' claim is currently false — see PENDING-ARMS.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/news/subscribe",
        "Same public opt-in shape as /api/blog/newsletter/subscribe "
        "(news.py:480) — no auth Depends, but the action itself (add an "
        "email to a mailing list) carries the same risk profile as the "
        "already-explicit blog equivalent.",
    ),
    IntentionalPublicMutation(
        "POST", "/api/news/unsubscribe",
        "Same public opt-out shape as /api/blog/newsletter/unsubscribe "
        "(news.py:512) — legal requirement to stay reachable unauthenticated.",
    ),
    # ── Observability: no-PII, best-effort ingestion, explicit registry row ──
    IntentionalPublicMutation(
        "POST", "/api/metrics/frontend",
        "Best-effort frontend browser metrics ingestion — no PII, no auth "
        "header, explicit registry row.",
    ),
    # ── Streamlit public map/KBLI dashboard: read-only compute or telemetry,
    #    already covered in spirit by the /api/dashboard/map/ registry reason
    #    ("KBLI validation, client geo, risk zones, stats") ──
    IntentionalPublicMutation(
        "POST", "/api/dashboard/map/validate-property",
        "Stateless KBLI compliance check (dashboard.py:747) — no DB write, "
        "returns an audit verdict only. Matches the registry reason "
        "verbatim ('KBLI validation').",
    ),
    IntentionalPublicMutation(
        "POST", "/api/dashboard/map/gistaru-zone",
        "Stateless GISTARU RDTR zone lookup (dashboard.py:778) — no DB "
        "write, read-only geo compute. Matches registry reason "
        "('client geo').",
    ),
    IntentionalPublicMutation(
        "POST", "/api/dashboard/map/analyze-investment",
        "Stateless BATARA+KBLI+ROI compute (dashboard.py:994, verified: no "
        "INSERT/UPDATE in the handler) — matches registry reason "
        "('risk zones, stats').",
    ),
    IntentionalPublicMutation(
        "POST", "/api/dashboard/map/analytics/log-lookup",
        "Telemetry-only insert into analytics_map_lookups (dashboard.py:882) "
        "— same shape/risk as the already-explicit /api/metrics/frontend "
        "(no PII beyond an optional user_email field the caller supplies "
        "voluntarily, no read-back exposed here).",
    ),
    # ── Admin mutations that are PUBLIC at the middleware layer but are
    #    INDEPENDENTLY re-gated inside the router via a real Depends() that
    #    does not rely on request.state.user — verified 2026-07-17 by reading
    #    the dependency chain, not assumed from the docstring. ──
    IntentionalPublicMutation(
        "POST", "/api/knowledge/visa/",
        "Docstring says 'ADMIN ONLY' — VERIFIED: Depends(get_admin_user) -> "
        "Depends(get_current_user) (backend/app/deps/auth.py:29) falls back "
        "to independently validating the Authorization Bearer JWT itself "
        "when request.state.user is unset (which it is here, since the "
        "middleware skips auth for public paths) — an unauthenticated "
        "caller still gets 401 from the router. Fragile pattern (breaks "
        "cookie-only browser admin sessions, no CSRF check runs), NOT an "
        "open authz hole. Flagged as a MEDIUM finding in the ledger, not a "
        "PENDING-ARMS security hole.",
    ),
    IntentionalPublicMutation(
        "PUT", "/api/knowledge/visa/{visa_id}",
        "Same Depends(get_admin_user) verified chain as POST /api/knowledge/visa/.",
    ),
    IntentionalPublicMutation(
        "POST", "/preview/upload",
        "Docstring says scraper-only — VERIFIED: Depends(verify_internal_api_key) "
        "(preview.py:46) is a real in-router dependency, independent of the "
        "middleware's public-path skip.",
    ),
)

_ALLOWLIST_INDEX: dict[tuple[str, str], IntentionalPublicMutation] = {
    (e.method, e.path): e for e in INTENTIONALLY_PUBLIC_MUTATIONS
}


def _unjustified(rows: Iterable[tuple[str, str, bool]]) -> list[str]:
    """Pure core, guilt+innocence-testable without booting the real app.

    ``rows`` are (method, path, is_public) triples. Returns "METHOD path"
    strings for every PUBLIC row not present in INTENTIONALLY_PUBLIC_MUTATIONS.
    A non-public row is NEVER flagged, regardless of allowlist membership —
    hybrid_auth already demands a credential for it; this test only polices
    the middleware-bypass surface.
    """
    return [
        f"{method} {path}"
        for method, path, is_public in rows
        if is_public and (method, path) not in _ALLOWLIST_INDEX
    ]


def _mutating_routes(app: FastAPI) -> Iterable[tuple[str, str]]:
    """Every unique (method, path) pair for a mutating verb on the real app.

    Uses ``iter_leaf_routes`` (NOT raw ``app.routes``) — fastapi>=0.137 turned
    ``router.routes`` into a tree of opaque ``_IncludedRouter`` nodes; a flat
    walk goes silently blind and sees only the ~4 app-level docs routes (the
    exact family-#2 "green != working" trap this repo has a tripwire for in
    ``test_route_walk_blind_guard.py``).
    """
    seen: set[tuple[str, str]] = set()
    for route in iter_leaf_routes(app):
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for m in sorted(methods & MUTATING):
            key = (m, path)
            if key not in seen:
                seen.add(key)
                yield key


@pytest.fixture(scope="module")
def app() -> FastAPI:
    a = FastAPI()
    include_routers(a)
    return a


class TestPureCoreGuiltAndInnocence:
    """Guard-over-match antidote (cicatrix family #3): no guard/gate ships
    without a colpevolezza (guilt) AND innocenza (innocence) test."""

    def test_guilt_unjustified_public_mutation_is_flagged(self) -> None:
        flagged = _unjustified([("POST", "/api/totally-fake/new-mutation", True)])
        assert flagged == ["POST /api/totally-fake/new-mutation"]

    def test_innocence_allowlisted_public_mutation_passes(self) -> None:
        # Use a REAL allowlist entry so this also breaks if the allowlist is
        # ever emptied by mistake, not just a synthetic fixture.
        sample_method, sample_path = next(iter(_ALLOWLIST_INDEX))
        flagged = _unjustified([(sample_method, sample_path, True)])
        assert flagged == []

    def test_innocence_non_public_route_is_never_flagged(self) -> None:
        """A route hybrid_auth already gates (is_public=False) needs no
        justification here, regardless of allowlist membership — this is
        the guard against a future refactor that starts flagging EVERY
        mutating route (the over-match half of family #3)."""
        flagged = _unjustified([("DELETE", "/api/totally-fake/protected", False)])
        assert flagged == []


def test_every_public_mutating_route_is_explicitly_whitelisted(app: FastAPI) -> None:
    """GUILT (real app): a mutating route that bypasses hybrid_auth (i.e. is
    public per PUBLIC_ENDPOINTS) and is not in INTENTIONALLY_PUBLIC_MUTATIONS
    fails the build. This is the durable defense — a NEW mutating route added
    under an existing public prefix (or a widened PUBLIC_ENDPOINTS entry that
    newly covers an existing mutation) fails here immediately."""
    rows = [(method, path, find_entry(path) is not None) for method, path in _mutating_routes(app)]
    unjustified = _unjustified(rows)
    assert not unjustified, (
        f"{len(unjustified)} mutating route(s) bypass HybridAuthMiddleware "
        "(reachable with ZERO credential, per PUBLIC_ENDPOINTS) with NO "
        "documented justification in INTENTIONALLY_PUBLIC_MUTATIONS. Either "
        "the PUBLIC_ENDPOINTS prefix covering it is too broad (accidentally "
        "sweeping in this method+path), or this really is meant to stay "
        "open and needs a reviewed, named justification added to this "
        "file:\n  " + "\n  ".join(sorted(unjustified))
    )


def test_no_stale_allowlist_entries(app: FastAPI) -> None:
    """ANTI-DECAY: an allowlist row whose route no longer exists, or is no
    longer public, is stale — delete it (mirrors route_risk_registry.py's
    own `test_no_dead_registry_entries` anti-decay guard)."""
    live_public = {
        (method, path) for method, path in _mutating_routes(app) if find_entry(path) is not None
    }
    stale = [
        f"{e.method} {e.path}" for e in INTENTIONALLY_PUBLIC_MUTATIONS if (e.method, e.path) not in live_public
    ]
    assert not stale, (
        "INTENTIONALLY_PUBLIC_MUTATIONS entries that match no LIVE public "
        "mutating route (route removed, method changed, or no longer "
        "public) — delete them:\n  " + "\n  ".join(stale)
    )


def test_allowlist_entries_have_real_justification() -> None:
    """ANTI-DECAY: no rubber-stamp entries (mirrors public_endpoints.py's
    own `test_every_entry_has_reason`)."""
    weak = [
        f"{e.method} {e.path}"
        for e in INTENTIONALLY_PUBLIC_MUTATIONS
        if not e.justification or len(e.justification) < 15
    ]
    assert not weak, f"Allowlist entries with missing/too-short justification: {weak}"


def test_allowlist_has_no_duplicate_entries() -> None:
    keys = [(e.method, e.path) for e in INTENTIONALLY_PUBLIC_MUTATIONS]
    assert len(keys) == len(set(keys)), "Duplicate (method, path) rows in INTENTIONALLY_PUBLIC_MUTATIONS"
