---
date: 2026-08-28
domain: operations
part: F4 frontend-platform-quality
scope: Next.js platform of apps/mouth + shared packages — architecture, auth, observability, test pyramid, design system, i18n, bundle, Vercel deploy path, dependency hygiene
sources:
  - https://nextjs.org/docs/app/guides/production-checklist
  - https://nextjs.org/docs/app/guides/authentication
  - https://playwright.dev/docs/test-sharding
  - https://mswjs.io/docs/philosophy
  - https://next-intl.dev/docs/getting-started/app-router
  - https://github.com/ai/size-limit
  - https://web.dev/incorporate-performance-budgets-into-your-build-tools/
  - https://shopify.engineering/core-web-vitals
  - https://performance.shopify.com/blogs/blog/web-performance-dashboard
  - https://www.deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues/
  - https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
  - https://www.netguru.com/blog/design-system-metrics
status: DONE
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# F4 — Frontend platform quality

## Anatomy (as measured)

All measurements taken on the pinned worktree at `11a3c89a2e` (origin/main), 2026-08-29.

**Framework and stack.** `apps/mouth` is a Next.js 16 App Router application (`apps/mouth/package.json`: `next ^16.3.1`, React 19.2.8, Tailwind 4, TypeScript 5.9, Zod 4, TanStack Query 5, Radix primitives, `@sentry/nextjs ^10.70.0`). The middleware file uses Next 16's renamed convention `src/proxy.ts` (not `middleware.ts`), implementing multi-domain routing between `balizero.com` (public) and `kita.balizero.com` (internal app) with an explicit `INTERNAL_ROUTES` list (`src/proxy.ts:14-29`), a subdomain route map, and retired-route handling that encodes fleet history (`src/proxy.ts:39-46` documents the deleted calendar/drive apps).

**Route surface.** 158 `page.tsx`, 30 `layout.tsx`, 41 `route.ts` handlers, organized into 7 route groups (`(assessment)`, `(blog)`, `(book)`, `(marketing)`, `(tax-calendar)`, `(visa-oracle)`, `(workspace)`) plus ~20 ungrouped top-level segments (`src/app/`). This is a genuinely large surface for one app: public marketing site, blog/CMS, KBLI explorer, visa funnel, client portal, and a full internal workspace live in one Next.js instance behind one domain-splitting proxy.

**Server/client split.** 476 of 957 `.tsx` files under `src/app` + `src/components` declare `"use client"` (~50%), and 113 of 158 pages (71%) are client components. The app is client-heavy: only 6 files in `src/app` import `next/headers` (server-side cookie/header reading), so almost all data fetching happens in the browser through the API client rather than in Server Components. This is the single biggest architectural distance from current Next.js guidance (see research section) — the App Router is used mostly as a file-router for SPA-style pages, not as a server-first rendering platform.

**Error/loading boundaries.** Genuinely excellent coverage: 87 `error.tsx` + 87 `loading.tsx` distributed down to leaf segments (e.g. `src/app/portal/(authenticated)/matters/[id]/error.tsx`), one `global-error.tsx`, 2 `not-found.tsx`. Boundary discipline is real, not theater.

