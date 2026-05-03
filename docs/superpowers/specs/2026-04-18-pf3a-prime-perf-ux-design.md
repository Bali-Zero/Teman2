# PF3a — Prime Intelligence 3D: Performance + UX Spec

**Date:** 2026-04-18
**Scope:** `apps/mouth/src/app/prime/` + `apps/mouth/src/components/maps/`
**Branch:** `pro/frontend-prime-perf-ux` (worktree `.worktrees/prime-perf-ux`)
**Deploy target:** `prime.balizero.com` (Vercel, `noindex`)
**Out of scope (deferred to PF3b):** KBLI search/detail/concordance, `kbli-navigator` dedup.

---

## 1. Problem

Prime Intelligence (`/prime` → `PrimeNexusLayout` → `PrimeMap3D`) is the 3D geospatial decision hub for Bali property/business investment. Today it has three blockers:

1. **LCP is bad.** `PrimeMap3D.tsx` (1,179 LOC, client component) is imported **statically** in `PrimeNexusLayout`, so the Google Maps JS API + maps3d library block first paint on every visit. No preconnect, no placeholder, no split.
2. **Firefox is broken silently.** `maps3d` requires Chromium WebGL; Firefox users get either a blank canvas or a crash — no detection, no fallback message.
3. **No state sharing.** URL is static `/prime` regardless of zoom/layers/selected zone — users cannot deep-link a finding, no screenshot-worthy share flow, losing referral potential.

Secondary gaps: no interactive legend, no side-by-side zone comparison.

## 2. Goals (measurable)

- **LCP target:** <3s on desktop (Moto G Power-class baseline), <5s on mobile Chrome. Baseline measured before any code change (artifact: `docs/superpowers/specs/artifacts/2026-04-18-prime-baseline.json`).
- **Firefox:** clear fallback page (not crash). Chromium-on-Android continues to work.
- **URL state:** `prime?lat=…&lng=…&zoom=…&layers=zoneColors,kkop&compareA=…&compareB=…` → shareable, reload-safe, back-button-safe.
- **Legend:** click isolate a zone type, hover highlight, keyboard reachable (ARIA).
- **Compare:** pick zone A, pick zone B, see delta card (zoning type, restrictions, POI count within radius).
- **Zero regressions:** existing Mode Switcher (CRM/INVEST/INTEL), PrimeZantaraChat, ClientMarkerLayer keep working.

## 3. Non-goals (explicit YAGNI)

- Save favorite locations (localStorage) → PF3c.
- Screenshot export via `html2canvas` → PF3c.
- Any backend change to `/api/prime/zoning`.
- Rewriting `PrimeMap3D.tsx` into smaller pieces (1,179 LOC stays, add around it). A full decomposition is a separate project.
- Mobile 2D fallback as a full alternative map — **replaced** by "3D requires Chromium desktop" message on non-supported clients (see §4.2). Scoping mobile 2D is another project.

## 4. Design

### 4.1 Architecture — wrap, don't rewrite

`PrimeMap3D.tsx` (1,179 LOC) stays **unmodified** in this PR except for three surgical changes (legend hook export, URL-state read/write hooks, a11y attrs on existing controls). All new behavior lives in **wrapper components** around it, exactly matching the pattern that `PrimeNexusLayout` already established for mode panels.

New components (all under `apps/mouth/src/components/maps/prime/`):

```
prime/
  PrimeGate.tsx            ← browser-support gate + lazy-load trigger (NEW)
  PrimeLayerLegend.tsx     ← interactive legend panel (NEW)
  PrimeCompareDrawer.tsx   ← side-by-side zone compare drawer (NEW)
  PrimeUrlStateBridge.tsx  ← reads URL → sets state, listens state → writes URL (NEW)
  hooks/
    usePrimeUrlState.ts    ← URLSearchParams serialize/deserialize (NEW)
    useBrowserSupport.ts   ← Chromium vs Firefox vs mobile detection (NEW)
```

Existing files changed:

- `apps/mouth/src/app/prime/page.tsx` — wrap in `<PrimeGate>`.
- `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx` — convert `PrimeMap3D` import to `next/dynamic({ ssr: false })`, mount `PrimeLayerLegend`, `PrimeCompareDrawer`, `PrimeUrlStateBridge`.
- `apps/mouth/src/components/maps/PrimeMap3D.tsx` — expose layer state via new context (not prop drilling); add ARIA labels on existing controls; accept optional initial state from URL bridge. No logic changes.
- `apps/mouth/src/contexts/PrimeNexusContext.tsx` — extend with `layers`, `selectedZoneA`, `selectedZoneB`, setters.

### 4.2 Performance — split, preconnect, placeholder

**Split.** `PrimeNexusLayout` imports `PrimeMap3D` via:

```ts
const PrimeMap3D = dynamic(() => import('@/components/maps/PrimeMap3D'), {
  ssr: false,
  loading: () => <PrimeMapSkeleton />,
});
```

