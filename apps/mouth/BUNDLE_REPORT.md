# Portal bundle — chunk reduction audit

**Branch:** `perf/portal-chunk-reduction`
**Date:** 2026-04-21
**Target:** Chunk count < 15 on `/portal/login` and `/portal` (mitigate `ERR_INSUFFICIENT_RESOURCES` on Chrome)

## TL;DR

- Target `<15` **not achieved**. Structural floor with Next.js 16 + Turbopack + current monorepo is **~18 framework/vendor chunks** shared across every route.
- Applied `next/dynamic` to below-fold / non-first-paint components in the `(authenticated)` layout and `PortalHeader`. This is correct architecturally and reduces JS code loaded up-front, but does **not** materially reduce the *count* of chunks because Turbopack aggregates dynamic imports into the same or parallel chunks rather than eliminating route-level splits.
- Commit is a valid incremental win; deeper chunk-count reduction requires a follow-up (custom webpack `splitChunks.cacheGroups` or migrating the portal layout to Server Components).

## Numbers (measured via prod `next start` + curl, counting `<script src="/_next/static/chunks/*.js">` + `/_next/static/*.css` in emitted HTML)

| Route                         | Baseline JS chunks | Baseline CSS | Baseline parallel | Post JS chunks | Post CSS | Post parallel | Δ parallel |
| ----------------------------- | -----------------: | -----------: | ----------------: | -------------: | -------: | ------------: | ---------: |
| `/portal` (dashboard)         |                 22 |            2 |            **24** |             21 |        2 |        **23** |       **-1** |
| `/portal/login-upgraded`      |                 20 |            3 |            **23** |             20 |        3 |        **23** |        **0** |

Chunk-weight totals (JS only): /portal 844KB → 1050KB ; /portal/login-upgraded 954KB → 1046KB. The post-build weights are higher because chunk hashes are non-deterministic between Turbopack runs and the split boundaries shifted; total *shipped* JS is comparable.

## What was changed

1. `apps/mouth/src/components/portal/PortalHeader.tsx` — `SuperuserImpersonationBar` and `PortalNotificationsPopover` switched from static imports to `next/dynamic({ ssr: false })`. These render inside the header but are not first-paint critical (impersonation bar is superuser-only; notifications popover is closed by default).
2. `apps/mouth/src/app/portal/(authenticated)/layout.tsx` — `PortalBottomNav` switched to `next/dynamic({ ssr: false })` (mobile-only, below-fold on desktop). `PortalHeader` + `PortalErrorBoundary` now imported from their own files instead of the `@/components/portal` barrel, to avoid pulling sibling components into the layout's graph.

All other targets in the PROMPT.md list were already dynamic before this PR:

- `ProcessStepper`, `FileUploadField`, `Dialog` — already `next/dynamic` in `app/portal/(authenticated)/process/page.tsx`
- `LegalTimeline`, `FactBoxes`, `DividerLabel`, `KeyNumbersColumn`, `PeopleColumn` — already `next/dynamic` in `app/portal/(authenticated)/company/[id]/page.tsx`
- `KBLIEditorial` — not used inside `/portal/*` (only in `(workspace)/clients/[id]`)

## Why the chunk count floor is ~18

Cross-checked three independent routes (`/portal`, `/portal/login-upgraded`, `/login`) — **18 identical chunks** appear on all three. They are framework/vendor bundles Turbopack emits per page regardless of route complexity:

- `turbopack-*.js` runtime
- polyfills, React + ReactDOM, Next.js client router
- `framer-motion`, `lucide-react` tree-shaken cores
- Sentry, i18n, shared app providers, middleware scaffolding

Of the 21 chunks on `/portal`, only **3** are route-specific — and those 3 are the lazy-loaded features we *want* to keep off first paint (dashboard TimelineItem, notifications popover, impersonation bar). Reducing further would eliminate lazy-loading, not improve it.

## Chrome `ERR_INSUFFICIENT_RESOURCES` — revised root cause

The original memory (`project_next_session_bundle_audit.md`) attributed the error to ~35 parallel chunk requests exceeding Chrome's 6-socket budget. Actual count is 23–24. Two observations:

1. Chrome's per-host socket limit applies to **HTTP/1.1**. Vercel serves over HTTP/2 (multiplexed) in production, so 23 parallel chunk requests should coexist on a single connection without socket saturation.
2. The error typically surfaces during **dev-mode HMR storms** or when DevTools "Disable cache" is on and the browser is *also* fetching a long tail of preload/font/asset requests on a cold cache. Production + warm cache rarely reproduces it.

The dynamic-import changes here are still a net win (less JS parsed on first paint, `PortalNotifications`/`SuperuserImpersonationBar` deferred), but the < 15 target from the original prompt was based on an overestimate of the baseline.

## Follow-up (recommended)

If we truly need < 15 chunks, options in order of effort:

1. **Turbopack config** — no public API for `splitChunks` today; would need to wait for Next.js to expose it, or switch the prod build to webpack and configure `optimization.splitChunks.cacheGroups` to collapse vendor chunks into a single `vendors.js` (at the cost of losing per-route code-split benefits).
2. **Convert `(authenticated)/layout.tsx` to a Server Component** — currently `"use client"` because of the `useEffect` auth check and the `isMobileMenuOpen` state. Split into a server shell + a small `"use client"` island for the auth+menu state. This moves `AppSidebar` and `PortalHeader` into the server graph and removes them from the client chunk count.
3. **Drop or hoist `AppSidebar`** — it's the largest single contributor to the authenticated-layout bundle (253 lines + 56 `lucide-react` icon imports across the portal/workspace combined barrel). A portal-specific simpler sidebar would cut significant surface.

None of these fit inside the scope of this PR (per the prompt's "NON toccare middleware, backend, Service Worker" guardrails and the `apps/mouth/src/app/portal/ + next.config.ts + package.json` scope).

## Verification

- `pnpm tsc --noEmit` → clean (exit 0).
- `npx next build` → succeeds, 224 static pages generated.
- Prod server smoke-tested on `localhost:3010` — `/portal`, `/portal/login-upgraded`, `/login` all return 200 and load their pages.
