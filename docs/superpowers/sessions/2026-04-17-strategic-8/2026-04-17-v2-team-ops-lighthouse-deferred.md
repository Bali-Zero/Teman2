# Lighthouse audit — deferred (2026-04-17 pro-3)

## Status
**DEFERRED** — requires Vercel preview deploy, which is out of scope for this
session (rules: NO deploy prod, NO PR open, draft only).

## Targets in scope for this sub-plan (04 team-ops)
Only routes added here:
- `https://<preview>/inbox` (target 85+)
- `https://<preview>/analytics/funnel` (target 85+)
- `https://<preview>/clients` with map view selected (target 85+ — Prime 3D is heavy WebGL)

## Out of scope (owned by other sub-plans)
- `balizero.com`, `visa.*`, `/kbli`, `tax.*`, `/property` (public + sub-plan 02)
- `my.*`, `prime.*/proposal/demo-token`, `zantara.*` (sub-plan 03 + others)

## To run after draft PR opens
```bash
npx lighthouse https://<preview>/inbox \
  --output=json --output-path=./inbox.json \
  --only-categories=performance,accessibility,best-practices,seo
npx lighthouse https://<preview>/analytics/funnel \
  --output=json --output-path=./funnel.json \
  --only-categories=performance,accessibility,best-practices,seo
```

## Expected scores
- `/inbox` — pure SSR text + list → 95+
- `/analytics/funnel` — recharts (SVG) → 90+
- `/clients` map view — PrimeMap3D (WebGL + Cesium) → performance < 85 by design;
  accessibility / best-practices / SEO should still be 90+.
