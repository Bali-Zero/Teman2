# REPORT-RA — SAETTA-20260915 / W-C, slice R-A

Workspace session gate on `apps/mouth/src/proxy.ts` (kita.balizero.com). Implemented,
tested, mutation-proved. **Not shipped** — this is a prepare-only report; the Dux ships.

---

## 1. Unified diff of `proxy.ts`

```diff
diff --git a/apps/mouth/src/proxy.ts b/apps/mouth/src/proxy.ts
index d8645d96be..a77694def9 100644
--- a/apps/mouth/src/proxy.ts
+++ b/apps/mouth/src/proxy.ts
@@ -49,6 +49,43 @@ export const INTERNAL_ROUTES = [
   "/terminal",
 ];

+// APP DOMAIN had NO server-side session check at all. The workspace auth gate
+// lived entirely in app/(workspace)/layout.tsx, a "use client" component — so
+// the SSR HTML payload was sent to ANYONE, and only THEN did browser JS decide
+// whether to redirect to /login. A client component can style the wait for a
+// redirect; it cannot BE the gate, because by the time it runs the bytes it
+// would have hidden already left the server.
+//
+// Measured live 2026-09-15T05:17Z against production, anonymously, all HTTP
+// 200 at 46-77 KB each: /lkpm /dashboard /clients /accounting /garuda-voa /hr
+// /intelligence /notifications /obligations /omnichannel /partners /process
+// /review /second-home /settings /terminal /admin /analytics /agents. /lkpm's
+// anonymous payload carried 2 excluded-roster markers.
+//
+// SESSION_EXEMPT_INTERNAL_ROUTES carves the two INTERNAL_ROUTES entries that
+// must stay reachable with NO session: /login is the login page itself
+// (gating it is an infinite redirect loop back to itself), and /portal is
+// already redirected off to my.balizero.com earlier in this file and gated
+// there via SESSION_COOKIE / hasSession() — gating it again here would be a
+// second, redundant mechanism guarding a route this file never actually
+// serves.
+export const SESSION_EXEMPT_INTERNAL_ROUTES = new Set<string>([
+  "/login",
+  "/portal",
+]);
+
+// EXPORTED for the same reason INTERNAL_ROUTES is: a test can import the real
+// derived array instead of recomputing the filter against source text.
+export const SESSION_GATED_ROUTES = INTERNAL_ROUTES.filter(
+  (route) => !SESSION_EXEMPT_INTERNAL_ROUTES.has(route),
+);
+
+function isSessionGatedPath(pathname: string): boolean {
+  return SESSION_GATED_ROUTES.some(
+    (route) => pathname === route || pathname.startsWith(`${route}/`),
+  );
+}
+
 // /knowledge is NOT a route on kita — it maps 1:1 to a standalone app on its
 // own subdomain. See APP_SUBDOMAIN_ROUTE_MAP in the APP DOMAIN block.
 const APP_SUBDOMAIN_ROUTE_MAP: Record<string, string> = {
@@ -97,7 +134,7 @@ const ASSESSMENT_DOMAIN = "subhi.balizero.com";
 // that somehow reaches this middleware for one of them doesn't get treated as
 // public marketing content.
 const SSO_SUBDOMAINS = ["mail", "calendar", "drive", "knowledge"];
-const PORTAL_SESSION_COOKIE = "nz_access_token";
+const SESSION_COOKIE = "nz_access_token";
 const PORTAL_PUBLIC_PATHS = new Set([
   "/portal/login",
   "/portal/login-upgraded",
@@ -176,8 +213,8 @@ function isPortalPath(pathname: string): boolean {
   return pathname === "/portal" || pathname.startsWith("/portal/");
 }

-function hasPortalSession(request: NextRequest): boolean {
-  return Boolean(request.cookies.get(PORTAL_SESSION_COOKIE)?.value);
+function hasSession(request: NextRequest): boolean {
+  return Boolean(request.cookies.get(SESSION_COOKIE)?.value);
 }

 export function proxy(request: NextRequest) {
@@ -282,7 +319,7 @@ export function proxy(request: NextRequest) {
   if (isPortalDomain || enforceProdlikePortal) {
     // Portal domain: only allow /portal/* routes
     if (isPortalPath(pathname)) {
-      if (PORTAL_PUBLIC_PATHS.has(pathname) || hasPortalSession(request)) {
+      if (PORTAL_PUBLIC_PATHS.has(pathname) || hasSession(request)) {
         return response;
       }

@@ -590,6 +627,34 @@ export function proxy(request: NextRequest) {
       return crossOriginRedirect(request, publicUrl);
     }

+    // The gate that was missing entirely — see the comment above
+    // SESSION_GATED_ROUTES for the defect and the measurement. It sits LAST,
+    // after every redirect already in this block (portal, root, /email,
+    // RETIRED_APP_ROUTES, the /knowledge ghost-route map, PUBLIC_CATEGORIES,
+    // /services, /contact /team /news), on purpose: each of those keeps its
+    // exact current behaviour unchanged, and only the blanket allow below is
+    // narrowed. That is what makes "no public route changes status" true by
+    // construction, not by hope.
+    if (isSessionGatedPath(pathname) && !hasSession(request)) {
+      const loginUrl = new URL("/login", request.url);
+      loginUrl.searchParams.set(
+        "redirect",
+        `${pathname}${request.nextUrl.search}`,
+      );
+      // Same-origin (relative to request.url): no CORS reason to route this
+      // through crossOriginRedirect, and doing so would be actively wrong —
+      // it returns 204 for RSC/prefetch, which would answer an RSC fetch of a
+      // gated workspace route with an empty 204 instead of sending it to
+      // /login.
+      const gateResponse = NextResponse.redirect(loginUrl, 302);
+      gateResponse.headers.set("x-pathname", pathname);
+      // A fresh NextResponse does not inherit the X-Robots-Tag `response`
+      // carries from earlier in this block — set it explicitly, same reason
+      // the /portal and RETIRED_APP_ROUTES redirects above re-set it.
+      gateResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
+      return gateResponse;
+    }
+
     // Allow all other routes on app domain
     return response;
   }
```