Savings: the ~1,179-LOC component + its transitive `maps3d` loader move out of the initial bundle. Skeleton renders first (small LCP element, optimizable).

**Preconnect.** In `apps/mouth/src/app/layout.tsx` (or scoped via `prime/layout.tsx` if the existing root layout cannot accept it), add:

```html
<link rel="preconnect" href="https://maps.googleapis.com" crossorigin />
<link rel="dns-prefetch" href="https://maps.gstatic.com" />
```

Scope: only on `/prime/*` routes to avoid polluting other pages.

**Skeleton.** `PrimeMapSkeleton` is a pre-blurred PNG (~30KB) of Bali at default view + shimmer overlay. Becomes the LCP element. Stored in `public/prime/map-skeleton.webp` (served with `cache-control: public, max-age=31536000, immutable`).

**Gate.** On Firefox or any non-Chromium UA, `PrimeGate` short-circuits the dynamic import entirely. User sees a static "Prime requires Chrome/Edge/Safari Technology Preview" page with browser logos and a "Continue anyway" escape hatch (preserves the existing undocumented behavior for power users who want to try).

### 4.3 Browser detection (`useBrowserSupport`)

Pure client-side, runs in `useEffect`:

- `chromium` = `navigator.userAgentData?.brands` includes `Chromium` OR (legacy: `navigator.userAgent` matches `Chrome|Edg` and not `Firefox|Gecko`).
- `webgl2` = can construct `document.createElement('canvas').getContext('webgl2')` (non-null).
- `isMobile` = `matchMedia('(pointer:coarse) and (max-width: 768px)')`.
- `supported` = `chromium && webgl2`.

Returns `{ supported, chromium, webgl2, isMobile, loading }`. `loading: true` on first render (SSR safety), never blocks hydration.

### 4.4 URL state (`usePrimeUrlState`)

API-shaped URL params, all optional, all validated with Zod (already in deps):

```ts
const PrimeUrlState = z.object({
  lat: z.coerce.number().min(-9).max(-8).optional(), // Bali bounds
  lng: z.coerce.number().min(114).max(116).optional(),
  zoom: z.coerce.number().min(6).max(22).optional(),
  layers: z.string().optional(), // csv: zoneColors,kkop,lp2b,…
  compareA: z.string().optional(), // zone id
  compareB: z.string().optional(),
});
```

- **Read once on mount** via `useSearchParams()` (already `'use client'`).
- **Write debounced** (400ms) via `router.replace(…, { scroll: false })` on state change — avoids URL churn during pan/zoom.
- Invalid params silently dropped (do not throw, do not reset other state).
- Serialization utility in `usePrimeUrlState.ts`, unit-tested.

Bridge component `PrimeUrlStateBridge` is headless (`return null`), owns the URL↔context sync. Placed once in `PrimeNexusLayout`.

### 4.5 Legend (`PrimeLayerLegend`)

Floating card, top-left (does not conflict with top-right ModeSwitcher).

- One row per layer in `MapLayers`: zoneColors, extrusion, kkop, lp2b, tsunami, floodRisk, templeBuffer.
- Each row: color swatch (from `ZONE_COLORS`/`CATEGORY_COLORS`, already exported from `mapConstants.ts`), label (i18n), checkbox (toggle on/off, syncs to existing `setLayers` in PrimeMap3D).
- Click label → isolate (only this layer on), shift+click → additive.
- Hover row → highlight matching polygons by raising opacity (existing zone polygon refs already exist in `PrimeMap3D`, exposed via context).
- Keyboard: each row is a `<button role="switch">`, tab-reachable, space/enter toggles.
- Collapsible (remembers state in localStorage `prime.legend.collapsed`).

### 4.6 Compare drawer (`PrimeCompareDrawer`)

- Trigger: right-click on a zone polygon → "Add to compare" menu item. First click → slot A, second → slot B (replaces A if both full). Also accessible via "Compare" button that exposes current selections.
- Drawer slides in from right, 320px wide, pushes sidebar if present or overlays on mobile.
- Each card: zone name, type, restricted flag, overlap with KKOP/LP2B/temple buffer, POI count (reusing existing `/api/prime/zoning` — no backend change, client-computes set difference).
- Delta section: highlights fields where A ≠ B.
- "Clear" buttons per slot. "Share" button → copies current URL (which now encodes `compareA`/`compareB`).
- a11y: drawer is `role="dialog"` `aria-label="Zone comparison"`, ESC closes.

### 4.7 Data flow

```
URL (search params)
   │
   ▼
PrimeUrlStateBridge ──── reads on mount ────► PrimeNexusContext (layers, compareA, compareB)
       ▲                                              │
       │ debounced write                              ▼
       └────── listens setState ◄─── PrimeLayerLegend / PrimeCompareDrawer / PrimeMap3D
                                              │
                                              ▼
                                     PrimeMap3D renders polygons / cards
```

