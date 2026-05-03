# Frontend Performance SOTA — SSG Massivo (1.5K+ pagine, 5 lingue, Vercel)

> **Date:** 2026-04-14 | **App:** `apps/mouth/` | **Machine:** Air (build audit) | **Stack:** Next.js 16.2.0, React 19.2.4, Turbopack, Vercel

---

## 1. Current State Audit — Numeri Reali

### 1.1 Build Profile

| Metric | Value |
|--------|-------|
| **Next.js** | 16.2.0 (Turbopack default) |
| **React** | 19.2.4 |
| **Build time** | ~38s total (compile 15.2s + TS check 18.7s + SSG 3.2s) |
| **Pages generated** | 196 total (120 static, 76 SSG w/ params) |
| **Dynamic routes** | 37 (API routes, parameterized pages) |
| **Source files** | 877 .tsx/.ts |
| **MDX articles** | 2,825 (14 categories, English base + locale variants) |
| **KBLI codes in data** | 1,563 |
| **KBLI pages pre-built** | 50 (ISR `dynamicParams: true`, revalidate 1 week) |

### 1.2 Bundle Size

| Asset | Size |
|-------|------|
| `.next/` total | 164 MB |
| `.next/static/chunks/` | 6.1 MB (242 files) |
| `.next/static/media/` | 636 KB |
| `public/` total | **368 MB** |
| `public/static/news/` | 109 MB (413 files) |
| `public/static/insights/` | 68 MB (408 files) |
| `public/static/blog/` | 66 MB (37 files) |
| `public/static/image_art/` | 45 MB (16 files) |
| `public/static/team/` | 43 MB (22 files) |

**Top 5 JS chunks:** 392KB, 228KB (Sentry Replay/rrweb), 208KB, 128KB (Sentry core), 120KB.

### 1.3 "use client" Surface

| Category | Count |
|----------|-------|
| **Total "use client" files** | 209 / 877 (23.8%) |
| Pages (page.tsx) with "use client" | 42 / 101 |
| Layouts with "use client" | 6 / 18 |
| Unnecessary "use client" (confirmed) | 2 pages (zero client deps) |
| Refactorable (thin client wrapper) | 5 pages |

### 1.4 Image Inventory

| Format | Count | Notes |
|--------|-------|-------|
| .jpg | 833 | ~213 MB |
| .png | 95 | ~138 MB, includes 19 MB team photos |
| .webp | 1 | Single file |
| .avif | 0 | Zero pre-converted |
| **Total** | 934 | 354 MB |

**Largest files:** `team/adit.png` (19.3 MB, 1024x1024), `team/dea.png` (19.0 MB), 7 `image_art/` files at 3-8 MB each.

### 1.5 Sentry Bundle Cost

| Component | Size |
|-----------|------|
| Replay integration (rrweb) | 228 KB |
| Core SDK | 128 KB |
| Tracing | 52 KB |
| Init + misc | 48 KB |
| **Total client-side** | **~456 KB** |

Session Replay enabled at 10% session sample, 100% error sample. `maskAllText: true`, `blockAllMedia: true`.

### 1.6 Third-Party Scripts

| Script | Loading | Blocking? |
|--------|---------|-----------|
| Google Fonts CSS (DM Serif, Inter, JetBrains) | `<link>` in homepage body | **YES** |
| Geist / Geist_Mono (next/font) | preload, swap | No |
| Google Analytics (GA4) | afterInteractive | No |
| Service Worker | afterInteractive | No |
| Sentry (~456 KB) | async chunks | No |

**No chat widgets, no GTM, no Hotjar.** Clean third-party footprint outside of Sentry.

### 1.7 Fonts

| Font | Where | Method |
|------|-------|--------|
| Geist (sans) | Root layout | `next/font/google`, preload, swap |
| Geist_Mono | Root layout | `next/font/google`, preload, swap |
| League_Spartan | Book layout | `next/font/google` |
| Montserrat | Book + KBLI layouts | `next/font/google` |
| Cormorant_Garamond | Portal login | `next/font/google` |
| DM Serif Display | Homepage only | Raw `<link>` CSS (**render-blocking**) |
| Inter | Homepage only | Raw `<link>` CSS (**render-blocking**) |
| JetBrains Mono | Homepage only | Raw `<link>` CSS (**render-blocking**) |

**8 font families total.** 5 use optimized `next/font`, 3 use legacy CSS `<link>` (homepage only).

