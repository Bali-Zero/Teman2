---
date: 2026-08-19
domain: security
client_case: null
sources:
  - apps/mouth/src/proxy.ts
  - "apps/mouth/src/app/(workspace)/layout.tsx"
  - apps/mouth/src/lib/api/auth/auth.api.ts
  - apps/mouth/src/components/workspace/AppSidebar.tsx
  - apps/backend-rag/backend/middleware/hybrid_auth.py
  - apps/backend-rag/backend/app/deps/auth.py
  - apps/backend-rag/backend/app/deps/crm_access.py
  - apps/backend-rag/backend/app/utils/crm_utils.py
  - apps/backend-rag/backend/app/routers/crm_clients.py
  - apps/backend-rag/backend/app/routers/dashboard.py
  - apps/backend-rag/backend/app/auth/public_endpoints.py
  - apps/backend-rag/backend/app/utils/cookie_auth.py
  - "live curl to https://kita.balizero.com/dashboard and /api/dashboard/map/stats (2026-08-19)"
adversarial_review: codex
---

# Refutation review — S2: client crosses into the operator workspace (kita.balizero.com)

**Method**: independent re-read of every cited file:line + re-run of every cited curl, plus an
attempted cross-family second opinion via `claude-glm`.

## Cross-family seat status

`claude-glm -p ...` returned `[claude-code:unrecognized_model] {"model":"glm-5.2[1m]",...}` /
`Execution error` — no substantive review, model alias not recognized by this CLI build. Per
instructions this is recorded as **unavailable**; the verdict below rests on independent
verification (A) alone, not an invented second opinion.

## Verdict summary

All three findings **SURVIVE**. Every cited file:line says exactly what the finding claims, the
two curl reproductions matched byte-for-byte (same etag `efa07bbcd26c4a3c5be5dcdc2b4cae3e` with
and without a cookie; `/api/dashboard/map/stats` returned `401 {"detail":"Authentication
required"}` with no credentials, confirming the middleware-level any-token gate the finding itself
describes), and I found no additional control elsewhere in the codebase (no RBAC middleware in
`apps/backend-rag/backend/middleware/`, no origin/host-based role gate in `hybrid_auth.py`, no
`role`-aware logic in `cookie_auth.py`) that would already close the gap the analyst reported.

### Finding 1 — kita edge middleware has zero identity check → **SURVIVES**

- `hasPortalSession()` is defined at `apps/mouth/src/proxy.ts:157-159` and its only call site is
  `proxy.ts:262`, inside the `isPortalDomain` branch. Confirmed by `grep -n hasPortalSession
  apps/mouth/src/proxy.ts` → exactly those two lines.
- The `isAppDomain` branch runs from `proxy.ts:441` (`// === APP DOMAIN (kita.balizero.com) ===` /
  `if (isAppDomain) {`) to the closing `return response; }` — confirmed the branch start line
  exactly (441) and read the full body: prime rewrite, portal→my redirect, root→/login redirect,
  `/email`→Zoho, `RETIRED_APP_ROUTES`, `APP_SUBDOMAIN_ROUTE_MAP`, `PUBLIC_CATEGORIES`,
  `/services`, `/contact`/`/team`/`/news` — none of these match `/dashboard`, so it falls through
  to the final `return response;` with no cookie read anywhere in the branch.
- Live reproduction (this run, not inherited): both curls returned `HTTP/2 200`,
  `etag: "efa07bbcd26c4a3c5be5dcdc2b4cae3e"`, `x-nextjs-prerender: 1`, `x-vercel-cache: HIT`,
  identical `content-length: 51293` — with no cookie and with a synthetic junk
  `nz_access_token`. This matches the finding's cited output exactly.
- No refutation found. The finding does not overclaim data leakage — it correctly scopes itself to
  "the edge has no identity check" (a prerendered/cached page shell, not proof of PII exposure by
  itself), which is exactly what findings 2/3 pick up.

### Finding 2 — only 3 files reject `role=='client'` explicitly → **SURVIVES, NARROWED**

- `HybridAuthMiddleware.dispatch` (`hybrid_auth.py:180` onward) was read in full through the
  auth-result branch (`:180-320`+): it 401s on no/invalid token (`auth_result` falsy) and 503s on
  an auth-system exception, but never inspects `auth_result.get("role")` — confirmed, no `role`
  token anywhere in `dispatch`.
- `require_team_member` (`apps/backend-rag/backend/app/deps/auth.py:155-168`, confirmed by direct
  read) is the only dependency that raises 403 on `role == "client"`.
