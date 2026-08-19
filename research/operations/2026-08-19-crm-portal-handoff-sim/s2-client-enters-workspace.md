---
date: 2026-08-19
domain: compliance
client_case: none — simulation of the persona-alternation attack surface, no real client data touched
sources:
  - apps/mouth/src/proxy.ts (opened this run)
  - "apps/mouth/src/app/(workspace)/layout.tsx (opened this run)"
  - apps/mouth/src/lib/api/index.ts, client.ts, auth/auth.api.ts (opened this run)
  - "apps/mouth/src/app/api/[...path]/route.ts (opened this run)"
  - apps/backend-rag/backend/app/deps/auth.py (opened this run)
  - apps/backend-rag/backend/app/deps/crm_access.py (opened this run)
  - apps/backend-rag/backend/app/utils/crm_utils.py (opened this run)
  - apps/backend-rag/backend/app/routers/crm_clients.py, dashboard.py (opened this run)
  - apps/backend-rag/backend/middleware/hybrid_auth.py (opened this run)
  - live curl probes against kita.balizero.com (run this session, GET only, no real credentials)
adversarial_review: codex
---

# S2 — Client logged into my.balizero.com opens https://kita.balizero.com/dashboard

## Scenario

A client has an active session on the portal (`my.balizero.com`). In the same
browser they open `https://kita.balizero.com/dashboard` — bookmark, stale
link, or a link an operator pasted into a chat. The SSO cookie
(`nz_access_token`, `PORTAL_SESSION_COOKIE`, `proxy.ts:78`) is domain-scoped
to `.balizero.com`, so it rides along automatically on the request to `kita`.

## Part 1 — Does `proxy.ts` gate this at the edge?

**No. Traced and reproduced live: zero.**

`proxy.ts:161-555` is one function (`proxy`) with one `hasPortalSession()`
helper (`proxy.ts:157-159`, presence-only: `Boolean(cookies.get(...)?.value)`).
Grep confirms `hasPortalSession` is referenced exactly twice in the whole
568-line file: its own definition (line 158) and one call site inside the
`isPortalDomain` branch (line 262, gating `my.balizero.com`). It is **never
called** inside the `isAppDomain` branch.

Walking the actual branch a `kita.balizero.com/dashboard` request takes
(`proxy.ts:161-555`):

1. `pathname = "/dashboard"` — not `_next`, not `/api`, no dot → falls through
   the static-file early return (`:166-176`).
2. `classifyRequest` tags human/bot/suspicious for robots-tag purposes only
   (`:179`) — no auth relevance.
3. Not `/kbli-navigator`, not `mo.` / `www.` redirects.
4. `hostname === APP_DOMAIN` → `isAppDomain = true` (`:239-242`).
5. `isDevelopment`/`isFlyDev` both false in prod.
6. `isPortalDomain` is false (hostname is `kita`, not `my`) → the ENTIRE
   `PORTAL DOMAIN` block (`:258-295`), which is the only place
   `hasPortalSession()` is ever consulted, is skipped completely.
7. `isVisaDomain`, `isTaxDomain`, zantara-domain: all false.
8. `isPublicDomain` false → skip.
9. Enter `=== APP DOMAIN (kita.balizero.com) ===` (`:441-552`):
   - `subdomain !== "prime"` → no rewrite.
   - sets `X-Robots-Tag: noindex, nofollow` (`:451`) — SEO header, not auth.
   - `pathname` doesn't start with `/portal`.
   - `pathname !== "/"` → skip the `/login` redirect.
   - not `/email`, not a `RETIRED_APP_ROUTES` prefix, not in
     `APP_SUBDOMAIN_ROUTE_MAP` (`/knowledge` only).
   - `firstSegment = "dashboard"` — not in `PUBLIC_CATEGORIES` (`:48-60`).
   - not `/services`, not `/contact`/`/team`/`/news`.
   - falls through to `// Allow all other routes on app domain` → `return
     response;` (`:551`).