Rename summary: `PORTAL_SESSION_COOKIE` → `SESSION_COOKIE`, `hasPortalSession()` →
`hasSession()`, one call-site updated (the portal block). New exports:
`SESSION_EXEMPT_INTERNAL_ROUTES`, `SESSION_GATED_ROUTES`. New private helper:
`isSessionGatedPath()`. New gate block inserted immediately before the app-domain
block's final `return response;`, after every pre-existing redirect in that block.

---

## 2. Test files changed / added

### Changed: `apps/mouth/src/__tests__/middleware.test.ts`

First ran the existing 793-line suite unmodified against the new gate: **1 test failed**
outright (`does not redirect unrelated app-domain routes (e.g. /dashboard)`, expected
not-302, got 302). But grepping every `kita.balizero.com/<gated-route>` reference showed
three more tests that kept "passing" only because their assertions were narrower than
their names claimed (`.not.toBe(301)` / `.not.toBe(307)` but never `.not.toBe(302)`) —
they encoded the old "served with no session" behaviour just as much as the one that
failed outright, just without a red to prove it. All four are workspace routes now in
`SESSION_GATED_ROUTES`; none was deleted, all four got the session cookie added:

- `should allow /lkpm on the app domain` (line ~422) — added
  `cookie: "nz_access_token=synthetic-session-token"`.
- `should allow internal app routes` (`/dashboard`, line ~430) — same.
- `should allow /clients route` (line ~439) — same.
- `does not redirect unrelated app-domain routes (e.g. /dashboard)` (line ~648, the one
  that failed outright) — same.

Every other `kita.balizero.com/<route>` reference in the file (`/portal/documents`,
`/services/api/endpoint`, `/contact`, `/team`, `/immigration...`, the ghost/retired
routes `/email` `/knowledge` `/calendar` `/documents`, `/dashboard` as a _redirect
target_ from the public-domain tests) is either not in `SESSION_GATED_ROUTES` or is
resolved by a branch that runs before the gate — verified by re-running the full
793-line file green with only the four edits above.

### Added: `apps/mouth/src/__tests__/workspace-session-gate.test.ts`