### 1.8 i18n

- **5 locales:** en (default), id, it, ru, fr
- **Implementation:** Custom client-side (`React.createContext` + `useTranslation` hook)
- **Bundle:** All 5 locale JSONs statically imported (~56 KB uncompressed, all shipped to every user)
- **Routing:** No URL-based locale routing (single URL, localStorage toggle)
- **SEO:** `hreflang` tags point to same URL (no locale-specific URLs = limited SEO value)

### 1.9 Middleware

- **File:** `src/middleware.ts` — 448 lines, Edge Runtime
- **Handles:** 8 domains/subdomains, bot classification, CORS/RSC protection, redirects, rewrites
- **Deprecated:** Next.js 16 warns to rename to `proxy.ts`
- **Performance:** Pure string matching, no external calls — <1ms execution

---

## 2. Gap Analysis — 15 Criteri SOTA

| # | Criterion | Current State | SOTA (2026) | Gap | Priority |
|---|-----------|--------------|-------------|-----|----------|
| 1 | **PPR (Partial Prerendering)** | Not enabled. Comment says "Next.js 16 handles automatically" — incorrect. | `cacheComponents: true` in next.config.ts enables PPR + `use cache`. Static shell + dynamic streaming holes. | **HIGH** — blog layout forces all children client-side, PPR would allow static shell + streaming | P1 |
| 2 | **ISR Strategy** | KBLI: 50 pre-built + ISR 1 week. Blog: `unstable_cache` 60s. | `revalidate: false` + on-demand `revalidateTag('kbli')` for static corpus. PPR for mixed pages. | **MEDIUM** — current ISR works but over-revalidates 1563 pages weekly for data that changes yearly | P2 |
| 3 | **SSG Coverage** | 50/1563 KBLI pre-built (3.2%). kbli-navigator pre-builds all 1563 separately. | Pre-build top-traffic pages, ISR rest. Consolidate into single app. | **HIGH** — duplicate app, duplicate build, duplicate deps | P3 |
| 4 | **Client JS Budget** | 6.1 MB chunks, 456 KB Sentry, 392 KB largest chunk. No CI budget enforcement. | <200 KB gzipped first-load per route. `size-limit` in CI. | **HIGH** — no regression detection | P1 |
| 5 | **RSC Adoption** | 209/877 files "use client" (24%). 2 pages unnecessarily client, 6 layouts force children client. | Push "use client" to leaves. Server Component layouts with client islands. | **HIGH** — blog layout (544 lines) forces entire public site client-side | P1 |
| 6 | **Image Optimization** | 934 images, 354 MB, 833 JPG + 95 PNG, zero AVIF. Homepage uses 8 raw `<img>` bypassing optimization. Team photos 19 MB each. | All images through `next/image`. AVIF/WebP served. Source images compressed. LCP image with `priority`. | **CRITICAL** — 368 MB public/, homepage LCP unoptimized | P0 |
| 7 | **Font Loading** | 8 families, 5 via next/font (good), 3 via raw CSS `<link>` (render-blocking homepage). | All fonts via `next/font`. Subset to used glyphs. Max 2-3 families. | **HIGH** — render-blocking fonts on homepage | P1 |
| 8 | **Search (KBLI corpus)** | Route-based lookup only. No typeahead, no fuzzy search across 1563 codes. | Pagefind build-time index: ~15 KB JS + WASM lazy, chunk-loaded index. | **MEDIUM** — functional but poor UX for 1563-item corpus | P2 |
| 9 | **i18n** | Custom client-side, all 5 locales bundled (~56 KB), no URL routing, limited SEO. | `next-intl`: URL sub-paths, bundle splitting per locale, RSC-compatible, proper hreflang. | **MEDIUM** — works but no SEO benefit, wastes ~44 KB on unused locales | P3 |
| 10 | **Web Vitals Monitoring** | web-vitals → GA4 events. No per-route dashboard. No CI regression detection. | Vercel Speed Insights (free, ~1 KB) + GA4. Per-deployment comparison. | **LOW** — data exists but hard to act on | P2 |
| 11 | **Bundle Budget CI** | `@next/bundle-analyzer` available but manual. No CI enforcement. | `size-limit` + GitHub Action. PR comments with size diff. Fail on regression >5 KB. | **HIGH** — silent regressions possible | P1 |
| 12 | **Streaming/Suspense** | 3 files use `<Suspense>`. 80 loading.tsx with good skeletons. | Suspense boundaries around data-fetching sections for streaming SSR. | **LOW** — ISR pages benefit less from streaming | P3 |
| 13 | **Sentry Overhead** | 456 KB client JS (228 KB replay). 10% session replay. | Disable replay or lazy-load it. ~200 KB savings. Or switch to Vercel Speed Insights for RUM. | **MEDIUM** — 228 KB for replay that samples 10% | P2 |
| 14 | **Content Pipeline** | MOCK_ARTICLES (62 items) as fallback. Backend API + MDX hybrid with `unstable_cache`. | Single source of truth. Eliminate MOCK_ARTICLES. MDX auto-discovery buildtime. | **LOW** — fallback works, but dead weight and source of confusion | P3 |
| 15 | **Middleware → Proxy** | `middleware.ts` (448 lines) — deprecated in Next.js 16. | Rename to `proxy.ts`, rename export to `proxy()`. Codemod: `npx @next/codemod middleware-to-proxy .` | **LOW** — functional, just generates build warning | P3 |