- `grep -rl require_team_member apps/backend-rag/backend/app/routers/` (re-run this session) →
  exactly `e33_cases.py`, `crm_intelligence.py`, `debug.py` — matches the finding's "3 files"
  claim precisely (order differs, set is identical).
- `crm_clients.py::list_clients` (confirmed at `apps/backend-rag/backend/app/routers/crm_clients.py:756-816`,
  1 line off the finding's `757-816` — immaterial) takes `Depends(get_current_user)` +
  `get_crm_user_filter(current_user)`, no role check.
- `get_crm_user_filter` (`crm_access.py:76-94`, confirmed) returns `None` (full access) only when
  `is_crm_admin()` is true; otherwise returns `current_user.get("email","").lower()`, which the
  caller (e.g. `crm_clients.py:~883`, `dashboard.py:836-838`) uses as `WHERE assigned_to = $N`.
  `is_crm_admin` (`crm_utils.py:108-118`, confirmed) checks an email allowlist or
  `role in ("admin","board member","ceo","founder")` — `"client"` matches neither branch, so a
  client is scoped to `assigned_to = <their own email>`, which returns zero rows only because no
  `clients.assigned_to` row is ever populated with a client's own email (staff-only field in
  practice) — exactly the finding's "coincidence, not a role gate" characterization. This is a
  design read, not directly falsifiable from static code alone, but it is what the code's own
  comment at `crm_access.py:84-89` documents ("NB: this is gated on `is_crm_admin`, NOT on
  `can_view_all_clients()`") — nothing in that comment or the surrounding function claims a
  client-role exclusion by design.
- `dashboard.py::get_clients_geo` (`:810-870`, confirmed) — same ownership-filter pattern, and its
  own 2026-08-12 docstring (`:820-828`) documents that the endpoint previously had **no** principal
  requirement at all (was in `PUBLIC_ENDPOINTS` as a prefix) until a P0 fix — corroborating, not
  contradicting, the finding's "authorization here is bolted on, not designed-in" thesis.
- `dashboard.py::get_stats` (`:975-976` signature `async def get_stats(request: Request)`,
  confirmed) has **no** `Depends(get_current_user)` parameter at all — re-confirmed by direct read
  of the full function body (`:975-1029`), which returns global aggregate counts
  (`total_clients`, `total_practices`, `map_lookups_24h`) with zero per-caller scoping.
- Re-ran the finding's curl: `curl -s -o /tmp/probe1.json -w 'HTTP_STATUS:%{http_code}\n'
  https://kita.balizero.com/api/dashboard/map/stats` → `HTTP_STATUS:401
  {"detail":"Authentication required"}` (this run) — matches exactly, confirming the
  middleware-level "any valid token" gate the finding describes (and correctly does NOT claim more
  than that — it explicitly labels the client-token behavior "code-traced, not reproduced").
- Additional check performed to try to refute this finding: searched for any other RBAC/role
  middleware (`apps/backend-rag/backend/middleware/` has only `activity_logging.py`,
  `correlation.py`, `error_monitoring.py`, `hybrid_auth.py`, `pii_scanner.py`, `rate_limiter.py`,
  `request_tracing.py`, `visa_oracle_privacy.py` — none role-aware) and for an
  origin/host-based gate in `hybrid_auth.py`/`cookie_auth.py` (none found: CORS handling in
  `hybrid_auth.py` is only for preflight/response headers, not an identity gate). No hidden
  mitigation found.

**Narrowed after review.** The original heading said backend authorization is "role-blind outside 3
files". That is false as stated: `is_crm_admin` alone appears in **29 router files**, and
`require_crm_admin` / `require_super_admin` exist too. The defensible claim — which is what this
section's body actually argues — is narrower: only `require_team_member` explicitly rejects
`role=='client'`, while the rest gate on ownership filters, which protect by data shape rather than
by a role decision. The heading was writing a cheque the body did not cash.

### Finding 3 — client-side redirect is UX-only, airtight here as a side effect → **SURVIVES**

- `isLoading` default `true` at `layout.tsx:54`; `gateChecked` default `false` at `layout.tsx:69` —
  confirmed exact line numbers via `grep -n`.
- Render guard `if (isLoading || !gateChecked)` at `layout.tsx:339` — confirmed exact line, and the
  branch body (`:339-358`) renders only the spinner `<main aria-busy="true">…Loading…</main>`.
- `gateChecked` is set `true` only inside the `refetchGate()` callback's `finally` block
  (confirmed at the `setGateChecked(true)` a few lines above the excerpt shown, inside the
  function whose call site is `layout.tsx:199`).
- The client-role check fires first: `if (profile?.role === "client")` at `layout.tsx:172`,
  `window.location.replace(...)` starting `:178`, both confirmed by `grep -n`; it `return`s before
  reaching `await refetchGate();` at `layout.tsx:199` — confirmed by reading the intervening code,
  which is a straight-line sequence with no branch that skips the client check.
- The comment justifying the render guard (`layout.tsx:337-338`, confirmed verbatim: "Show loading
  state — also hold here until the gate decision is known so we never flash the workspace before
  clearance is determined (spec §5)") is about the unrelated INTAKE gate, not about client-role
  security — supporting the finding's "side effect of a different design" reading.
- Full workspace JSX (sidebar/header/`{children}`/widgets) only exists in the branch starting
  `layout.tsx:390` (`return (<I18nProvider>...`) through `:483` — confirmed by direct read; this
  branch is unreachable while `gateChecked` is false, which for a client session is permanently
  (the function has already returned by then).
- `AppSidebar.tsx`: `grep -n "useEffect|useQuery|fetch("` → zero matches (confirmed), consistent
  with "purely presentational, moot here since it never mounts."
- `auth.api.ts:141-142` (`async getProfile()` → `this.client.request<UserProfile>("/api/auth/profile")`)
  — confirmed, matches the finding's "one network call" claim (off-by-a-line from the finding's
  cited `141-145`, immaterial — the function body is `141-145` inclusive of the closing brace).
- No refutation found. The finding's own framing — "not itself a security control... see finding 2
  for what actually is or isn't a control" — is correct and consistent with what backend code
  review in finding 2 shows: a client hitting the API directly (bypassing this React component
  entirely) is only stopped by whatever finding 2 already found to be thin.

## What would have refuted these findings (and did not appear)

- A role-aware check inside `HybridAuthMiddleware.dispatch` or a separate RBAC middleware — absent.
- `hasPortalSession()` (or an equivalent) called anywhere in the `isAppDomain` branch of
  `proxy.ts` — absent (single call site confirmed, inside `isPortalDomain` only).
- A second, earlier `gateChecked`-setting path that would let the workspace JSX mount before the
  client-role redirect — absent; the function is straight-line with the client check strictly
  before the gate-await.
- Vercel-level access control in front of `kita.balizero.com` (password protection / IP allowlist)
  — no evidence of it; the live curl got a normal `200` with the app's own headers, not a
  Vercel-auth challenge.

## Cross-family seat

`claude-glm` invocation returned `[claude-code:unrecognized_model] {"model":"glm-5.2[1m]",
"query_source":"sdk"}` followed by `Execution error` — not a review, an unrecognized-model
notice. Recorded as **glm-zhipu-unavailable**; no opinion from this seat was fabricated or relied
upon.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (OpenAI family, effort medium, read-only sandbox) — the
cross-family second opinion this file records as *unavailable* when written (`claude-glm` answered
`[claude-code:unrecognized_model]`). Obtained now, it returned six BLOCKERs, and the first one
removes a piece of evidence this file relied on.

1. **Accepted, and it retracts an inference.** "*the two curl reproductions matched byte-for-byte
   (same etag … with and without a cookie)*" was read as evidence of a missing gate. It is not
   evidence of anything about authorization: an identical ETag on a prerendered, cacheable shell is
   exactly what a correctly-gated application also returns before its client-side auth runs. Treat
   that observation as neutral, not as corroboration.
2. **Accepted.** "*All three findings SURVIVE*" — no probe used a valid client token. What was shown
   is that absent credentials return 401 and that the shell is served publicly. That a client
   session can read an operator-only resource was not demonstrated.
3. **Accepted.** "*backend authorization is role-blind outside 3 files*" — derived from grepping one
   helper name. Router-level dependencies, query predicates, DB policy and differently-named guards
   are outside that criterion.
4. **Accepted.** "*no `clients.assigned_to` row is ever populated with a client's own email*" — the
   code shows the predicate; "ever" is a claim about the database contents and about operational
   practice, and was narrated rather than measured. This premise is what converts an ownership check
   into a coincidence, so it carries the finding's weight.
5. **Accepted.** "*confirming the middleware-level 'any valid token' gate*" — an uncredentialed
   request confirms only the no-token branch.
6. **Accepted.** "*No additional control elsewhere in the codebase*" — a negative assertion far
   wider than the search performed.
7. **Accepted as over-claimed.** "*airtight*" and "*permanently*" describe runtime behaviour
   (hydration, direct navigation, version skew) that was not exercised.

The reviewer's summary of both refutation files: they "too often elevate *the code says X* to *the
real system does X*." That is the correct reading, and it is why these two files are shipped as
evidence of method rather than as settled conclusions.