New file (sibling to `middleware.test.ts`, per the spec's "your call"). Imports
`proxy`, `INTERNAL_ROUTES`, `SESSION_GATED_ROUTES`, `SESSION_EXEMPT_INTERNAL_ROUTES`
from `../proxy`, and `walkAppRoutes` from `../../scripts/lib/app-routes.mjs`.

- **GUILT** — parametrized over the real `SESSION_GATED_ROUTES` array (19 routes):
  anonymous GET on each → 302, `location` is exactly `https://kita.balizero.com/login`
  with `?redirect=<route>` (built via `URL`/`searchParams`, not hand-encoded, so it
  can't drift from how the proxy itself constructs it).
- **GUILT deep path** — `/clients/123?tab=tax` anonymous → 302, redirect param is
  `/clients/123?tab=tax` (path **and** query preserved).
- **INNOCENCE authenticated** — same 19 routes, with the session cookie → not
  301/302/307, `x-pathname` echoes the route.
- **INNOCENCE no login loop** — anonymous `/login` and `/login/anything` are not
  redirected at all.
- **INNOCENCE app-domain public content** — `/team`, `/news`, `/contact`,
  `/services/visa-assistance`, and `/visas/kitas` (a `PUBLIC_CATEGORIES` entry) still
  301 to `balizero.com`, anonymously, unchanged.
- **INNOCENCE public domain untouched** — `/`, `/visas`, `/kbli`, `/news`, `/team`,
  `/contact` on `balizero.com` behave as before (no 301/302/307); `/dashboard` on
  `balizero.com` still 301s to `kita.balizero.com/dashboard`, **not** to `/login`.
- **INNOCENCE portal domain untouched** — re-asserts the authenticated-allow and
  anonymous-307-to-portal-login behaviour directly against the renamed
  `SESSION_COOKIE`/`hasSession()`, on top of the two pre-existing portal tests in
  `middleware.test.ts` (which stayed green — see §3).
- **Derived class-closer** (`SESSION_GATED_ROUTES covers every (workspace) page`) —
  mirrors `internal-routes-cover-workspace.test.ts`: walks
  `src/app/(workspace)` with the same `walkAppRoutes` import, takes the first URL
  segment of every real page, and asserts each is in `SESSION_GATED_ROUTES`. Includes
  the same "guards the guard" assertion (route count > 9, contains `lkpm` and
  `partners`) so a silently-empty derivation can't pass.
- **Tripwire** — asserts `SESSION_EXEMPT_INTERNAL_ROUTES` contains no route the
  filesystem walk reports as a `(workspace)` page (currently vacuously true: neither
  `/login` nor `/portal` lives under `(workspace)` — see §5).
- One extra sanity assertion: `SESSION_GATED_ROUTES.length === INTERNAL_ROUTES.length -
SESSION_EXEMPT_INTERNAL_ROUTES.size`, and neither exempted route appears in
  `SESSION_GATED_ROUTES`.

---

## 3. Command output

### `npx tsc --noEmit -p tsconfig.json` (from `apps/mouth`)

```
$ npx tsc --noEmit -p tsconfig.json > /tmp/tsc-final.log 2>&1; echo "TSC_EXIT=$?"
TSC_EXIT=0
$ wc -l /tmp/tsc-final.log
0 /tmp/tsc-final.log
```

Exit 0, zero output — no errors anywhere in the project, so there's no pre-existing
baseline to distinguish from.

### Targeted suite — `npx vitest run src/__tests__/middleware.test.ts src/__tests__/internal-routes-cover-workspace.test.ts src/__tests__/workspace-session-gate.test.ts`

Before the 4-test fix (gate present, tests unmodified):

```
❯ src/__tests__/middleware.test.ts (91 tests | 1 failed)
  × does not redirect unrelated app-domain routes (e.g. /dashboard)
AssertionError: expected 302 not to be 302
 Test Files  1 failed (1)
      Tests  1 failed | 90 passed (91)
```

After the fix, all three files:

```
 Test Files  3 passed (3)
      Tests  153 passed (153)
   Duration  614ms
```

### Broad suite — `npx vitest run src/__tests__ src/lib/client-roster-boundary.test.ts`

```
 Test Files  5 passed (5)
      Tests  169 passed (169)
   Start at  13:39:55
   Duration  568ms
```

Files run: `middleware.test.ts`, `internal-routes-cover-workspace.test.ts`,
`workspace-session-gate.test.ts`, `sentry.test.ts`, `client-roster-boundary.test.ts`.
Honestly: **169/169 passed, 0 failed, 0 skipped.**

---

## 4. Mutation proof

### Mutation A — no-op the gate (`if (false && isSessionGatedPath(pathname) && !hasSession(request))`)

Re-ran the same 3-file targeted suite. **20 tests went red**, all and only the ones
whose entire purpose is proving the gate fires:

```
 Test Files  1 failed | 2 passed (3)
      Tests  20 failed | 133 passed (153)
```

Names (all in `workspace-session-gate.test.ts`, `GUILT` describe block):

```
redirects anonymous GET /dashboard to /login?redirect=/dashboard
redirects anonymous GET /clients to /login?redirect=/clients
redirects anonymous GET /process to /login?redirect=/process
redirects anonymous GET /second-home to /login?redirect=/second-home
redirects anonymous GET /settings to /login?redirect=/settings
redirects anonymous GET /lkpm to /login?redirect=/lkpm
redirects anonymous GET /admin to /login?redirect=/admin
redirects anonymous GET /agents to /login?redirect=/agents
redirects anonymous GET /analytics to /login?redirect=/analytics
redirects anonymous GET /intelligence to /login?redirect=/intelligence
redirects anonymous GET /notifications to /login?redirect=/notifications
redirects anonymous GET /accounting to /login?redirect=/accounting
redirects anonymous GET /garuda-voa to /login?redirect=/garuda-voa
redirects anonymous GET /hr to /login?redirect=/hr
redirects anonymous GET /obligations to /login?redirect=/obligations
redirects anonymous GET /omnichannel to /login?redirect=/omnichannel
redirects anonymous GET /partners to /login?redirect=/partners
redirects anonymous GET /review to /login?redirect=/review
redirects anonymous GET /terminal to /login?redirect=/terminal
preserves a deep path AND its query string in the login redirect
```

(19 GUILT-per-route tests + the deep-path test = 20; `middleware.test.ts`'s 4
cookie-bearing tests stayed green since they authenticate regardless of the gate.)
Reverted (`if (isSessionGatedPath(pathname) && !hasSession(request))`), re-ran: 153/153
green again.

### Mutation B — drop `"/login"` from `SESSION_EXEMPT_INTERNAL_ROUTES`

```
export const SESSION_EXEMPT_INTERNAL_ROUTES = new Set<string>(["/portal"]);
```

Re-ran the same 3-file suite. **2 tests went red** (total went 153→155 because
`/login` re-entering `SESSION_GATED_ROUTES` added two new parametrized GUILT/INNOCENCE
cases, which themselves — as predicted — stayed green, since a bare 302-to-a-different-
query-string doesn't trip a status-code assertion; only the dedicated loop tests catch
the loop):

```
 Test Files  1 failed | 2 passed (3)
      Tests  2 failed | 153 passed (155)
```

Names:

```
does not redirect anonymous /login to itself
does not redirect anonymous /login/anything to /login
```

Reverted, re-ran: 153/153 green again, `npx tsc --noEmit` exit 0.

---

## 5. Findings that don't match the spec verbatim (not contradictions, but worth flagging)

- **`/agents` is not a `(workspace)` page.** It lives at `src/app/agents/page.tsx`,
  outside the `(workspace)` route group. It stays in `INTERNAL_ROUTES` /
  `SESSION_GATED_ROUTES` (per the spec's own GUILT list, which includes it), and is
  gated correctly — but the derived class-closer test can't and doesn't verify it
  (same as the pre-existing `internal-routes-cover-workspace.test.ts`, which has the
  identical property). Noted so it isn't mistaken for a gap in the derivation.
- **`src/app/(workspace)/revenue/` exists but has no `page.*` file** (only `error.tsx`
  and `loading.tsx`), so `walkAppRoutes` correctly does not report it as a route and it
  is correctly absent from both `INTERNAL_ROUTES` and `SESSION_GATED_ROUTES`. Flagging
  only because it's the one directory under `(workspace)` that looks like a route and
  isn't — if a `page.tsx` is ever added there, the derived class-closer test in
  `workspace-session-gate.test.ts` (and the pre-existing one) will correctly go red
  until it's added to `INTERNAL_ROUTES`.
- **`/login`'s `?redirect=` contract, verified on disk** as instructed:
  `apps/mouth/src/app/login/page.tsx` resolves `redirect` via `firstPartyRedirect()`
  from `./contract` against `globalThis.location.origin`, documented inline as
  "K1d-REDIRECT-SPEC" (`windows/K1d-REDIRECT-SPEC.md`) — a same-origin-only check, so
  the gate's `?redirect=<pathname+search>` (always same-origin, since it's built from
  the incoming request's own pathname) is honoured as intended. Confirmed this is
  unchanged by this PR; nothing needed touching there.
- Everything else in the spec matched what's on disk: `PORTAL_SESSION_COOKIE` /
  `hasPortalSession()` existed exactly as described with the one call-site;
  `internal-routes-cover-workspace.test.ts` and its `walkAppRoutes` import worked
  exactly as documented and were reusable without modification;
  `auth-localstorage-gate.guard.test.ts` and `client-roster-boundary.test.ts` exist at
  the stated paths.

---

## 6. Scope

Touched only: `apps/mouth/src/proxy.ts`, `apps/mouth/src/__tests__/middleware.test.ts`,
`apps/mouth/src/__tests__/workspace-session-gate.test.ts` (new). No commit, no push, no
PR — per instructions, the Dux ships.

---

## ROUND 2

### 0. Re-verified the Dux's premise myself before touching anything

Re-ran the exact live measurement (not trusted from the mandate text):

```
$ curl -s -o /tmp/lkpm_json_body.html -w "HTTP=%{http_code} SIZE=%{size_download}\n" "https://balizero.com/lkpm.json"
HTTP=200 SIZE=76797
```

Confirmed `/clients/1.2` behaviour live too (below, §4, after the fix — the Dux's own
pre-fix numbers were reproduced by the mutation-revert runs in §5, which is the same
thing measured a different way: reverting either half of the round-1 cure reproduces
the exact defect). Root cause, confirmed on disk, not assumed: two independent
mechanisms in `proxy.ts` both treat "pathname contains a dot" as "is a static asset",
which is false for a dynamic route segment (`/clients/[id]` with `id="1.2"`):

1. `config.matcher`'s only entry excluded every dotted path from ever reaching this
   file — Next does not invoke `proxy()` at all for `/clients/1.2`.
2. Even if it did, the early-return at the top of `proxy()` independently skips any
   dotted path (`pathname.includes(".")`).

Both pre-date round 1; round 1's session gate inherited them (it sits inside the same
function, after both). So did the five-PR-old `INTERNAL_ROUTES` public-domain redirect
(`isInternalRoute` inline in the `isPublicDomain` block) — `balizero.com/clients/1.2`
served the workspace payload anonymously on the PUBLIC domain too, independent of
round 1's gate entirely.

### 1. Unified diff of `proxy.ts` (round 2 delta on top of round 1 — diffed against the

exact round-1 file contents recorded in §1 above, not against git HEAD, so this is
ONLY what round 2 changed)

```diff
@@ -49,6 +49,27 @@
   "/terminal",
 ];

+// Exact-segment match over the FULL route list (unlike SESSION_GATED_ROUTES,
+// this one still includes /login and /portal). Used in TWO places below: the
+// early-return's dotted-path exclusion, and the public-domain 301.
+//
+// Measured live 2026-09-15T05:44Z against production: balizero.com/clients/1
+// 301s to kita as expected, but balizero.com/clients/1.2 answered anonymous
+// HTTP 200 at 62,817 bytes — the workspace payload, on the PUBLIC domain, for
+// a dynamic route segment ([id]) that happens to contain a dot. Two causes
+// stack: (1) config.matcher below excludes every path containing a dot, so
+// Next never even invokes this function for it; (2) the early-return a few
+// lines down independently skips any dotted path too. A dotted id walks past
+// both the session gate AND the public-domain redirect the five PRs before
+// this one (#6327 #6361 #6391 #6397 #6400) built — because both mechanisms
+// treated "has a dot" as synonymous with "is a static asset", which is false
+// for `/clients/[id]` and every other dynamic segment under INTERNAL_ROUTES.
+export function isInternalPath(pathname: string): boolean {
+  return INTERNAL_ROUTES.some(
+    (route) => pathname === route || pathname.startsWith(`${route}/`),
+  );
+}
+
 // APP DOMAIN had NO server-side session check at all. The workspace auth gate
 // lived entirely in app/(workspace)/layout.tsx, a "use client" component — so
 // the SSR HTML payload was sent to ANYONE, and only THEN did browser JS decide
@@ -226,7 +247,11 @@
     pathname.startsWith("/_next") ||
     pathname.startsWith("/api") ||
     pathname.startsWith("/static") ||
-    pathname.includes(".") // files with extensions
+    // Files with extensions — EXCEPT an internal path, because a dynamic
+    // segment value can legitimately contain a dot (/clients/1.2 is the
+    // [id] route with id="1.2", not a static asset). See isInternalPath
+    // above for the live measurement this carve-out closes.
+    (pathname.includes(".") && !isInternalPath(pathname))
   ) {
     // Still add pathname header for consistency
     const response = NextResponse.next();
@@ -463,11 +488,7 @@
     }

     // Check if trying to access internal routes
-    const isInternalRoute = INTERNAL_ROUTES.some(
-      (route) => pathname === route || pathname.startsWith(`${route}/`),
-    );
-
-    if (isInternalRoute) {
+    if (isInternalPath(pathname)) {
       // Redirect to app domain
       const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
       appUrl.search = request.nextUrl.search;
@@ -672,5 +693,15 @@
      * - public files (images, etc)
      */
     "/((?!_next/static|_next/image|favicon.ico|.*\\..*|api).*)",
+    // The pattern above excludes EVERY dotted path, including a dynamic
+    // segment value like /clients/1.2 — so Next never invoked this
+    // middleware for it at all, no matter what isInternalPath said. Next
+    // requires config.matcher to be statically analysable (literal strings,
+    // not something built from INTERNAL_ROUTES at runtime), so this is a
+    // second, hand-written copy of that array's prefixes, alternated over a
+    // single path segment. workspace-session-gate.test.ts parses this string
+    // back out and asserts it against INTERNAL_ROUTES in both directions —
+    // add a route to one without the other and that test goes red.
+    "/(accounting|admin|agents|analytics|clients|dashboard|garuda-voa|hr|intelligence|lkpm|login|notifications|obligations|omnichannel|partners|portal|process|review|second-home|settings|terminal)/:path*",
   ],
 };
```

`isInternalRoute`'s inline definition inside the `isPublicDomain` block is deleted and
replaced with a call to the new exported `isInternalPath` — same predicate, same
semantics, one definition instead of two. `INTERNAL_ROUTES` itself is unchanged (still
21 entries); the matcher's second-entry alternation is derived from it by hand (Next
requires the matcher to be a static literal) and pinned against it by a test (§3).