---

## 3. Roadmap — 4 Fasi

### Fase 0 — Quick Wins Critici (1-2 giorni)

**Obiettivo:** eliminare i problemi piu' visibili senza rischi architetturali.

#### 0.1 Homepage Font Fix
**Problema:** 3 Google Fonts caricate via raw `<link>` CSS = render-blocking LCP.
**Fix:** Migrare `DM Serif Display`, `Inter`, `JetBrains Mono` a `next/font/google` nel layout marketing.
```tsx
// src/app/(marketing)/layout.tsx
import { DM_Serif_Display, Inter, JetBrains_Mono } from 'next/font/google';
```
**Impatto:** Eliminazione render-blocking resources su homepage. TTFB → FCP gap ridotto.

#### 0.2 Homepage Image Migration
**Problema:** 8 raw `<img>` tags sulla homepage, incluso logo 949 KB mostrato a 92x92 px.
**Fix:** Sostituire `<img>` con `<Image>` da `next/image`, aggiungere `priority` su LCP hero image.
**Impatto:** Auto AVIF/WebP, dimensioni corrette, LCP improvement.

#### 0.3 Team Photo Compression
**Problema:** `team/adit.png` (19.3 MB) e `team/dea.png` (19.0 MB) sono PNG 1024x1024 non compressi.
**Fix:** Converti a WebP/AVIF con quality 85 e max 512x512 (dimensione di display effettiva).
```bash
for f in apps/mouth/public/static/team/*.png; do
  sharp "$f" -o "${f%.png}.webp" --resize 512 512 --quality 85
done
```
**Impatto:** ~38 MB → ~200 KB.

#### 0.4 Unnecessary "use client" Removal
**Problema:** `edge/page.tsx` e `(workspace)/intelligence/page.tsx` hanno "use client" senza motivo.
**Fix:** Rimuovere `"use client"` da entrambi.
**Impatto:** Queste pagine diventano Server Components, zero client JS.

#### 0.5 Vercel Speed Insights
**Fix:** Aggiungere `<SpeedInsights />` al root layout.
```bash
pnpm add @vercel/speed-insights
```
```tsx
// src/app/layout.tsx
import { SpeedInsights } from '@vercel/speed-insights/next';
// In JSX: <SpeedInsights />
```
**Impatto:** RUM gratis con breakdown per route e per deployment. ~1 KB bundle.

---

### Fase 1 — Performance Architecture (1-2 settimane)

#### 1.1 PPR Activation
**Cosa:** Abilitare `cacheComponents: true` in `next.config.ts`.
```diff
- // Partial Prerendering - Next.js 16 handles this automatically
+ cacheComponents: true,
```
**Rollout graduale:**
1. Abilitare globalmente
2. Blog layout: estrarre nav/footer interattivi in client components, rendere il layout Server Component
3. I `{children}` delle route blog diventano streamabili

**Impatto atteso:** Static shell istantanea per tutte le pagine pubbliche. Dynamic content (nav, search, i18n) streamed in holes.

#### 1.2 Blog Layout Refactor (Highest Impact RSC Fix)
**Problema:** `(blog)/layout.tsx` (544 righe, "use client") forza TUTTO il sito pubblico client-side: homepage, /visas, /business, /services, /team, /contact, tutti gli articoli.