**No branch in the `isAppDomain` path ever reads a cookie, a header, or any
credential.** `/dashboard` is listed in `INTERNAL_ROUTES` (`:16`), but that
array is consulted **only** inside the `isPublicDomain` block (`:386-397`) to
redirect `balizero.com/dashboard → kita.balizero.com/dashboard` — it plays no
role once the request is already on `kita`.

### Live reproduction (this run, GET only, no real credentials)

```
$ curl -s -D - -o /dev/null "https://kita.balizero.com/dashboard"
HTTP/2 200
age: 17872
etag: "efa07bbcd26c4a3c5be5dcdc2b4cae3e"
x-matched-path: /dashboard
x-nextjs-prerender: 1
x-nextjs-stale-time: 300
...

$ curl -s -D - -o /dev/null -H "Cookie: nz_access_token=junk-synthetic-not-a-real-token-000" "https://kita.balizero.com/dashboard"
HTTP/2 200
age: 17872
etag: "efa07bbcd26c4a3c5be5dcdc2b4cae3e"
x-matched-path: /dashboard
x-nextjs-prerender: 1
x-nextjs-stale-time: 300
...
```

Same `etag`, same `age`, byte-identical response, cookie present or absent,
synthetic or real-shaped. `x-nextjs-prerender: 1` confirms this is a
statically prerendered HTML shell served from Vercel's edge cache — the page
is not personalized server-side at all. This matches the code trace exactly:
the HTML that ships for `/dashboard` is always the same loading-spinner shell
(`layout.tsx:339-358`, see Part 2), because `isLoading` and `gateChecked`
default to `true`/`false` on first render regardless of who's asking.

**Source of cause:** the edge middleware treats `isAppDomain` as a pure
host/pathname router (legacy-path redirects, SEO headers, subdomain
rewrites) and was never given an identity check, unlike `isPortalDomain`
which has one (`hasPortalSession`, presence-only). The asymmetry is
structural, not a bug in one conditional: `kita.balizero.com` has **no edge
authentication layer of any kind** — 100% of gating for the operator
workspace happens client-side, in the browser, after the JS bundle loads.

## Part 2 — The workspace layout's `checkAuth` effect

`(workspace)/layout.tsx` is `"use client"` (`:1`). Relevant state on mount:
`isLoading = true` (`:54`, default), `gateChecked = false` (`:69`, default).

**Render gate** (`:339-358`): while `isLoading || !gateChecked`, the
component returns ONLY a centered spinner (`<main id="main-content"
aria-busy="true">` + a spin div + "Loading…" text). No `<AppSidebar>`, no
`<Header>`, no `{children}` (i.e. no dashboard page), no `<CellWidget>`, no
`<ZantaraWidget>`, no `<KitaCommandPalette>` — none of that JSX exists inside
this branch. This is the ONLY thing that can paint until both flags flip.

**The auth effect** (`:164-246`) is scheduled via `setTimeout(checkAuth,
100)` (`:243`) and runs once on mount. Inside `loadData()`:

1. `await loadUserProfile()` (`:169`, calling the `useCallback` at `:103-142`):
   - `api.getUserProfile()` (`:105`) reads `localStorage["user_profile"]` via
     `safeStorage.getItem` (`lib/api/client.ts:154-183`). **localStorage is
     origin-scoped, not domain-scoped** — unlike the `nz_access_token`
     cookie. A client whose only prior session was on `my.balizero.com` has
     an empty `kita.balizero.com` localStorage, so this returns `null`.
   - Falls through to `await api.getProfile()` (`:122`) →
     `auth.api.ts:141-145` → `this.client.request("/api/auth/profile")` — a
     **same-origin** relative fetch to `kita.balizero.com/api/auth/profile`.
     The browser attaches the `nz_access_token` cookie automatically (domain
     `.balizero.com` covers `kita`), and `getToken()` returns `null` (no
     Bearer in this origin's localStorage either) — so this request goes out
     as cookie-only.
   - That request lands on `app/api/[...path]/route.ts` (`:78-543`), which is
     a pure transport proxy: no persona/role logic, just credential
     plumbing. Since there's no `authorization` header, it takes the
     cookie-forward branch (`:151-162`): forwards `nz_access_token` as-is to
     `https://nuzantara-rag.fly.dev/api/auth/profile` with
     `credentials: "include"` (`:271`).
   - Backend validates the JWT and returns the caller's own profile
     (`name`/`email`/`role: "client"`/`team`) — **200 OK**, not 401. The
     token is genuinely valid; it just belongs to a client, and this
     specific endpoint's job is exactly to answer "who is this and what
     role are they" so the frontend can route them. This is by design, not
     a leak: it returns only the caller's own identity.
2. `const profile = api.getUserProfile()` (`:171`) — now populated from the
   response `client.setUserProfile()` sets (`auth.api.ts:143`) into
   localStorage/memory.
3. `if (profile?.role === "client")` (`:172`) → **true**. Executes
   `window.location.replace(getClientPortalDestination(window.location.hostname))`
   (`:178-181`) → `getClientPortalDestination` (`:28-33`) resolves
   `hostname === "kita.balizero.com"` to the hardcoded
   `CLIENT_PORTAL_URL = "https://my.balizero.com/portal"` (`:26`) — a
   cross-origin **document** navigation (deliberately not a Next router push,
   per the comment at `:173-177`, to avoid the RSC-prefetch CORS failure
   mode this repo already has a fix for elsewhere). Then `return;` (`:181`)
   exits the `try` block immediately.

Everything downstream of that `return` — the `/inbox` owner check (`:188-194`)
and, critically, `await refetchGate()` (`:199`, the INTAKE gate probe, the
**only** place that ever calls `setGateChecked(true)`, at `:159`) — **never
runs** for this code path.

`finally { setIsLoading(false); }` (`:235-237`) DOES still execute — a
`return` inside a `try` runs the paired `finally` before the function
actually returns, and `window.location.replace()` does not synchronously
halt JS execution (it schedules a cross-origin navigation that takes at
least one network round-trip). So `isLoading` flips to `false`. But
`gateChecked` was never set — it stays `false` for the entire remaining
lifetime of the component. The render guard `isLoading || !gateChecked`
(`:339`) is still `true` (the second term alone keeps it true), so the
component **stays on the loading spinner** until the browser actually
unloads the page for the cross-origin redirect. There is no intermediate
render, no flash frame, of the operator UI.

## Part 3 — What renders / what fires, precisely

| Item | Renders / fires before the bounce? | Why |
|---|---|---|
| Loading spinner (`layout.tsx:340-357`) | **Yes** — the only thing painted, start to finish | Default `isLoading=true` + `gateChecked` never flips |
| `<AppSidebar>` | No | Only appears in the JSX branch at `:390-483`, which requires `!isLoading && gateChecked && (!gateStatus?.blocked \|\| bypassed)` — never reached |
| `<Header>` | No | Same branch as above |
| `{children}` (i.e. `(workspace)/dashboard/page.tsx`, also `"use client"`) | No | Only exists inside the same final JSX branch; its own hooks (`useDashboardData`, `useRealtime`, `useQuery` for compliance alerts / system pulse) never mount, so their fetches never fire either |
| `<CellWidget>` / `<ZantaraWidget>` / `<KitaCommandPalette>` | No | Same branch |
| `<GateScreen>` (INTAKE gate wall) | No | Requires `gateStatus?.blocked`, and `gateStatus` is never set (`refetchGate` never called) — stays `null` |
| Network: `GET /api/auth/profile` | **Yes — the only network call** | `loadUserProfile()` fires unconditionally at the top of `checkAuth` |
| Network: `GET /api/intake/gate-status` (or whatever `getGateStatus()` hits) | No | Guarded by the same early `return` |
| Network: dashboard data (`useDashboardData`, compliance alerts, system pulse, realtime) | No | Component never mounts |

`AppSidebar.tsx` and the dashboard page's data hooks were checked directly:
`AppSidebar` is pure/presentational — it takes `user`/`unreadWhatsApp`/
`reviewCount` as props and has no `useEffect`/`useQuery`/module-level fetch
of its own (grep on the file, no matches). It cannot leak data on its own
even if it were forced to mount; it has none to fetch. This is moot here
regardless, since it never mounts.

**Conclusion for Part 3: no operator-only data is fetched or painted before
the bounce.** The one network call that does fire (`GET /api/auth/profile`)
returns only the caller's own identity — exactly the datum the redirect
logic needs to decide where to send them.

## Part 4 — Security boundary or UX redirect? What does the backend do?

**The client-side role check (`layout.tsx:172`) is a UX redirect, not a
security boundary.** It has no enforcement power — it decides what paints in
one browser tab. Nothing stops a client from disabling JavaScript, editing
`localStorage`, or simply issuing the same HTTP requests the layout would
have issued, directly, with curl. The real question is what the *backend*
does when those requests arrive with a client-role JWT — and the answer is
inconsistent across endpoints, traced to one architectural cause:

### The identity gate is centralized and fail-closed; the role gate is not.

`backend/middleware/hybrid_auth.py::HybridAuthMiddleware.dispatch` (`:180-320`)
runs on every request except an explicit `PUBLIC_ENDPOINTS` allowlist
(`backend/app/auth/public_endpoints.py`). For anything not on that allowlist:
it validates the JWT (cookie or Bearer), and on failure returns a hard
`401` (`:307-314`, fail-closed by design — even an internal auth-system
exception fails to `503`, never open, `:269-297`). On success it sets
`request.state.user = auth_result` (`:316`) **without inspecting the
`role` claim at all** — a client token and a team-member token both pass
this layer identically; the only difference is what `role` value ends up in
`request.state.user`.

`get_current_user()` (`backend/app/deps/auth.py:34-118`) is what turns that
into the `dict` most routers receive via `Depends(get_current_user)` — it
also does no role filtering; it returns `role: "client"` verbatim (`:57`,
`:98`).

**One purpose-built role gate exists**: `require_team_member()`
(`backend/app/deps/auth.py:155-168`) — raises `403` if
`user.get("role") == "client"`. It is used as a route dependency in exactly
**3 files** across the whole `backend/app/routers/` tree (grep, this run):
`e33_cases.py`, `debug.py`, `crm_intelligence.py`. Everything else that
needs "not a client" protection either uses a different mechanism or has
none.

### The dominant pattern instead: ownership-scoping that happens to zero out for clients

Both `GET /api/crm/clients/` (`crm_clients.py:757-816`, list) and
`GET /api/dashboard/map/clients/geo` (`dashboard.py:810-870`) use
`Depends(get_current_user)` — **any valid role passes** — plus
`get_crm_user_filter(current_user)` (`backend/app/deps/crm_access.py:76-94`):

```python
if is_crm_admin(current_user):
    return None                                    # admin: unfiltered
return current_user.get("email", "").lower()        # everyone else: WHERE assigned_to = <own email>
```

`is_crm_admin()` (`backend/app/utils/crm_utils.py:108-118`) checks an
email allowlist OR `role in ("admin","board member","ceo","founder")` —
`"client"` matches neither, so a client-role caller gets
`WHERE assigned_to = $1` bound to their own client email. Since
`assigned_to` in the `clients` table holds **staff** emails (per
`CLAUDE.md` §13's CRM RBAC rule: "Team = only `assigned_to` matches"), a
client's own email essentially never appears there — so in the live shape
of the data this degenerates to an empty result set (`{"clients": [],
"total": 0}`) rather than a 403.

This is a real but **accidental** safety net, not a designed one:
- It is designed to answer "which team member owns this row", not "is the
  caller a client". Nothing in the code asserts the two questions coincide
  — it is true only because `assigned_to` happens to be populated
  exclusively with staff addresses today.
- The `dashboard.py:810-870` docstring itself documents a P0 from
  2026-08-12 where this exact endpoint had **no principal requirement at
  all** (`/api/dashboard/map/` sat in `PUBLIC_ENDPOINTS`, returning 500
  client rows — name/phone/email/address — to anonymous internet
  traffic) before the ownership filter was added as the fix. The comment
  frames the ownership filter as protection against a **team member**
  reading rows outside their book, not against a **client** reading team
  data — the client case is covered only as a side effect of the same
  filter, never named as its own threat model.

### A third shape: no filter and no role check, just the middleware gate

`GET /api/dashboard/map/stats` (`dashboard.py:975-1029`,
`get_stats(request: Request)`) declares **no** `Depends(get_current_user)`
in its signature at all — it reads nothing from the caller. Live probe this
run:

```
$ curl -s -o /tmp/probe1.json -w "HTTP_STATUS:%{http_code}\n" "https://kita.balizero.com/api/dashboard/map/stats"
HTTP_STATUS:401
{"detail":"Authentication required"}
```

This confirms the route is **not** currently in `PUBLIC_ENDPOINTS` (the
`HybridAuthMiddleware` 401 fires before the handler runs, per
`hybrid_auth.py:299-314`) — so it is gated, just not by the handler itself.
Once a caller clears the middleware with *any* valid JWT (team or client),
`get_stats()` runs with zero further checks and returns
`total_clients`/`total_practices`/`map_lookups_24h` — aggregate counts, not
per-record PII, but genuine operator-facing business metrics, to a
client-role token exactly as readily as to a team-role token. This is the
cleanest illustration of the underlying architecture: **authentication is
centralized in one fail-closed middleware; authorization (role, and
separately, ownership) is delegated per-route, applied inconsistently, and
in this case not applied at all.**

## Source of the cause (not the symptom)

Three symptoms trace to two decisions, and it is worth naming that they
share ancestry:

1. **Symptom**: `kita.balizero.com/dashboard` returns an identical 200 HTML
   shell with or without any cookie.
   **Source**: `proxy.ts`'s `isAppDomain` branch was built purely as a
   host/pathname router (legacy-path redirects, SEO headers, subdomain
   rewrites) and was never given a `hasPortalSession()`-style presence
   check the way `isPortalDomain` was — the asymmetry is architectural, not
   a missed `if`.

2. **Symptom**: the operator sidebar/dashboard never paints and no
   operator-only data is fetched before the client bounces to
   `my.balizero.com/portal`.
   **Source**: `WorkspaceLayout` gates all rendering on
   `isLoading || !gateChecked`, and the client-redirect branch returns
   before the one statement that would ever set `gateChecked = true`
   (`refetchGate()`). This is a **correct-by-accident** design: the guard
   exists to stop a flash of the workspace before the INTAKE gate decision
   is known (per the code comment at `:337-338`), not specifically to stop
   a flash before a persona check — but it happens to also close that gap
   because the persona check sits earlier in the same function and returns
   before the gate probe.

3. **Symptom**: a client-role JWT can successfully call several
   workspace-labeled backend endpoints (profile, CRM client list, CRM
   geo-map, dashboard stats) and get a `200`, not a `403`.
   **Source, and this is the one that actually matters**: authentication
   and authorization are architecturally split, and only authentication is
   centralized and mandatory. `HybridAuthMiddleware` enforces "is there a
   valid principal" fail-closed on every non-public path. "Is that
   principal allowed to see *this*" is left to each route to opt into, via
   three different, non-uniform mechanisms observed in this trace:
   `require_team_member` (hard 403 on `role=="client"`, used in 3 files),
   `get_crm_user_filter` (ownership-by-email scoping that only
   *coincidentally* filters clients to empty because `assigned_to` happens
   to be staff-only data), or nothing (aggregate stats, gated by "any valid
   token" only). **Findings 1 and 2 both reduce to "the frontend never
   asked the question"; finding 3 is the one place that actually asked —
   and answered it three different, non-uniform ways depending which file
   you're reading.** The frontend gaps (1, 2) are UX-only precisely because
   this backend layer is what would have to fail for them to matter, and on
   the specific endpoints traced here it degrades safely by chance rather
   than by design on two counts and does not filter at all on the third.

## What I did NOT verify (scope limits, stated plainly)

- I did not obtain or use a real client-role JWT/session — per the hard
  rules, no live reproduction of "backend returns 200 with real client data"
  was attempted or is claimed. The `GET /api/dashboard/map/stats` 401 probe
  used no credentials at all (confirms the middleware gate exists; does not
  confirm what it returns to a *valid client* token — that step is
  code-traced from `hybrid_auth.py`/`crm_access.py`/`crm_utils.py`, not
  reproduced).
- I did not enumerate every workspace-labeled backend route — `crm_clients.py`
  and `dashboard.py` were chosen because they are the two files the frontend
  trace actually touches for this route (`/dashboard`) and its likely first
  clicks (client list, map). Other CRM/workspace routers may follow either
  pattern; the 3-file count for `require_team_member` is a full-repo grep
  result and is exact, but which of the *remaining* routers use ownership
  scoping vs. no scoping at all was not exhaustively catalogued here.
- `(workspace)/dashboard/page.tsx`'s own data hooks (`useDashboardData`,
  `useRealtime`, `getComplianceAlerts`, `getSystemPulse`) were confirmed
  never to mount in this scenario, but their own internal auth handling was
  not inspected — moot for S2 since they never fire, but relevant to a
  hypothetical S3 (client with JS disabled hitting `/dashboard` directly)
  which this report does not cover.

## Adversarial review

Two passes; the second removed a piece of this file's evidence.

**Pass 1 — same-family.** A Sonnet lane re-verified every citation, producing
`s2-client-enters-workspace.refutation.md`. Its cross-family seat (`claude-glm`) answered
`unrecognized_model` and it recorded *unavailable* rather than inventing a second opinion.

**Pass 2 — cross-family: Codex `gpt-5.6-terra`**, run twice independently on fresh context. Both
runs raised the same first objection, and it is accepted:

1. **The live-reproduction evidence does not support the conclusion drawn from it.** Identical
   HTTP 200 and identical `etag` with and without a cookie proves that `/dashboard` serves the same
   cached, prerendered shell — **not** that there is "zero identity check". A correctly-gated
   application built this way returns exactly the same thing, because authorization happens in
   hydration or on the API calls that follow. Confirmed independently by re-probing live and
   observing `x-nextjs-prerender: 1` on both responses. That header is the mechanism: this is a
   prerendered shell, and its cookie-independence is the expected behaviour of prerendering, not a
   statement about auth. **Treat this observation as neutral.** The finding's actual weight rests on
   the `/api/dashboard/map/stats` 401 test, which is a different piece of evidence.
2. **False as stated.** "Backend authorization is role-blind outside 3 files" — `is_crm_admin` alone
   appears in **29 router files**, and `require_crm_admin` / `require_super_admin` exist besides.
   The defensible claim is narrower: only `require_team_member` explicitly rejects `role=='client'`,
   while the rest gate on ownership filters that protect by data shape rather than by a role
   decision. That narrower claim is what this file's body argues; the summary overreached it.
3. **Unverifiable as fact.** "Returns zero rows only because no `clients.assigned_to` row is ever
   populated with a client's own email" — static code shows the predicate, not the production data,
   and not an operational "never". This file already labels it a design read; the label is correct
   and load-bearing, because that premise is what turns an ownership filter into a coincidence.
4. **Unsupported universal.** "A client hitting the API directly is only stopped by whatever
   finding 2 already found to be thin" — no complete route/dependency inventory was taken and no
   valid client token was ever tested.

The reviewer's summary of this file and its refutation: they "too often elevate *the code says X* to
*the real system does X*." That is a fair reading and it is why both ship as evidence of method
rather than as settled conclusions.