### 2. How the second matcher entry was verified, not guessed

Next.js does not publicly document what its `config.matcher` compiler actually does
with a pattern beyond the two idioms in its own docs. Rather than hand-derive the
resulting regex (which would just be a second, human-written translation at risk of
being wrong the same way the matcher-vs-INTERNAL_ROUTES drift risk already is), this
round imports Next's own compiler and runs it for real:

```
node_modules/next/dist/build/analysis/get-page-static-info.js  — getMiddlewareMatchers()
node_modules/next/dist/shared/lib/router/utils/middleware-route-matcher.js — getMiddlewareRouteMatcher()
```

These are the exact two functions Next's own build step calls to turn `config.matcher`
into the regex used to decide, per request, whether `proxy()` runs at all. They are not
in Next's public `.d.ts` (import guarded with a one-line `@ts-expect-error`, not an
`any` cast — see the comment in the test file), but the compiled JS export is real,
confirmed with `node -e "require('next/dist/build/analysis/get-page-static-info').getMiddlewareMatchers"`
before writing a single test against it. This is also how the exact byte-for-byte
production regex for the _existing_ first matcher entry was confirmed, independent of
any assumption:

```
$ node -e "
const { getMiddlewareMatchers } = require('next/dist/build/analysis/get-page-static-info');
console.log(getMiddlewareMatchers(['/((?!_next/static|_next/image|favicon.ico|.*\\\\..*|api).*)'], {})[0].regexp);
"
^(?:\/(_next\/data\/[^/]{1,}))?(?:\/((?!_next\/static|_next\/image|favicon.ico|.*\..*|api).*))(\.json|\.rsc|\.segments\/.+\.segment\.rsc)?[\/#\?]?$
```