**Fix architetturale:**
```
PRIMA:
  (blog)/layout.tsx  ["use client" — 544 righe]
    └── children (tutti client-side)

DOPO:
  (blog)/layout.tsx  [Server Component]
    ├── <BlogNav />      ["use client" — nav interattiva, search, i18n]
    ├── {children}        [Server Component — streamabile]
    └── <BlogFooter />   ["use client" — interattivo se necessario]
```

**Procedura:**
1. Estrarre l'header/nav in `components/blog/BlogNav.tsx` con "use client"
2. Estrarre il footer in `components/blog/BlogFooter.tsx`
3. Rendere `(blog)/layout.tsx` un Server Component che compone i pezzi
4. I `children` (tutte le pagine blog) diventano Server Components candidati

**Impatto:** Il sito pubblico intero (la parte piu' visitata) passa da full-client a server-first. LCP, TTI, JS bundle drasticamente ridotti per visitatori freddi.

#### 1.3 ISR Optimization per KBLI
**Cambio:**
```diff
- export const revalidate = 604800; // 1 week
+ export const revalidate = false; // Fully static, on-demand revalidation only
```
Aggiungere endpoint admin per trigger on-demand:
```typescript
// app/api/revalidate/kbli/route.ts
import { revalidateTag } from 'next/cache';
export async function POST(request: Request) {
  const { secret } = await request.json();
  if (secret !== process.env.REVALIDATION_SECRET) return Response.json({ error: 'Invalid' }, { status: 401 });
  revalidateTag('kbli');
  return Response.json({ revalidated: true });
}
```
**Impatto:** Zero revalidation overhead per 1563 pagine che cambiano forse 1x/anno. Trigger manuale quando KBLI dataset viene aggiornato.

#### 1.4 Sentry Replay Lazy Loading
**Problema:** Replay integration (228 KB) caricata sempre, attiva su 10% sessioni.
**Fix:** Lazy-load replay solo quando attivato:
```typescript
// sentry.client.config.ts
Sentry.init({
  integrations: (defaultIntegrations) => {
    return defaultIntegrations.filter(i => i.name !== 'Replay');
  },
  // Load replay lazily
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
});

// Carica replay on-demand (Sentry 8+ lo supporta nativamente)
if (typeof window !== 'undefined') {
  Sentry.lazyLoadIntegration('replayIntegration').then(() => {
    // Replay loaded only when needed
  });
}
```
**Impatto:** -228 KB dal critical path. Replay caricato solo per il 10% di sessioni campionate.

#### 1.5 Bundle Budget CI
**Setup:**
```json
// apps/mouth/package.json
{
  "size-limit": [
    { "path": ".next/static/chunks/main-*.js", "limit": "120 kB", "gzip": true },
    { "path": ".next/static/chunks/app/layout-*.js", "limit": "80 kB", "gzip": true },
    { "path": ".next/static/**/*.js", "limit": "350 kB", "gzip": true }
  ]
}
```
```yaml
# .github/workflows/bundle-budget.yml
- uses: andresz1/size-limit-action@v2
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    directory: apps/mouth
```
**Impatto:** Ogni PR mostra diff di bundle size. Build fallisce su regressione >5 KB.

---

### Fase 2 — Consolidation (2-3 settimane)

#### 2.1 kbli-navigator Merge Decision

**Stato attuale:**
- `apps/kbli-navigator/`: app Next.js separata, port 3001, genera 1563 pagine SSG
- `apps/mouth/`: genera 50 KBLI pagine con ISR
- Codice duplicato: `kbli-data.ts`, `kbli-types.ts`, `kbli-english.ts`, `kbli-gold-codes.ts`, `kbli-search.ts`, tutti i componenti KBLI
- Dati duplicati: lo stesso JSON letto da path diversi (kbli-navigator non ha nemmeno il file, usa fallback a path relativo)
- Deploy separati: Vercel (mouth) + potenzialmente Netlify/Vercel (kbli-navigator)

**Raccomandazione: MERGE in mouth.**

**Piano incrementale:**
1. Muovere i componenti KBLI unici da `kbli-navigator/` a `mouth/src/components/kbli/`
2. Rimuovere `generateStaticParams().slice(0, 50)` — pre-build i top 200-300 codici per traffico
3. Mantenere ISR `dynamicParams: true` per il resto
4. Aggiungere Pagefind search (vedi 2.2)
5. Eliminare `apps/kbli-navigator/`
6. Rimuovere `public/kbli-navigator/` (2.9 MB)

**Trade-off:**
- PRO: una sola app, un solo deploy, deps condivise, search unificata
- CON: build mouth leggermente piu' lungo (ma ISR mitiga — solo top-N pre-built)

#### 2.2 Pagefind Search Integration
**Setup:**
```json
// package.json
"postbuild": "npx pagefind --site .next/server/app --output-path public/pagefind"
```
```tsx
// src/components/kbli/KBLISearch.tsx
'use client';
import { useEffect, useRef, useState } from 'react';

export function KBLISearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const pagefind = useRef(null);

  useEffect(() => {
    async function load() {
      pagefind.current = await import(/* webpackIgnore: true */ '/pagefind/pagefind.js');
      await pagefind.current.init();
    }
    load();
  }, []);

  async function search(q: string) {
    setQuery(q);
    if (!pagefind.current || !q) { setResults([]); return; }
    const { results: raw } = await pagefind.current.search(q);
    const loaded = await Promise.all(raw.slice(0, 10).map(r => r.data()));
    setResults(loaded);
  }

  return (/* search UI */);
}
```
**Impatto:** Full-text fuzzy search su 1563+ pagine KBLI. ~15 KB JS + ~200 KB WASM (lazy). Index chunks on-demand (~100-300 KB per query).

#### 2.3 i18n Bundle Splitting
**Quick fix senza next-intl migration:**
```typescript
// src/i18n/index.tsx — dynamic import per locale
const localeLoaders = {
  en: () => import('./locales/en.json'),
  id: () => import('./locales/id.json'),
  it: () => import('./locales/it.json'),
  ru: () => import('./locales/ru.json'),
  fr: () => import('./locales/fr.json'),
};

// In provider: load only active locale
const messages = await localeLoaders[locale]();
```
**Impatto:** -44 KB (4 lingue non usate) dal bundle iniziale. Ogni utente carica solo la sua lingua (~10-14 KB).

---

### Fase 3 — i18n Evolution (1-2 settimane, se ROI positivo)

#### 3.1 next-intl Migration Assessment

**Stato attuale:** Custom i18n, localStorage-based, no URL routing, no SEO benefit.

**Cosa darebbe next-intl:**
- URL sub-paths: `/it/kbli/47111` — SEO hreflang funzionante
- Bundle splitting nativo per locale
- RSC-compatible (`getTranslations()` in Server Components — no "use client" per i18n)
- Middleware/proxy integration per locale detection

**Costo di migrazione:**
- Ristrutturare `src/app/` sotto `[locale]/` segment
- Sostituire `useTranslation()` con `useTranslations()` (next-intl API)
- Creare `proxy.ts` per locale routing
- 258 chiavi di traduzione x 5 lingue = relativamente piccolo

**Decisione:** Valutare ROI dopo aver misurato traffico per lingua su GA4. Se >20% traffico e' non-English, migrare. Se <5%, il custom i18n e' sufficiente.

#### 3.2 Middleware → Proxy Rename
```bash
npx @next/codemod@latest middleware-to-proxy .
```
O manuale: rinominare `middleware.ts` → `proxy.ts`, `export function middleware` → `export function proxy`.

---

## 4. Bundle Budget Proposal

### Per-Route Targets

| Route Category | First-Load JS Target (gzipped) | Current Estimate | Notes |
|---------------|-------------------------------|-----------------|-------|
| `/` (homepage) | < 150 KB | ~300 KB+ (Sentry, fonts, inline CSS) | Highest traffic, needs most optimization |
| `/kbli/[code]` | < 100 KB | ~120 KB (mostly static) | SSG, minimal client JS |
| `/visas`, `/business` (blog) | < 120 KB | ~250 KB (blog layout forces client) | **Biggest win after layout refactor** |
| `[category]/[slug]` (articles) | < 100 KB | ~220 KB | Same layout issue |
| `/kbli` (explorer) | < 150 KB | ~180 KB | Search widget adds JS |
| Workspace pages | < 250 KB | ~300 KB | Authenticated, less critical |
| Portal pages | < 200 KB | ~250 KB | Authenticated |

### CI Enforcement

```json
{
  "size-limit": [
    { "name": "Root layout JS", "path": ".next/static/chunks/app/layout-*.js", "limit": "80 kB", "gzip": true },
    { "name": "Blog layout JS", "path": ".next/static/chunks/app/(blog)/layout-*.js", "limit": "100 kB", "gzip": true },
    { "name": "Total static JS", "path": ".next/static/**/*.js", "limit": "400 kB", "gzip": true },
    { "name": "Largest chunk", "path": ".next/static/chunks/*.js", "limit": "200 kB", "gzip": true }
  ]
}
```

---

## 5. RUM Dashboard Design

### Data Flow

```
Browser                     Vercel                    GA4
  │                           │                        │
  ├─ web-vitals ──────────> gtag() ──────────────────> GA4 Property G-S3H2M6VXWT
  │                           │                        │
  ├─ @vercel/speed-insights ──> Vercel Dashboard       │
  │   (NEW, ~1 KB)            │ (per-route, per-deploy)│
  │                           │                        │
  └─ Sentry Performance ────> Sentry Dashboard         │
      (10% sample)            (errors, traces)         │
```

### Grafici Proposti (admin-dashboard o Vercel Dashboard)

1. **LCP per route template** — bar chart, evidenzia route >2.5s
2. **CLS distribution** — histogram, target <0.1
3. **INP per interaction type** — form submit, navigation, search
4. **First-load JS per deployment** — trend line, alert on regression
5. **TTFB by region** — map/table (Bali users vs EU vs US)

### Raccomandazione

**Non costruire dashboard custom.** Vercel Speed Insights (free tier, 5K data points/month) + GA4 (gia' configurato) coprono il 95% dei casi. Sentry copre error tracking. Un dashboard custom in admin-dashboard costerebbe settimane di sviluppo per valore marginale.

**Se serve un custom view:** esporre `/api/admin/performance` che aggrega da GA4 Data API, rendere come widget in admin-dashboard. Ma solo dopo aver verificato che i dati Vercel+GA4 non bastano.

---

## 6. Decisioni Aperte

### 6.1 PPR: Attivare Ora o Aspettare?
- **Pro ora:** `cacheComponents: true` e' stable in Next.js 16. Il blog layout refactor (1.2) e' il prerequisito principale. Low risk su route SSG pure.
- **Pro aspettare:** Testare prima su staging. PPR + Sentry wrapping non testato nel nostro setup.
- **Raccomandazione:** Attivare in Fase 1, dopo blog layout refactor. Testare su preview deploy prima di main.

### 6.2 kbli-navigator: Merge Si/No?
- **Pro merge:** Elimina duplicazione (6+ file duplicati, deps duplicate, build separato). Un solo searchable corpus. Maintenance dimezzata.
- **Pro tenere separato:** Deploy indipendente, failure isolation.
- **Raccomandazione:** **Merge.** La failure isolation non giustifica il costo di duplicazione. kbli-navigator non ha nemmeno il data file corretto (fallback a path relativo fragile). Il redirect `/kbli-navigator → /kbli` gia' in place conferma la direzione.

### 6.3 Sentry: Tenere, Ridurre, o Sostituire?
- **Tenere (ridotto):** Disabilitare Session Replay (- 228 KB). Mantenere error tracking + traces al 10%. Costo bundle: ~228 KB → 0 per replay, ~228 KB residui per core.
- **Sostituire con Vercel:** Speed Insights per RUM (~1 KB). Ma perde error tracking dettagliato.
- **Raccomandazione:** **Tenere ridotto.** Lazy-load replay (Fase 1.4). Speed Insights in aggiunta per RUM (Fase 0.5). Sentry rimane per error tracking — non c'e' alternativa piu' leggera con lo stesso livello di dettaglio.

### 6.4 next-intl Migration: Ora o Mai?
- **Dipende da:** Percentuale traffico non-English. Se <5%, custom i18n e' adeguato. Se >20%, la SEO hreflang di next-intl giustifica la migrazione.
- **Check:** GA4 → Audience → Language breakdown.
- **Raccomandazione:** **Fase 3, condizionale.** Prima misurare. Il quick-fix bundle splitting (Fase 2.3) cattura il beneficio di performance senza la migrazione completa.

### 6.5 MOCK_ARTICLES: Eliminare?
- 62 articoli hardcoded in `NewsPageClient.tsx` come fallback.
- Il backend API + MDX pipeline e' la source of truth.
- **Raccomandazione:** Ridurre a 3-5 items (loading state), non 62. O eliminare se il backend e' stabile.

---

## 7. Appendice — Script di Audit

### A.1 Find Unnecessary "use client"
```bash
#!/bin/bash
# find-unnecessary-use-client.sh
# Flags files with "use client" that don't use React hooks or browser APIs
cd apps/mouth

for f in $(grep -rl '"use client"' src/ --include='*.tsx' --include='*.ts'); do
  HOOKS=$(grep -cE 'use(State|Effect|Ref|Callback|Memo|Context|Reducer|LayoutEffect|ImperativeHandle|SyncExternalStore|Transition|DeferredValue|Router|Pathname|SearchParams|Params|Translation)' "$f")
  EVENTS=$(grep -cE 'on(Click|Change|Submit|Focus|Blur|KeyDown|KeyUp|Mouse|Touch|Scroll|Drag|Drop)' "$f")
  BROWSER=$(grep -cE '\b(window|document|localStorage|sessionStorage|navigator|location)\b' "$f")
  if [ "$HOOKS" -eq 0 ] && [ "$EVENTS" -eq 0 ] && [ "$BROWSER" -eq 0 ]; then
    echo "CANDIDATE: $f (0 hooks, 0 events, 0 browser APIs)"
  fi
done
```

### A.2 Measure Bundle Per Route
```bash
#!/bin/bash
# bundle-per-route.sh
cd apps/mouth
pnpm build 2>&1 | grep -E '(○|●|ƒ|λ)\s+/' | while read line; do
  ROUTE=$(echo "$line" | awk '{print $2}')
  SIZE=$(echo "$line" | awk '{print $3, $4}')
  echo "$ROUTE → $SIZE"
done
```

### A.3 Image Optimization Candidates
```bash
#!/bin/bash
# find-large-images.sh
find apps/mouth/public/static/ -type f \( -name "*.png" -o -name "*.jpg" \) -size +500k \
  -exec sh -c 'echo "$(du -h "$1" | cut -f1) $1"' _ {} \; | sort -rh | head -30
```

### A.4 Build Time Profiling
```bash
#!/bin/bash
# build-profile.sh
cd apps/mouth
rm -rf .next
time NEXT_TELEMETRY_DISABLED=1 pnpm build 2>&1 | tee /tmp/mouth-build.log
echo "---"
grep -E '(Compil|Generat|runAfter|Total)' /tmp/mouth-build.log
echo "---"
echo "Static chunks:" && du -sh .next/static/chunks/
echo "Server:" && du -sh .next/server/
echo "Total .next:" && du -sh .next/
```

### A.5 Sentry Bundle Contribution
```bash
#!/bin/bash
# sentry-bundle-audit.sh
cd apps/mouth/.next/static/chunks
grep -rl 'sentry\|Sentry\|rrweb\|replay' *.js 2>/dev/null | while read f; do
  SIZE=$(du -h "$f" | cut -f1)
  echo "$SIZE $f"
done | sort -rh
```

---

## Riepilogo Priorita'

| Fase | Item | Effort | Impact | Risk |
|------|------|--------|--------|------|
| **0** | Homepage fonts → next/font | 1h | HIGH (render-blocking) | LOW |
| **0** | Homepage `<img>` → `<Image>` | 2h | HIGH (LCP) | LOW |
| **0** | Team photos compression | 30m | MEDIUM (38 MB) | LOW |
| **0** | Remove unnecessary "use client" | 30m | LOW (2 pages) | LOW |
| **0** | Add Vercel Speed Insights | 30m | MEDIUM (RUM) | LOW |
| **1** | Blog layout RSC refactor | 1-2d | **CRITICAL** (entire public site) | MEDIUM |
| **1** | PPR activation | 2h | HIGH | MEDIUM |
| **1** | ISR `revalidate: false` KBLI | 1h | MEDIUM | LOW |
| **1** | Sentry Replay lazy-load | 2h | HIGH (-228 KB) | LOW |
| **1** | Bundle budget CI | 3h | HIGH (regression gate) | LOW |
| **2** | kbli-navigator merge | 3-5d | HIGH (dedup) | MEDIUM |
| **2** | Pagefind search | 1-2d | MEDIUM (UX) | LOW |
| **2** | i18n bundle splitting | 3h | MEDIUM (-44 KB) | LOW |
| **3** | next-intl migration | 5-7d | MEDIUM (SEO, conditional) | HIGH |
| **3** | middleware → proxy rename | 30m | LOW (warning fix) | LOW |