### 4.8 Error handling

- **Google Maps script fails to load** (network, CSP, blocked by extension): `PrimeMap3D` already has a loaded state; we extend to a timeout (15s) → show error card "Could not load map. Check connection or ad blocker." with retry button.
- **`/api/prime/zoning` fails on click**: existing error toast stays; compare slot shows "Data unavailable" placeholder, slot stays selected so the user can retry by reselecting.
- **Invalid URL state**: silently dropped (see §4.4). No error surfaced — URL deep-links are best-effort.
- **Firefox/non-Chromium**: gated at `PrimeGate`, never reaches `PrimeMap3D`.

### 4.9 Testing

- **Vitest (unit)** — `usePrimeUrlState`, `useBrowserSupport`, legend isolate logic, compare delta calculator.
- **Playwright (e2e)** Chromium project:
  - `prime.spec.ts`: load `/prime?lat=-8.65&lng=115.21&zoom=15&layers=zoneColors,kkop` → assert map loaded, these two layers on, others off, zoom applied.
  - `prime-compare.spec.ts`: right-click zone, right-click another, assert drawer opens with two cards and delta section.
  - `prime-firefox.spec.ts` (Firefox project in `playwright.config.ts`): load `/prime` → assert gate message shown, map not loaded.
- **Visual regression**: 3 screenshots (desktop fresh load, legend expanded, compare drawer open).
- **Lighthouse assertion** (new script in `apps/mouth/scripts/`): run Lighthouse headless against local preview, fail if LCP > 3500ms desktop or > 5000ms mobile.

### 4.10 Verification before completion

Per `superpowers:verification-before-completion`:

1. `npm run typecheck` green.
2. `npm run lint` green.
3. `npm run test` (Vitest) green.
4. `npm run test:e2e -- --grep Prime` green.
5. `npm run build` green and bundle analyzer confirms `PrimeMap3D` split into its own chunk.
6. Manual Chrome desktop: LCP baseline delta recorded.
7. Manual Chrome mobile viewport: LCP baseline delta recorded.
8. Manual Firefox: gate message appears, no crash, no console error other than intentional one.
9. Screenshot artifacts in `docs/superpowers/specs/artifacts/2026-04-18-prime-after/`.

## 5. Constraints / hard rules

- Maps API key `AIzaSyCWPZb1_aSV_NVvS9ZSR0Mlq9El8qO8uLQ` unchanged (note: char 21 is lowercase `l`, not digit `1` — verified against production `/prime` page load).
- Backend `/api/prime/zoning` contract unchanged.
- `packages/core/styles/bz-tokens.css` read-only — all new components use existing `--bz-*` tokens.
- `packages/core/components/BZLogo.tsx` untouched.
- i18n: legend labels via `next-intl`/existing system (check `apps/mouth/src/i18n/` — if absent, ship EN-only and add TODO).
- Deploy via `git push origin main`, not `vercel --prod`, to pick up any `NEXT_PUBLIC_*` (none currently needed).

## 6. Risks

| Risk                                                                        | Likelihood | Mitigation                                                                                       |
| --------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------ |
| `next/dynamic` of `PrimeMap3D` breaks an existing ref or context dependency | M          | Small step — do dynamic split first, ship, verify regression tests, then layer on legend/compare |
| Preconnect in root layout affects other pages' budget                       | L          | Scope via `apps/mouth/src/app/prime/layout.tsx` only                                             |
| `useSearchParams` triggers client-side suspense boundary issue              | M          | Wrap `PrimeNexusLayout` in `<Suspense>` (Next.js 16 requirement for `useSearchParams` in CSR)    |
| Firefox gate too aggressive (blocks Chromium-based Firefox forks)           | L          | Gate is advisory — "Continue anyway" escape hatch                                                |
| Lighthouse CI adds flakiness                                                | M          | Thresholds are p50 targets, keep as warning not hard block initially                             |

## 7. Build sequence

1. Worktree + baseline Lighthouse (desktop + mobile Chrome + Firefox screenshots).
2. `useBrowserSupport` hook + unit tests.
3. `PrimeGate` component + Firefox gate integration.
4. `PrimeMap3D` dynamic split + skeleton + preconnect.
5. Re-measure Lighthouse — gate for next step (LCP delta must be positive, else investigate).
6. Extend `PrimeNexusContext` with layers/compare state.
7. `usePrimeUrlState` + `PrimeUrlStateBridge` + unit tests.
8. `PrimeLayerLegend` + unit tests + a11y audit.
9. `PrimeCompareDrawer` + unit tests.
10. Playwright e2e suite.
11. Final Lighthouse + screenshot artifacts + PR.

## 8. PR

Branch: `pro/frontend-prime-perf-ux`
Title: `feat(prime): LCP split + Firefox gate + URL state + interactive legend + compare drawer`
Labels: `frontend`, `performance`, `a11y`.
Reviewers: request when ready.