(Next's official `next/experimental/testing/server` wrapper around the same two
functions was tried first and rejected: it throws `Invariant: AsyncLocalStorage
accessed in runtime where it is not available` under vitest's jsdom environment,
because it pulls in unrelated app-render modules. Calling `getMiddlewareMatchers` +
`getMiddlewareRouteMatcher` directly avoids that chain entirely and was confirmed to
run clean under `npx vitest run` before being kept.)

One finding from using the real compiler instead of a hand-rolled regex: Next
auto-appends an optional `(\.json|\.rsc|\.segments\/.+\.segment\.rsc)?` transport-suffix
group to EVERY matcher entry (its data-route/RSC-segment-prefetch mechanism). This
means the widened matcher's second entry also matches e.g. `/lkpm.json` and
`/accounting.json` — not because of anything this round added on purpose, but because
Next's compiler does this to every matcher pattern unconditionally. Traced all the way
through: `isInternalPath("/lkpm.json")` is still `false` (no `/` boundary — the
predicate correctly distinguishes a transport-suffix form from a real subpath), so
`proxy()`'s early-return still treats it as a plain dotted file and returns unchanged —
confirmed by calling `proxy()` directly for both domains (§4). No new gate opens; this
path is invoked now instead of never-invoked, but produces the identical output either
way. Not a regression, not something this round needed to special-case.

### 3. Test file changes

`apps/mouth/src/__tests__/workspace-session-gate.test.ts` — extended (round 1's
content untouched), three new `describe` blocks appended:

- **`ROUND 2: a dotted dynamic-segment value must not bypass either mechanism`** —
  GUILT: `kita.balizero.com/clients/1.2` anonymous → 302 to `/login?redirect=/clients/1.2`
  (was 200); same for `/clients/a.b` (a non-numeric dotted id, so the fix isn't
  numeric-id-shaped); `balizero.com/clients/1.2` anonymous → 301 to the app domain (was
  200 — the public-domain half of the same defect, via the `isInternalRoute` →
  `isInternalPath` refactor). INNOCENCE: both with the session cookie behave exactly
  like their undotted twins; `/static/team/adit.jpg`, `/favicon.ico`,
  `/_next/static/x.js`, `/api/health` stay untouched (proxy() called directly, not just
  matcher-checked); a direct unit check that `isInternalPath("/administration")` is
  `false` while `isInternalPath("/admin")` and `isInternalPath("/admin/users")` are
  `true` — proving the fix didn't turn the exact-segment match into a loose substring
  match.
- **`config.matcher's second entry tracks INTERNAL_ROUTES exactly`** — the drift
  killer. `extractAlternationRoutes()` parses the `/(a|b|c)/:path*` shape back out of
  the live `config.matcher` array; `diffMatcherRoutes()` compares it against
  `INTERNAL_ROUTES` in both directions (`missingFromMatcher`, `extraInMatcher`). Real
  test asserts both are `[]`. Guilt control: the SAME `diffMatcherRoutes()` function fed
  a deliberately mismatched fabricated list (`["/accounting", "/admin",
"/not-a-real-internal-route"]`) — asserts `missingFromMatcher.length > 0` and
  `extraInMatcher` equals exactly the fabricated extra route, proving the comparison
  isn't vacuous.
- **`config.matcher — which paths actually reach proxy() in production`** — the table
  from the mandate (`/clients/1`, `/clients/1.2`, `/clients/a.b`, `/lkpm.json`,
  `/dashboard`, `/static/team/x.jpg`, `/_next/static/chunk.js`, `/api/health`,
  `/favicon.ico`, `/news/some-article`, `/kbli/12345`), each pinned against Next's own
  compiled matcher (§2) with a one-line reason, plus two closing assertions: static/API
  paths are never invoked, and every `INTERNAL_ROUTES` entry — dotted or not — is.

### 4. Command output — real, from this machine, this round

**`npx tsc --noEmit -p tsconfig.json`** (from `apps/mouth`):

```
TSC_EXIT=0
```

(zero output, zero errors — includes the `@ts-expect-error` import, which would itself
turn into a hard error if it ever stopped being necessary)

**Targeted suite** — `npx vitest run src/__tests__/middleware.test.ts
src/__tests__/internal-routes-cover-workspace.test.ts src/__tests__/workspace-session-gate.test.ts`:

```
 Test Files  3 passed (3)
      Tests  178 passed (178)
   Duration  441ms
```

(153 from round 1 + 25 new in round 2: 3 GUILT + 2 INNOCENCE + 4 static/API INNOCENCE +
1 `isInternalPath` unit check + 2 matcher/INTERNAL_ROUTES parity + 11 matcher-invocation
table rows + 2 matcher-invocation closing assertions = 25.)

**Broad suite** — `npx vitest run src/__tests__ src/lib/client-roster-boundary.test.ts`:

```
 Test Files  5 passed (5)
      Tests  194 passed (194)
   Duration  519ms
```