**Auth plumbing (the measured version of the known trap).** Auth is dual-path by design (`src/lib/api/client.ts:36-37`: httpOnly cookies primary, localStorage "OPTIONAL … UX enhancement"; `client.ts:313,326` send `credentials: "include"`). But `isAuthenticated()` (`src/lib/api/client.ts:211-215`) returns `getToken() !== null` where `getToken()` reads only the localStorage-backed `auth_token` (`client.ts:137-141`). Measured callers in page code: **9 gate pages** — `(workspace)/settings/{security,roles,users}`, `(workspace)/admin` + `admin/{system,team-activity,cell}`, `agents`, `dream` (the live-context figure "13 gates" counts additional non-page callers; 16 files total reference it including the API-client tests and types). A user authenticated purely via httpOnly cookie (localStorage blocked or cleared — Safari private mode is called out in the code's own comments at `client.ts:86`) is silently treated as unauthenticated on those 9 pages. A separate, properly scoped `PublicAuthClient` exists for unauthenticated auth screens with an endpoint allowlist and CSRF handling (`src/lib/api/public-auth.ts:6-16,29-31`).

**API layer.** `src/lib/api/` is a large hand-built SDK: ~30 domain subdirectories (crm, portal, chat, knowledge, whatsapp, telegram, …) over a shared `ApiClient` with typed `schema.d.ts` generated from the backend's OpenAPI (`package.json` scripts `generate:openapi` → `generate:api` → `validate:visa-oracle-openapi`, i.e. a real contract pipeline against `apps/backend-rag`). `src/lib/gateway.ts` (103 lines) implements a dual-path transport: localhost gateway (`https://127.0.0.1:8090`) first, cloud fallback to Fly — with the load-bearing comment that SSE streams bypass the Vercel proxy because Vercel's 60s timeout kills long RAG responses (`gateway.ts:9-12`).

**Realtime.** `src/lib/realtime.tsx` (473 lines) is a hand-rolled WebSocket service class: token auth via `getValidToken()`, heartbeat interval, capped exponential reconnect (`maxReconnectAttempts = 5`, `realtime.tsx:31-32`), typed message guards from `api/types/realtime.types`. Functional but bespoke — the reconnect cap means a laptop that sleeps through 5 backoff cycles stays silently disconnected until reload.

**Design system reality.** Three layers, only one alive: (1) `packages/design-system` declares itself `[DEPRECATED]` in its own `package.json` description and has **zero** importers in mouth src (only `scripts/token_lint.py`, `scripts/brand_token_lint.py`, `scripts/brand_api_gen.py` read its `brand-api/components.json`); (2) `packages/core` (`@balizero/core`) is the real foundation — tokens (primitives/semantic/operative CSS), fonts, effects, ~20 tested components (NavShell, ThemeProvider, ProgressRing, FactBadge…) with per-component exports — but only **10 files** in mouth import it, almost all in `(workspace)`; (3) mouth's own `src/components/` — 43 domain directories plus a 36-file shadcn-style `ui/` kit (button, dialog, table, toast… with colocated tests) — carries the bulk of the UI. So the design system exists and is tested, but the app substantially bypasses it: brand consistency is enforced negatively by CI lint (`token-lint.yml`: "no new hardcoded brand hex in redesigned surfaces") rather than positively by shared-component adoption.

**Test infrastructure.** Larger than the mandate's briefing figures: **441 unit test files / 3,860 `it()`/`test()` blocks** in `src` (vitest 4, jsdom, Testing Library, istanbul coverage) and **53 Playwright spec files / 256 test blocks** in `e2e/`, including dedicated `a11y/`, `auth/`, `offline/`, `websocket/`, `smoke/` suites and a separate prod-like config (`playwright.prodlike.config.ts`) with a fail-closed synthetic-contract smoke (`playwright.config.ts:19-21` deliberately excludes it from the default run). CI wiring is real: `tests.yml` runs mouth vitest with a coverage gate (`matrix include: app: mouth / coverage: true`, `tests.yml:1624-1625`) and — after a scar where `packages/core`'s vitest config had no caller ("Built, never armed", `tests.yml:1721-1724`) — core's suite is now a step of the same required job. The coverage bar, however, is **20% statements** (`package.json` `test:coverage:check`), a tripwire against collapse, not a quality gate. Playwright runs `workers: 1` on CI with 2 retries (`playwright.config.ts:26-29`) — serial, no sharding.

**Observability.** Sentry via `@sentry/nextjs` with three runtime configs: client (`sentry.client.config.ts` — 10% traces sampling in prod, session replay 10%/100%-on-error with `maskAllText`+`blockAllMedia`, dev events dropped in `beforeSend`), server and edge. Wiring is *conditional by construction*: `next.config.ts:391-392` applies `withSentryConfig` only if a DSN env var exists, and `:384-385` disable the webpack plugins per-side without DSN — a missing/empty env produces a build with no Sentry at all and no error (the on-disk mechanism behind the live-context fact "`@sentry/nextjs` does not block the build"; the config's own comment at `next.config.ts:366-379` records the opposite scar — `silent: true` once hid an expired `SENTRY_AUTH_TOKEN`, so `silent` is deliberately unset). The Sentry project name (`nuzantara-frontend` per live context) is env-driven (`SENTRY_PROJECT`, `next.config.ts:381-382`) and not verifiable on disk (unverified). Web-vitals field data: `src/lib/web-vitals.ts` dynamically imports `web-vitals` and reports CLS/INP/LCP/TTFB/FCP to GA4 `gtag` (`web-vitals.ts:26-42`) — RUM goes to Google Analytics, not to Sentry; errors and field performance live in different silos. Structured logging via `src/lib/logger.ts` (378 lines) + `lib/logging/structured-logger.ts`.

**Bundle discipline.** Three mechanisms, none a hard size budget: (1) `scripts/assert-public-login-bundle.mjs` runs *inside* `npm run build` and fails the build if the public login route's client chunks leak internal API routes (deny-by-default, `ALLOWED_ROUTE_PREFIXES = ["/api/auth/"]`, lines 24-27) — a security-shaped bundle gate, genuinely novel; (2) `BUNDLE_REPORT.md` documents an honest chunk-reduction audit (target <15 chunks **not achieved**, structural floor ~18 with Next 16 + Turbopack, measured tables included); (3) `lighthouse.yml` runs Lighthouse CI on 10 public URLs with `.lighthouserc.json` asserting performance ≥0.85 *warn*, accessibility ≥0.9 **error**, LCP ≤2.5s warn, TBT ≤300ms warn. So: a11y is the only hard Lighthouse gate; performance regressions warn and pass; JS byte-size has no budget anywhere. `productionBrowserSourceMaps: false` (`next.config.ts:28`); source maps go to Sentry via the plugin.

**i18n.** Hand-rolled: `src/i18n/index.tsx` is a client-side React context with 5 locales (en/fr/id/it/ru) **statically imported** — all ~80KB of locale JSON ships to every client regardless of locale. No next-intl, no URL-locale routing, no server-side message resolution; locale is client state (`LocaleHead`/`ContentLangSync` doing DOM sync). Testing of i18n behavior is real (7 test files incl. `secondhome-forbidden-claims.test.ts`, a compliance-shaped i18n test).

**a11y.** One dedicated axe e2e (`e2e/a11y/workspace-a11y.spec.ts`; 3 files reference `AxeBuilder`), `@axe-core/playwright` in devDependencies, plus the Lighthouse a11y ≥0.9 hard assertion on 10 public pages. Coverage is thin relative to 158 pages, but the hard-error posture is right.

**Vercel deploy path.** `vercel.json` is minimal (`buildCommand: npm run build`, `installCommand: cd ../.. && npm ci --include=dev` — monorepo root install; no `ignoreCommand`). The deploy-skip trap from live context (a frontend commit sandwiched between two backend commits doesn't get deployed) is platform-side and not verifiable on disk (unverified), **but the repo has built the antibody**: `.github/workflows/frontend-live-sentinel.yml` runs every 30 minutes and on every frontend-touching push to main, computes the last commit that touched `apps/mouth`/`packages`/lockfiles (`git log -1 -- apps/mouth packages …`), and checks that production is actually serving a deployment containing that commit — converting the silent skip into a red check. Frontend CI is broad: `frontend-typecheck.yml`, `tests.yml`, `lighthouse.yml`, `token-lint.yml`, `lint-cross-import.yml`, `lint-i18n-providers.yml`, `prettier-changed-files.yml`, `npm-lock-sync.yml`, `frontend-live-sentinel.yml` — 106 workflows total in the repo.

**Security headers.** CSP set in `next.config.ts:198`: `frame-ancestors 'none'`, `object-src 'none'`, but `script-src 'self' 'unsafe-inline' …` — no nonces/hashes, so the CSP does not actually stop injected inline scripts; `connect-src` allowlists Fly + Sentry + GA. XSS utilities (`lib/security/xss.ts`, DOMPurify) and input validation (`lib/security/validation.ts`) exist and are small (94/92 lines).

## Honest state vs. SOTA

**Genuinely good (better than most teams this size):**

- Boundary coverage (87+87+global-error) is above what most production Next.js apps ship.
- The **frontend-live-sentinel** is a rare pattern: CI that verifies *production is serving the commit it should*, purpose-built from a real deploy-skip scar. Most SOTA teams have this only implicitly via deploy orchestration.
- The **public-login bundle leak gate** (deny-by-default API-route scan of built chunks, inside the build command itself) is a genuinely novel, security-shaped bundle check.
- OpenAPI-generated types with a contract validation script = real frontend/backend contract discipline.
- Test *volume* is high (3,860 unit blocks, 256 e2e blocks) with colocated tests as the norm, and the "built, never armed" scar was cured in CI (packages/core suite now runs inside the required job).
- `BUNDLE_REPORT.md` is honest engineering writing: it documents a failed target with measurements instead of claiming victory.

**Theater or thin:**

- The **20% statement-coverage gate** is a collapse tripwire dressed as a coverage gate. With 441 test files the real number is likely far above it, meaning the gate asserts nothing about new code (no ratchet, no per-diff coverage).
- **Design-system maturity is inverted**: the deprecated package still sits in `packages/`, the live foundation (`@balizero/core`) has 10 importers against ~950 UI files, and brand consistency is enforced by a *negative* hex-lint rather than *positive* component adoption. Two parallel UI kits with no adoption metric.
- **Lighthouse performance assertions are warn-level** — a performance regression cannot fail CI; only a11y can.
- **a11y program**: one axe spec + Lighthouse on 10 public URLs, for a 158-page app with a client portal. Posture right, surface ~6%.

**Broken or structurally risky:**

- The **auth split-brain**: cookie-primary transport with localStorage-only `isAuthenticated()` on 9 admin/settings gates (`client.ts:211`). These are client-side gates on client pages; `proxy.ts` does domain routing, not auth, so nothing server-side protects those routes either. (Data access is still protected by the backend, but the routing/UX layer lies about auth state, and the pattern is exactly what the official Next.js auth guide calls "not recommended" — see below.)
- **Client-heavy architecture** (71% of pages client components, 6 files using `next/headers`): data fetching, auth state and i18n all resolve in the browser. This forfeits most of what Next 16 provides — server components, streaming, cache components — and makes the localStorage-auth class of bug *possible at all*.
- **i18n ships all 5 locales to every visitor** (~80KB JSON) and cannot do localized SSR/SEO (no locale routing, no hreflang per locale path).
- **Sentry can silently vanish**: a deployment without the DSN env builds green with zero observability (`next.config.ts:391-392`) — the "exists ≠ armed" disease (scar family #2) on the observability layer itself.
- **Playwright serial on CI** (`workers: 1`): 256 e2e blocks run one at a time; wall-clock cost lands on every PR and creates pressure to skip.

## Deep research: the world's best

**1. Server-first rendering — Vercel/Next.js production guidance.** The official production checklist is unambiguous: Server Components are the default rendering model precisely because they "have no impact on the size of your client-side JavaScript bundles"; client boundaries should be placed deliberately ("check the placement of your `use client` boundaries"), request-time APIs (`cookies()`) should be wrapped in `<Suspense>`, streaming via `loading.tsx` should prevent whole-route blocking, and forms should run through Server Actions with server-side validation ([production checklist](https://nextjs.org/docs/app/guides/production-checklist)). Mouth already excels at the streaming/boundary half of this list and inverts the rendering half.

**2. Auth architecture — the official Next.js authentication guide.** The prescription is precise and directly indicts the measured gap: sessions live in **httpOnly, Secure cookies set on the server**; middleware/proxy does **optimistic, cookie-only checks** ("avoid database checks in Proxy"); real authorization lives in a **Data Access Layer** with a cached `verifySession()` that every data request passes through; and — verbatim — "a common pattern in SPAs is to `return null` in a layout or a top-level component if a user is not authorized. This pattern is **not recommended**" ([authentication guide](https://nextjs.org/docs/app/guides/authentication)). SOTA auth in this stack is: proxy-level optimistic redirect + DAL-level secure check, never client-side boolean gates, and never localStorage as the source of truth.

**3. Testing at scale — Playwright sharding + MSW as network contract.** Playwright's own CI guidance: shard with `--shard=x/y` across a GitHub Actions matrix, emit **blob reports**, merge with `npx playwright merge-reports`, and enable `fullyParallel` for test-level granularity ([test sharding](https://playwright.dev/docs/test-sharding)). A 4-shard matrix turns a serial hour into ~15 minutes for the cost of three more runners. MSW's philosophy solves a different scale problem: mock **at the network level** with WHATWG Request/Response handlers that are "a standalone layer" reused identically across unit tests, integration tests, and dev — the mock becomes a *contract describing network behavior* rather than per-test fetch stubs ([MSW philosophy](https://mswjs.io/docs/philosophy)). Mouth's 3,860 unit blocks mock at the module level today; a shared MSW handler set would let unit, e2e and dev share one API truth (and would pair naturally with the existing OpenAPI-generated types).

**4. Bundle budgets in CI — size-limit and web.dev.** The sector standard is a **hard, per-PR budget**: `size-limit` "checks every commit on CI, calculates the real cost of your JS for end-users and throws an error if the cost exceeds the limit", posting the size diff as a PR comment ([ai/size-limit](https://github.com/ai/size-limit)); web.dev's guidance is the same shape — budgets as build-failing numbers, not dashboards ([performance budgets in build tools](https://web.dev/incorporate-performance-budgets-into-your-build-tools/)). Lighthouse CI supports `assert: error` on byte and metric budgets. The distance from mouth is small mechanically (Lighthouse CI already runs; `@next/bundle-analyzer` is installed) but large in posture: today no byte number can fail a PR.

**5. Frontend observability — Sentry hardening + unified RUM.** Sentry's own Next.js production guidance: `tunnelRoute` to route events through your own server past ad-blockers, `widenClientFileUpload: true` for complete source maps, an `instrumentation.ts` with `onRequestError` for server-side capture, per-environment sampling, and `silent: !process.env.CI` so CI logs uploads ([Sentry Next.js manual setup](https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/)). Sector practice pairs **synthetic** monitoring (availability, baseline) with **RUM field data** (percentiles by device/geo, never averages) in the *same* tool that holds errors, so a spike in INP correlates with a release and a stack trace. Shopify institutionalized exactly this: a merchant-facing **web performance dashboard with real-user Core Web Vitals** ([Shopify performance dashboard](https://performance.shopify.com/blogs/blog/web-performance-dashboard)) and an engineering culture that treats CWV as a product KPI ([Shopify engineering on CWV](https://shopify.engineering/core-web-vitals)). Mouth has the synthetic half (live-sentinel, Lighthouse) and sends field vitals to GA4, where no engineer looks and no alert fires.

**6. Design systems — adoption as the metric, tokens as the API.** Design-system maturity in the Polaris/Lightning tradition is measured by **adoption rate** — the percentage of product surfaces using system components versus custom implementations — plus component usage frequency and objective deprecation criteria ([design system metrics](https://www.netguru.com/blog/design-system-metrics)). Shopify's 2025 Polaris rebuild moved to **framework-agnostic web components** specifically to break dependency-version churn between the system and its consumers. The transferable lesson for a solo-operator monorepo is not web components; it is (a) one system, not three; (b) an adoption number computed in CI so drift is visible; (c) tokens as the stable API (which `@balizero/core/tokens` already models well).

**7. Accessibility programs — automated coverage is ~57%, so wire it wide.** Deque's cross-industry study (13k+ pages, ~300k issues) measured that axe-core automation detects **57.38% of accessibility issues by volume** ([Deque study](https://www.deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues/)). The SOTA consequence: run axe on *every* e2e navigation (a shared fixture, not a dedicated spec), hard-fail serious/critical violations, and reserve manual audit budget for the remaining 43% on the highest-stakes flows (checkout, login, forms). One spec + 10 Lighthouse URLs samples a fraction of what the same tooling could cover for near-zero marginal cost.

**8. i18n architecture — next-intl's server-first model.** The App Router reference implementation: a `[locale]` URL segment, **server-side message loading** per request ("only rendering results are sent" to the client), per-locale JSON split so a visitor downloads one locale, and natural hreflang/static-rendering support for multilingual SEO ([next-intl App Router](https://next-intl.dev/docs/getting-started/app-router)). For a business whose public pages compete on Indonesian/English/Russian search terms, locale-in-URL is an SEO instrument, not a refactor vanity.

## Gap table

| Dimension | Nuzantara (measured) | SOTA reference | Gap |
|---|---|---|---|
| Rendering model | 71% client pages, 6 files use `next/headers` | Server-first RSC, deliberate client islands (Vercel checklist) | Large, structural |
| Error/loading boundaries | 87+87+global-error | Per-segment boundaries | **None — at/above SOTA** |
| Auth | Cookie-primary transport, localStorage-only `isAuthenticated()` on 9 client gates; no auth in proxy | Proxy optimistic cookie check + DAL `verifySession()`; client boolean gates explicitly "not recommended" | Critical |
| Design system | 3 layers; deprecated pkg present; core has 10 importers; negative hex-lint only | One system, CI-computed adoption %, objective deprecation | Large |
| Unit testing | 3,860 blocks, colocated, CI-armed | Same shape + network-level mocks (MSW) shared across layers | Small |
| Coverage gating | Flat 20% statements | Ratchet or changed-lines coverage | Medium (theater) |
| E2E | 53 specs, serial `workers:1`, 2 retries | Sharded matrix + blob merge + `fullyParallel` | Medium, mechanical |
| Bundle discipline | Leak-gate (novel), analyzer, warn-only Lighthouse | Hard per-route byte budgets failing PRs (size-limit / LHCI error) | Medium |
| Observability | 3-runtime Sentry but DSN-conditional (can silently vanish); no tunnelRoute | Fail-closed arming check; tunnel; `onRequestError` | Medium, high-stakes |
| RUM | web-vitals → GA4 (silo, no alerts) | Field p75 CWV in the error tool, alerting, release-correlated (Shopify model) | Large |
| a11y | 1 axe spec + 10 LH URLs (hard-fail) | Axe on every e2e navigation; automation ≈57% of issues, manual on top | Large surface gap |
| i18n | Client context, 5 locales × 80KB shipped to all, no locale URLs | Server-resolved messages, per-locale split, `[locale]` SEO routing | Large |
| Deploy verification | live-sentinel proves prod serves the frontend commit (30-min cron) | Deploy orchestration equivalent | **Above typical SOTA** |
| Contract types | OpenAPI → `schema.d.ts` + validators | Same; drift gate in CI | Small (arming unverified) |
| CSP | `unsafe-inline` script-src | Nonce/hash-based strict CSP | Medium |

## Recommendations — reach SOTA

Each sized for one operator + agent fleet; priorities P0 (structural risk) → P2 (compounding quality).

1. **P0 — Kill the auth split-brain.** Replace the 9 page-level `apiClient.isAuthenticated()` gates with (a) an optimistic cookie check in `src/proxy.ts` for the protected `INTERNAL_ROUTES` prefixes (redirect to `/login`, cookie-presence only, per the Next.js auth guide), and (b) a single client `useSession()` probe backed by `/api/auth/profile` (cookie-transported) for UI state. Delete the localStorage read as an auth *decision* (keep it as WebSocket back-compat only). **Acceptance (falsifiable):** an e2e test that logs in, wipes localStorage, and still reaches all 9 gated pages passes; `grep -rn "isAuthenticated()" src/app` returns 0.
2. **P0 — Make Sentry fail-closed.** Add a build-time assert (same pattern as `assert-public-login-bundle.mjs`, which proves the mechanism works) that fails when `VERCEL_ENV=production` and no `NEXT_PUBLIC_SENTRY_DSN`/`SENTRY_DSN` is present, plus `tunnelRoute` and `widenClientFileUpload` per Sentry's hardening guide. **Acceptance:** deleting the DSN env from a preview deploy turns the build red; a thrown test error in prod appears in Sentry with a readable stack.
3. **P0 — Byte budgets that can say no.** Add `size-limit` (or flip `.lighthouserc.json` byte/metric assertions from `warn` to `error`) with per-route budgets seeded from today's measured sizes +5%, PR-comment diff. Start with the 3 revenue routes: visa funnel, portal login, KBLI pages. **Acceptance:** a PR adding a 50KB dependency to the funnel goes red without human eyes.
4. **P1 — Shard Playwright.** `fullyParallel: true`, 4-shard GitHub Actions matrix, blob reports + `merge-reports`. **Acceptance:** e2e wall-clock on PR < 10 minutes with an unchanged pass rate over 20 runs.
5. **P1 — Coverage ratchet instead of the 20% floor.** Record the measured coverage high-water mark in a committed JSON; gate fails if total statements drop >0.5pt below it; agents update the mark upward. **Acceptance:** the gate value tracks measured coverage within 1 point instead of sitting 40+ points below it.
6. **P1 — Axe everywhere it's already driving.** Convert the axe check into a shared Playwright fixture asserted on every page the smoke/e2e suites visit; hard-fail serious/critical. **Acceptance:** axe executes on ≥80% of routes touched by e2e (measured by fixture log), zero serious/critical violations on main.
7. **P1 — One design system, with an adoption number.** Delete `packages/design-system` (nothing imports it; migrate the 3 scripts to read from `packages/core`), declare `@balizero/core` the only kit, and add a CI-computed adoption metric (files importing core ÷ UI files) published as a check summary. Fold mouth's `ui/` primitives into core opportunistically, one component per PR. **Acceptance:** deprecated package gone; adoption % visible on every PR and monotonically rising for 4 consecutive weeks.
8. **P2 — Per-locale code-splitting, then locale routing.** Step 1: dynamic-import locale JSON so a visitor downloads exactly one (~16KB not 80KB). Step 2: migrate the public `(marketing)`/`(blog)`/kbli surfaces to next-intl with `[locale]` segments and hreflang. **Acceptance:** built client chunks contain exactly one locale's messages; localized URLs indexed (Search Console shows hreflang pairs).
9. **P2 — Server-first migration of the public read surface.** The KBLI explorer, blog and marketing pages are read-mostly and already have server data files (`kbli-data.server.ts`): move their pages off `"use client"` route-by-route. **Acceptance:** client-page ratio falls from 71% to <50%; funnel-route First Load JS drops measurably in the budget report from rec 3.
10. **P2 — MSW as the one network contract.** Generate MSW handlers from the existing OpenAPI schema; use them in vitest and Playwright (route interception) alike. **Acceptance:** one handler directory imported by both configs; module-level fetch mocks reduced (grep count) release over release.

## Recommendations — beyond SOTA

1. **Generalize the bundle-leak gate to the whole public surface.** `assert-public-login-bundle.mjs` proves a unique idea: *the built artifact is scanned for secrets-shaped knowledge as a build step*. Extend the deny-by-default API-route scan to every public route's chunks (marketing, blog, kbli, funnel). No sector reference does this route-wide. **Acceptance:** a seeded internal endpoint string in any public chunk fails the build; scan-covered route list = all public routes.
2. **Close the RUM→gate loop.** Nightly agent job reads field CWV (GA4 export or Sentry vitals once rec 2 lands), writes p75 per route to a committed JSON, and *regenerates the Lighthouse/size budgets from field data* — budgets only ever tighten automatically. The fleet, not the operator, keeps budgets honest. **Acceptance:** budget file carries a generated-from-field-data header with a date <7 days old; a route whose field p75 improves gets a stricter budget within a week, verified in git history.
3. **Fleet-native full-surface a11y + visual crawl.** A nightly agent crawls all 158 pages (route manifest is enumerable from the filesystem), runs axe + screenshot diff against the previous night, and files findings as PENDING-ARMS lines instead of a dashboard nobody reads. This out-scales what human-team SOTA does weekly. **Acceptance:** nightly artifact lists per-route axe verdicts for ≥95% of routes; a deliberately-broken contrast token is caught within 24h.
4. **Deploy-probe registry.** Merge the live-sentinel idea with the ASSEMBLY-LINE synthetic-purchase doctrine: every PR that adds a route must also add a one-line probe (URL + expected marker) to a registry the 30-minute sentinel iterates. The sentinel stops proving only "prod serves commit X" and starts proving "every declared surface answers". **Acceptance:** CI fails a PR adding a `page.tsx` without a probe row; sentinel iterates the registry (run log shows N probes = N registry rows).

## §Meta-pattern

The platform's strongest assets are all **antibodies grown from scars**: the live-sentinel (deploy-skip scar), the bundle-leak gate (public-repo secret scars), the un-silenced Sentry plugin comment (hidden token-expiry scar), the CI step arming packages/core tests ("built, never armed" scar). Its weakest points are all **foundations that were never re-derived**: the SPA-in-App-Router rendering model, the localStorage auth boolean, the hand-rolled i18n, three design-system layers. The organism heals better than it grows — reactive quality is beyond SOTA while proactive architecture is behind it. This is the program's shared meta-disease in local form: *the artifact that exists and is announced is presumed to be the thing in force* — a 20% gate presumed to gate, a warn-level Lighthouse presumed to protect performance, a Sentry config presumed armed because the file exists, a design system presumed adopted because the package exists. The cure shape is always the same and this codebase already invented it four times: make the claim measurable in CI and let red mean something.

## §Solo-operatore

Decisions only Zero can take (business calls, spend, risk):

1. **Rendering-migration risk appetite.** Rec "server-first migration" touches live revenue surfaces (funnel, KBLI). Approve route-by-route migration under the ASSEMBLY-LINE ship-dark procedure, or freeze the rendering model and accept the permanent bundle/SEO tax.
2. **Design-system ruling (Legge 5, brand).** Declare `@balizero/core` the single kit and authorize deleting `packages/design-system` — a brand-governance call, since the token pipeline scripts anchor to it.
3. **Locale portfolio.** ru/fr locales cost maintenance and translation drift; whether Russian/French are product-strategic markets (vs en/id/it) is a market decision that sizes the i18n investment.
4. **CI spend.** Playwright sharding ×4 and a nightly 158-page crawl multiply GitHub Actions minutes; approve the runner budget or set a cap.
5. **Observability spend.** Routing RUM into Sentry raises event volume against the plan quota (the fleet memory already records 28% quota discard on the backend project); consolidating projects or raising the plan is a spend decision.
6. **Public WCAG commitment.** Hard-failing serious axe violations effectively commits Bali Zero to WCAG 2.x AA on public surfaces — a legal/brand posture worth stating deliberately, not implicitly.

## Sources

1. Next.js — Production checklist: https://nextjs.org/docs/app/guides/production-checklist
2. Next.js — Authentication guide (sessions, Proxy, DAL): https://nextjs.org/docs/app/guides/authentication
3. Playwright — Test sharding in CI: https://playwright.dev/docs/test-sharding
4. Mock Service Worker — Philosophy: https://mswjs.io/docs/philosophy
5. next-intl — App Router setup: https://next-intl.dev/docs/getting-started/app-router
6. size-limit (per-PR JS budgets): https://github.com/ai/size-limit
7. web.dev — Performance budgets in build tools: https://web.dev/incorporate-performance-budgets-into-your-build-tools/
8. Shopify Engineering — The Vitality of Core Web Vitals: https://shopify.engineering/core-web-vitals
9. Shopify — Web performance dashboard with real user insights: https://performance.shopify.com/blogs/blog/web-performance-dashboard
10. Deque — Automated testing identifies 57% of digital accessibility issues: https://www.deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues/
11. Sentry — Next.js manual setup / production hardening: https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
12. Netguru — Design system metrics (adoption rate): https://www.netguru.com/blog/design-system-metrics

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** Same as F3: the auth split-brain map is already cured upstream. An i18n-payload contradiction inside this file was raised but not settled.