(169 from round 1's broad run + the same 25.)

**The regex/matcher invocation table, real output** (`--reporter=verbose`, this exact
round-2 file, all green):

```
✓ config.matcher — which paths actually reach proxy() in production > /clients/1 -> invoked=true (internal route, no dot)
✓ config.matcher — which paths actually reach proxy() in production > /clients/1.2 -> invoked=true (THE BUG this round fixes: a dotted [id] value under an internal route)
✓ config.matcher — which paths actually reach proxy() in production > /clients/a.b -> invoked=true (same class, a non-numeric dotted id)
✓ config.matcher — which paths actually reach proxy() in production > /lkpm.json -> invoked=true (not a real route ... invoked because Next's matcher compiler auto-appends an optional .json/.rsc DATA-ROUTE transport suffix ...)
✓ config.matcher — which paths actually reach proxy() in production > /dashboard -> invoked=true (internal route, no dot, unaffected by this round)
✓ config.matcher — which paths actually reach proxy() in production > /static/team/x.jpg -> invoked=false (excluded — static asset)
✓ config.matcher — which paths actually reach proxy() in production > /_next/static/chunk.js -> invoked=false (excluded — Next internal asset)
✓ config.matcher — which paths actually reach proxy() in production > /api/health -> invoked=false (excluded — API route)
✓ config.matcher — which paths actually reach proxy() in production > /favicon.ico -> invoked=false (excluded — favicon)
✓ config.matcher — which paths actually reach proxy() in production > /news/some-article -> invoked=true (public content route, no dot, unaffected)
✓ config.matcher — which paths actually reach proxy() in production > /kbli/12345 -> invoked=true (public content route, no dot, unaffected)
✓ config.matcher — which paths actually reach proxy() in production > /static/... and /_next/... and /api/... are never invoked, no matter which matcher entry is checked
✓ config.matcher — which paths actually reach proxy() in production > every INTERNAL_ROUTES entry, dotted or not, is invoked
```

And directly against `proxy()` itself (not just the matcher), confirming the Dux's live
numbers are now reversed:

```
kita.balizero.com/clients/1.2  [anon]   => status=302 location=https://kita.balizero.com/login?redirect=%2Fclients%2F1.2
kita.balizero.com/clients/1.2  [cookie] => status=200 x-pathname=/clients/1.2
balizero.com/clients/1.2       [anon]   => status=301 location=https://kita.balizero.com/clients/1.2
balizero.com/clients/1.2       [cookie] => status=301 location=https://kita.balizero.com/clients/1.2
```

### 5. Mutation proof, for the NEW code specifically

**Mutation A — revert the early-return narrowing alone** (matcher stays widened):
`(pathname.includes(".") && !isInternalPath(pathname))` → `pathname.includes(".")`.

```
 Test Files  1 failed | 3 passed (4)
      Tests  4 failed | 181 passed (185)
```

Names, all in the ROUND 2 describe block:

```
kita.balizero.com/clients/1.2 anonymous -> 302 to /login (was 200)
kita.balizero.com/clients/a.b anonymous -> 302 to /login (arbitrary dotted id, not just numeric)
balizero.com/clients/1.2 anonymous -> 301 to the app domain (was 200, the public-domain half of the same defect)
balizero.com/clients/1.2 WITH the session cookie still 301s to kita (public domain never checks the cookie, same as its undotted twin)
```

Reverted, re-ran: 185/185 green again. Note what did NOT go red: the matcher-invocation
table (11+2 tests) — correct, because this mutation only breaks `proxy()`'s own logic,
not `config.matcher`, and those tests exercise the matcher in isolation from `proxy()`.

**Mutation B — revert the matcher widening alone** (early-return narrowing stays):
removed the second `config.matcher` entry entirely.

```
 Test Files  1 failed | 3 passed (4)
      Tests  5 failed | 180 passed (185)
```

Names:

```
has every INTERNAL_ROUTES entry in the matcher, and nothing in the matcher that isn't in INTERNAL_ROUTES
/clients/1.2 -> invoked=true (THE BUG this round fixes: a dotted [id] value under an internal route)
/clients/a.b -> invoked=true (same class, a non-numeric dotted id)
/lkpm.json -> invoked=true (not a real route ...)
every INTERNAL_ROUTES entry, dotted or not, is invoked
```

Reverted, re-ran: 185/185 green, `npx tsc --noEmit` exit 0. Note what did NOT go red
here: all four ROUND 2 `proxy()`-direct GUILT/INNOCENCE tests — correct, and exactly
the lesson this whole round exists to encode: calling `proxy()` directly cannot see a
matcher-only regression, because the matcher never runs in that call path. Only the
matcher-invocation-table tests (built on Next's real compiler, §2) catch Mutation B —
proving those tests, and not just the `proxy()`-direct ones, are load-bearing.

Neither mutation left 0 tests red — both are real, non-vacuous.

### 6. Findings that don't match the spec verbatim

- **`/lkpm.json` is NOT a gated-content leak** — checked myself rather than assumed
  from the mandate's evidence list. `curl`'d it live: 200, 76,797 bytes, and the first
  script chunk referenced in the HTML is `_next/static/chunks/app/(marketing)/page-*.js`
  — the MARKETING homepage bundle, not the workspace one. There is no `/lkpm.json`
  route or route handler anywhere under `src/app` (`find src/app -iname "*lkpm*"` shows
  only the real `/lkpm` and `/portal/.../lkpm` pages). The request falls through to the
  `(blog)/[category]/page.tsx` catch-all with `category="lkpm.json"`, which apparently
  renders the full public shell rather than a 404 — a separate, minor, pre-existing SEO
  quirk (200 instead of 404 for an unmatched category), unrelated to session gating and
  out of scope for this round. `isInternalPath` deliberately does NOT treat it as
  internal (no `/` boundary after `lkpm`), so this round does not touch its behaviour
  either way — confirmed identical (200, no redirect) before and after, on both
  domains (§4).
- **The mandate's suggested matcher alternation matched `INTERNAL_ROUTES` exactly** —
  derived independently (`INTERNAL_ROUTES.slice().sort().join("|")`) and compared
  character-for-character against the mandate's own suggested list before writing it
  into `proxy.ts`; identical, 21 routes both ways.
- **Next's matcher compiler auto-suffixes every entry with an optional
  `.json`/`.rsc`/`.segments/...segment.rsc` transport form** (§2) — not documented in
  Next's public docs at the level of detail needed to predict it; found only by running
  the real compiler instead of hand-translating the pattern. Traced through to confirm
  it doesn't reopen anything (§2, §4).
- **`getMiddlewareMatchers` has no public `.d.ts` export** — confirmed via `tsc`
  diagnostics before importing it, handled with `@ts-expect-error` + a comment
  explaining why (not an `any` cast), so a future Next upgrade that starts exporting it
  properly turns that line red as a prompt to remove the suppression, rather than
  silently continuing to work.
- **Next's own `next/experimental/testing/server` wrapper (`unstable_doesMiddlewareMatch`)
  is unusable here** — throws `AsyncLocalStorage` invariant errors under vitest's jsdom
  environment (confirmed both via plain `node -e` and via `vitest run` on a throwaway
  probe file). Calling the two lower-level functions it wraps directly avoids the
  problem entirely and was the approach kept.

### 7. Scope — unchanged from round 1

Touched only `apps/mouth/src/proxy.ts` and `apps/mouth/src/__tests__/workspace-session-gate.test.ts`
(extended, round 1's content untouched) this round. `middleware.test.ts` untouched in
round 2. No commit, no push, no PR — the Dux ships. All scratch/probe test files used
to verify the matcher compiler's real behaviour before committing to a design were
moved to `.trash/` (never `rm`, per the no-`rm`-in-headless-sessions rule) and are not
part of this diff — `git status --porcelain` confirms only the three files above plus
this report are touched.

BUSINESS: before this round, a client's workspace page (name, case data, everything
`/clients/<id>` renders) was readable by ANY anonymous visitor on the public
`balizero.com` domain, no login, just by putting a dot in the id — e.g. `/clients/1.2`
instead of `/clients/1`. That is exactly the UU PDP exposure round 1 was meant to
close, left open by one character. §4's proof is the same shape the Dux specified: the
anonymous request now comes back 302/301 (denied) instead of 200 (client data served),
on both domains, while a team member with a session cookie sees zero difference from
before — same 200, same `x-pathname`, same page. Nothing the team does on kita changes.

---

## ROUND 3

Small, review-driven round: a constructive reviewer (Gemini) raised points, the Dux
disposed them, and only the ones marked CURE were implemented — verbatim, nothing
extra. No `--dangerously`, no npm install/ci, no commit/push/PR (unchanged from rounds
1-2 — the Dux ships).

### CURE 1 — composite pipeline test

Round 1's 20 GUILT tests and round 2's matcher-invocation table were each correct on
their own assumptions, in separate `describe` blocks — which is exactly how round 1
missed the dot bypass in the first place: `wouldInvoke` (the real Next matcher) and
`proxy()` were never asserted TOGETHER for the same path, so a path could pass the
matcher check and pass the `proxy()` check while still failing the combined production
pipeline (matcher decides whether Next calls `proxy()` at all, then `proxy()` decides
what to do).

Added `describe("ROUND 3: composite pipeline — the real matcher AND proxy() asserted
together, not in separate blocks", ...)` to `workspace-session-gate.test.ts`, with two
helpers:

- `expectGatedThroughRealPipeline(pathname)` — asserts `wouldInvoke(pathname, ...)` is
  `true` AND `proxy()` returns 302 to `/login?redirect=<pathname>`, both in one
  function, driven over `it.each` on: `/clients/1`, `/clients/1.2`, `/clients/a.b/c`,
  `/lkpm`, `/dashboard`, `/settings/profile.v2`. `/clients/a.b/c` and
  `/settings/profile.v2` are new cases beyond what rounds 1-2 covered: a dotted segment
  that is NOT the last path segment, and a dotted segment under a gated route
  (`/settings`) other than `/clients`.
- `expectNeverGatedToLogin(pathname, hostname)` — the inverse: calls `wouldInvoke`
  (recorded, not asserted to a fixed value — the point is it doesn't matter) and
  `proxy()`, and asserts `proxy()` never answers with a 302 whose `location` contains
  `/login`. Driven over `it.each` on `/` / `/visas` / `/news/some-article` (all on
  `balizero.com`, the public domain these actually live on) and
  `/static/team/adit.jpg` (on `kita.balizero.com`, matching the exact route string
  round 2 already used for the static-asset carve-out).

Per the instruction, `wouldInvoke`/`noopRequest`/`matchers` were NOT redeclared: they
were hoisted from inside the round-2 `describe("config.matcher — which paths actually
reach proxy() in production", ...)` block to module scope (right after
`expectedLoginRedirect`), and that block's own local `const` declarations were deleted
so it now reads the shared module-scope instance. One matcher compilation for the
whole file, reused by both rounds.

All 10 new cases pass — verbatim output (`--reporter=verbose`):

```
✓ /clients/1: the real matcher invokes proxy(), AND proxy() gates it to /login
✓ /clients/1.2: the real matcher invokes proxy(), AND proxy() gates it to /login
✓ /clients/a.b/c: the real matcher invokes proxy(), AND proxy() gates it to /login
✓ /lkpm: the real matcher invokes proxy(), AND proxy() gates it to /login
✓ /dashboard: the real matcher invokes proxy(), AND proxy() gates it to /login
✓ /settings/profile.v2: the real matcher invokes proxy(), AND proxy() gates it to /login
✓ / on balizero.com: proxy() never gates it to /login, regardless of matcher invocation
✓ /visas on balizero.com: proxy() never gates it to /login, regardless of matcher invocation
✓ /news/some-article on balizero.com: proxy() never gates it to /login, regardless of matcher invocation
✓ /static/team/adit.jpg on kita.balizero.com: proxy() never gates it to /login, regardless of matcher invocation
```

### CURE 2 — empty/whitespace cookie

Added `describe("ROUND 3: an empty or whitespace-only session cookie is not a
session", ...)` with two tests against a gated kita path (`/dashboard`):

- `cookie: "nz_access_token="` (empty value) → expect 302 to `/login?redirect=/dashboard`.
- `cookie: "nz_access_token=   "` (three trailing spaces, no other value) → expect the
  same 302.

Both pass at baseline (unmutated `hasSession`), verbatim:

```
✓ ROUND 3: an empty or whitespace-only session cookie is not a session > cookie: nz_access_token= (empty value) is NOT a session -> 302 to /login
✓ ROUND 3: an empty or whitespace-only session cookie is not a session > cookie: nz_access_token=   (whitespace-only value) is NOT a session -> 302 to /login
```

**Mutation, exactly as instructed**: `hasSession` temporarily changed from

```ts
return Boolean(request.cookies.get(SESSION_COOKIE)?.value);
```

to

```ts
return request.cookies.has(SESSION_COOKIE);
```

Re-ran `npx vitest run src/__tests__ --reporter=verbose`, real output:

```
 × workspace-session-gate.test.ts > ROUND 3: an empty or whitespace-only session cookie is not a session > cookie: nz_access_token= (empty value) is NOT a session -> 302 to /login
 × workspace-session-gate.test.ts > ROUND 3: an empty or whitespace-only session cookie is not a session > cookie: nz_access_token=   (whitespace-only value) is NOT a session -> 302 to /login
 Test Files  1 failed | 3 passed (4)
      Tests  2 failed | 195 passed (197)
```

**Honest result: BOTH went red, not just the empty-value one.** The instruction said
"at least the empty-value one MUST" go red and asked me to say so plainly if the
whitespace case did NOT — it did too, so there is nothing to paper over in that
direction. Root cause, traced rather than assumed: Next's cookie-header parser trims
the whole `name=value` pair as a unit before splitting on `=`, so a header literally
containing `nz_access_token=   ` (trailing spaces at the very end of the pair, nothing
after) is parsed to value `""`, identical to the empty-value case, by the time
`request.cookies.get()` sees it — confirmed empirically by the baseline run above (both
tests pass identically against the REAL, unmutated `Boolean(...?.value)` check, which
only distinguishes falsy-vs-truthy strings and would react differently to a
non-trimmed `"   "` than to `""` if the value had actually survived with the spaces
in it). So under the `.has()` mutation, both cookies are "present" with the same
(post-trim, empty) value, and `.has()` — which only asks "is a cookie of this name
present at all," never inspecting the value — is blind to both identically. This is
not a coincidence to flag as a discrepancy; it is the expected result once the parser's
trimming behavior is accounted for, and the test amply proves what CURE 2 asked it to
prove: a future `.get()?.value` → `.has()` refactor silently turns a present-but-empty
(or present-but-whitespace) cookie into a valid session, and this test goes red the
moment that happens.

Reverted `hasSession` to the original `Boolean(request.cookies.get(SESSION_COOKIE)?.value)`.
Production code is otherwise untouched — no change was made to force either test to
pass; both already pass on the code that shipped in rounds 1-2.

### CURE 3 — two comments in `proxy.ts`, no logic change

(a) Above `export const INTERNAL_ROUTES`, appended a `WARNING:` paragraph to the
existing comment block: states that `config.matcher` at the bottom of the file carries
a literal, hand-alternated copy of these prefixes (because Next requires the matcher to
be statically analysable), that adding a route here without adding it there leaves
dotted paths under it ungated, and that
`workspace-session-gate.test.ts`'s `"config.matcher's second entry tracks
INTERNAL_ROUTES exactly"` test is what turns that specific omission red.

(b) Above `const SESSION_COOKIE = "nz_access_token"`, added a comment stating the
cookie is deliberately shared across `*.balizero.com` (`Domain=.balizero.com`, set by
`app/api/auth/login/route.ts` — confirmed on disk before writing this, see below), that
this file checks PRESENCE only, and that role/token validity are enforced downstream by
the backend on every data request, so a forged cookie value gets at most an empty
workspace shell, never data.

Verified on disk, not assumed: `apps/mouth/src/app/api/auth/login/route.ts` line 109
sets `nz_access_token=${token}`, and lines 95-100 build
`cookieDomain = ... (process.env.NODE_ENV === "production" ? ".balizero.com" : "")`,
appended as `Domain=${cookieDomain}` — i.e. `Domain=.balizero.com` in production,
exactly as the new comment states.

Zero logic changed by CURE 3 — confirmed by the unchanged 197/197 pass count and
`tsc --noEmit` exit 0 before and after (comments only touch comment lines).

### NOT done (disposed MOTIVATE, left alone, confirmed untouched)

- `pathname.includes(".")` in the early-return is still a literal dot check, not an
  extension regex — `git diff` shows no change to that line beyond round 2's own
  `&& !isInternalPath(pathname)` addition (already in the round-2 diff, not round 3).
- The 204 short-circuit for RSC/prefetch requests (`isRSCOrPrefetch` /
  `crossOriginRedirect`) is untouched — no round-3 diff touches either function.

### VERIFY — real output, this round, this machine

**`npx vitest run src/__tests__`** (from `apps/mouth`), after CURE 1+2+3 all applied
and the CURE-2 mutation reverted:

```
 Test Files  4 passed (4)
      Tests  197 passed (197)
   Duration  504ms
```

(185 pre-existing across the 4 files under `src/__tests__` — `middleware.test.ts`,
`internal-routes-cover-workspace.test.ts`, `sentry.test.ts`, and rounds 1-2 of
`workspace-session-gate.test.ts` — plus 12 new round-3 tests: 10 from CURE 1 + 2 from
CURE 2 = 197. Matches exactly.)

**`npx tsc --noEmit -p tsconfig.json`** (from `apps/mouth`):

```
TSC_EXIT=0
```

(0 lines of output, both before touching the mutation and after reverting it)

**CURE 2 mutation result** (already shown above, repeated here per the VERIFY
checklist): `hasSession` → `request.cookies.has(SESSION_COOKIE)` turns
**2 tests red** (`Tests 2 failed | 195 passed (197)`) — both the empty-value AND the
whitespace-value case, names listed in full in the CURE 2 section above. Reverted;
197/197 green again, confirmed by the `npx vitest run src/__tests__` output directly
above (that run already reflects the reverted, shipped state).

**`git diff --stat`** (from repo root, this round's final state):

```
 apps/mouth/src/__tests__/middleware.test.ts        |  26 +-
 apps/mouth/src/__tests__/workspace-session-gate.test.ts | 616 +++++++++++++++++++++
 apps/mouth/src/proxy.ts                            | 132 ++++-
 3 files changed, 760 insertions(+), 14 deletions(-)
```

Confirmed: only `apps/mouth/src/proxy.ts` and `apps/mouth/src/__tests__/*` — the same
two files/dirs as rounds 1-2, nothing new in scope. `git status --porcelain` shows the
same three tracked paths plus this untracked report.

BUSINESS: unchanged from round 2 (this round hardens the test suite and documents two
security-relevant invariants in comments — it does not change what an anonymous or
authenticated request experiences on kita.balizero.com or balizero.com). The two new
comments (CURE 3) exist so the NEXT engineer who touches `INTERNAL_ROUTES` or
`SESSION_COOKIE` sees, at the point of the edit, exactly what breaks if they get it
wrong and exactly which test catches it — turning a live-production discovery (this
mandate) into a design-time one.
