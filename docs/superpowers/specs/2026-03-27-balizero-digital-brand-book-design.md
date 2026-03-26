# Bali Zero Digital Brand Book — Design Spec
_2026-03-27 · Synthesized from Gemini (narrative), DeepSeek (psychology), Codex (architecture)_

---

## 1. Vision

A full-screen interactive web experience at `balizero.com/book` — part magazine, part proof of capability. Not a brochure. A book that reads you back.

**Tone:** Hybrid B — each chapter opens with concrete numbers, then the story comes in. Data earns the right to tell the story.

**Goal:** A prospect at chapter 5 (Impact) should feel one thing: "These people have already solved my exact problem, 5.000 times."

---

## 2. URL & Deployment

| Item | Decision |
|------|----------|
| URL | `balizero.com/book` |
| App | `apps/mouth` (no new Vercel project) |
| Route group | `(book)` — isolated from blog nav |
| Deep links | `/book/[chapter]` — e.g. `/book/team`, `/book/services` |
| Rejected options | `zantara.balizero.com` (noindex middleware — fatal), `book.balizero.com` (overkill) |

---

## 3. Eight Chapters

| # | ID | Opens With (hybrid B) | Then |
|---|----|-----------------------|------|
| 1 | `cover` | Nessun testo — cinematic full-bleed | Logo + "Bali Zero" + caret down |
| 2 | `manifesto` | "5.000 clienti. 6 anni. 4 servizi. 1 missione." | Perché esiste Bali Zero in 3 paragrafi |
| 3 | `origin` | "2020. Una coda alle 5 di mattina a Imigrasi." | Narrativo fondatore — Ruptura → Riconoscimento → Arrivo |
| 4 | `team` | "35 specialisti. 8 nazionalità. 0 tolleranza per le scuse." | Grid team con bio modal + LinkedIn + WhatsApp |
| 5 | `services` | "Prezzi reali. Nessuna sorpresa." | ServicePricingCard live dal RAG, WhatsApp CTA |
| 6 | `impact` | StatsCounter animati (5.000+, 6 anni, 93k documenti, 24/7) | Timeline interattiva dalla fondazione |
| 7 | `technology` | "Il primo studio legale con un AI dedicato, 24/7." | Demo Zantara live in-page |
| 8 | `contact` | Pull quote finale del fondatore | WhatsApp + email + download PDF |

### Fear→Trust map (DeepSeek)
Ogni capitolo risolve un timore specifico del prospect:

| Capitolo | Paura | Soluzione narrativa |
|----------|-------|---------------------|
| Manifesto | "Sono tutti uguali" | 5.000 prove concrete |
| Origin | "Non capiscono il mio problema" | "Abbiamo vissuto la stessa cosa" |
| Team | "Chi mi segue davvero?" | Facce reali, diretti contattabili |
| Services | "Mi faranno pagare extra" | Prezzi live, trasparenti |
| Impact | "Funziona davvero?" | Timeline + numeri verificabili |
| Technology | "Resterò abbandonato?" | Zantara live, risponde ora |
| Contact | "Come si comincia?" | Un passo solo: un messaggio |

**Momento di credenza:** capitolo 7 (Technology) — il prospect usa Zantara in tempo reale. È il punto di non ritorno.

---

## 4. Architecture

### 4.1 File structure

```
apps/mouth/src/app/
└── (book)/
    ├── layout.tsx                     # Shell: font League Spartan + Montserrat, no blog nav
    ├── book/
    │   ├── page.tsx                   # Root: renders <BookPage>
    │   ├── [chapter]/page.tsx         # Deep-link: generateStaticParams + generateMetadata
    │   └── loading.tsx                # Chapter skeleton

apps/mouth/src/components/book/
    ├── book-data.ts                   # All static data (chapters, team, milestones, stats)
    ├── BookShell.tsx                  # Scroll container + IntersectionObserver URL sync
    ├── BookNav.tsx                    # Sidebar dots (md+) + mobile bottom bar
    ├── ChapterSection.tsx             # Generic wrapper: content-visibility: auto
    ├── ChapterHero.tsx                # Full-bleed parallax hero
    ├── StatsCounter.tsx               # react-countup + IntersectionObserver
    ├── PullQuoteBlock.tsx             # 64px League Spartan + Web Share API
    ├── VideoBackground.tsx            # Deferred src + bandwidth detection
    ├── TeamGrid.tsx                   # 3-col grid, CSS hover
    ├── TeamModal.tsx                  # Radix Dialog + framer-motion AnimatePresence
    ├── TimelineComponent.tsx          # SVG stroke-dashoffset + horizontal scroll
    ├── ServicePricingCard.tsx         # SWR pricing hook + AnimateHeight + WhatsApp deep-link
    ├── ZantaraCTA.tsx                 # Floating pill (capitoli 5-7), triggers ZantaraWidget
    └── ShareButton.tsx                # Web Share API + clipboard fallback + Sonner toast

apps/mouth/src/app/api/og/book/
    └── route.tsx                      # Edge OG generator per capitolo

apps/mouth/src/lib/book/
    └── image-utils.ts                 # generateBlurPlaceholder() — build-time only, never runtime
```

### 4.2 Navigation & URL sync

`BookShell` monta un singolo `IntersectionObserver` su tutti i `ChapterSection` con `threshold: 0.4`.
Quando un capitolo supera il 40% di visibilità:
1. Aggiorna `activeChapter` state
2. `window.history.replaceState(null, '', '/book/' + chapterId)` — URL aggiornato, zero re-render
3. `document.title` aggiornato

**Deep-link su load:** se URL è `/book/team`, dopo mount → `scrollIntoView({ behavior: 'instant' })` sul `#team` section. Il contenuto è tutto in una pagina — nessun split in bundle separati per capitolo.

**Mobile:** barra bottom fissa — `←` | "Capitolo 3 di 8: Team" | `→`. Swipe touch avanza capitolo via `scrollIntoView`.

### 4.3 Pricing (live dal RAG)

`ServicePricingCard` usa SWR hook `usePricingData(serviceId)`:
- Chiama `/api/pricing/calculate` (proxy → Fly.io backend)
- `revalidateOnFocus: false`
- Fallback a prezzi statici in `book-data.ts` se backend in cold start
- **Regola:** mai hardcodare prezzi. Sempre `PricingTool` via backend.

---

## 5. Components Detail

### BookNav
- Desktop (md+): sidebar sinistra fissa — 8 dot verticali, dot attivo = `--bz-accent` (#d4845a) riempito, progress bar verticale sottile
- Mobile: bottom bar (prev/next arrows + nome capitolo), hamburger per drawer full-screen

### ChapterHero
- `<Image priority fill>` da `/public/static/` (AI cinematic art)
- Parallax: CSS custom property `--scroll-y` impostata da passive scroll listener → `transform: translateY(calc(var(--scroll-y) * 0.4px))`
- Testo: `framer-motion initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}`, stagger 0.1s tra children

### TimelineComponent
- Desktop: scroll orizzontale. Mobile: verticale.
- SVG linea: `stroke-dashoffset` da 1→0 tied allo scroll progress del capitolo genitore
- Nodi: `framer-motion useInView`, fade-in sequenziale
- Click nodo: espande inline card con foto + testo

### TeamGrid + TeamModal
- Grid: 3-col desktop, 2-col tablet, 1-col mobile. `aspect-ratio: 1` per foto.
- Hover: CSS transition — `box-shadow` + `scale: 1.05` su foto. Zero JS.
- Modal: `@radix-ui/react-dialog` + `framer-motion AnimatePresence` slide-up
- Dati: `TEAM_MEMBERS` in `book-data.ts` — foto da `/public/static/team/` o `/public/avatars/`

### ServicePricingCard
- Mostra: nome servizio, tagline, prezzo "a partire da IDR X", 2 item visibili (expand per resto)
- Expand: `framer-motion AnimateHeight`, `overflow: hidden`
- CTA: `wa.me/6285904369574?text=Ciao, sono interessato a [Servizio]` — link diretto WhatsApp

### StatsCounter
- `react-countup` (già installato): `duration: 2`, `enableScrollSpy: true`, `scrollSpyOnce: true`
- Labels: `framer-motion` stagger fade-in
- 4 numeri: 5.000+ clienti, 6 anni, 93k documenti vettorizzati, 24/7 AI

### VideoBackground
- `<video autoPlay muted loop playsInline>`
- `src` impostato **solo** quando il capitolo entra in viewport (IntersectionObserver)
- Bandwidth detection: `navigator.connection.effectiveType === '2g' || '3g'` → swap con immagine statica

### PullQuoteBlock
- 64px League Spartan, `--bz-accent-warm`, decoro `zantara_ornate_corner_transparent.png`
- Share: `navigator.share()` su mobile, clipboard + Sonner toast su desktop

### ZantaraCTA
- Floating pill bottom-right, visibile solo su capitoli 5, 6, 7
- Testo: "Chiedi a Zantara" + pulse ring animato
- On click: `setZantaraOpen(true)` via context ref del `ZantaraWidget` già montato in `BookShell`
- **Regola:** un solo `ZantaraWidget` montato — `ZantaraCTA` è solo un trigger

---

## 6. OG Images & WhatsApp Cards

### Edge OG generator
`/api/og/book/route.tsx` — `ImageResponse` Next.js, Edge runtime.

Query params: `?chapter=team&title=Meet+the+Team&subtitle=35+specialists`

Template:
- Background: `#0c0c0e`
- Layer: `zantara_gold_black_gradient_transparent.png` (base64 inline a build time)
- Chapter number top-left (terracotta)
- Titolo: League Spartan equivalent via Google Fonts in ImageResponse
- Logo bottom-right (base64 inline)
- Linea divisoria kintsugi gold

### WhatsApp caveat
WhatsApp crawler non esegue JS, non segue redirect Edge in modo affidabile in Asia.
**Soluzione:** pre-generare PNG statici a `/public/og/book/[chapter].png` via `scripts/generate-book-og.ts` durante build.
`generateMetadata` punta a `/og/book/team.png` (statico), con `/api/og/book?chapter=team` come meta fallback.

### Deep-link per ogni capitolo
`/book/[chapter]/page.tsx`:
```typescript
export async function generateStaticParams() {
  return CHAPTERS.map(c => ({ chapter: c.id }));
}

export async function generateMetadata({ params }) {
  const chapter = CHAPTERS.find(c => c.id === params.chapter);
  return {
    title: `${chapter.title} — Bali Zero`,
    openGraph: {
      images: [`/og/book/${chapter.id}.png`]  // statico per WhatsApp
    }
  };
}
```

---

## 7. PDF Relationship

**I due artefatti hanno ruoli distinti:**

| Artefatto | Quando | Come |
|-----------|--------|------|
| `balizero.com/book` | Sempre online — prospect online | Browser, link diretto |
| `brochure_balizero_en.pdf` | Meeting fisico, allegato proposta | Scaricabile dal capitolo 8 |

**Non auto-generare PDF dal DOM** — Puppeteer su Fly.io cold start è fragile e produce output bassa qualità.

**Collegamento:**
- Nel capitolo Contact: `<a href="/files/balizero-brochure.pdf" download>Scarica la brochure</a>`
- Nel PDF (aggiungere a `generate_brochure.py`): QR code back cover → `balizero.com/book` via libreria `qrcode`

---

## 8. Performance

### Target
FCP < 2.5s su 4G Indonesia (10 Mbps, 100ms RTT)

### Strategie

| Strategia | Dettaglio |
|-----------|-----------|
| Framer Motion | `LazyMotion + domAnimation` → 18KB vs 108KB. Usare `<m.div>` non `<motion.div>` |
| `content-visibility` | `auto` su tutti `ChapterSection` fuori viewport, `visible` solo su capitolo 0 |
| Immagini | `<Image>` Next.js, `priority` solo cap 0, `placeholder="blur"` con base64 baked in `book-data.ts` |
| AVIF | Script `scripts/convert-book-assets.ts` (sharp) — target < 150KB per hero |
| Video | `src` impostato solo su IntersectionObserver entry. Skip completo su 2G/3G |
| Bundle | Cap 0+1 SSR'd, cap 2-7 dynamic import (lazy) triggered da scroll |
| Font | `next/font/google` League Spartan + Montserrat, `subsets: ['latin']`, `display: 'swap'` — dichiarati solo in `(book)/layout.tsx` |

### Budget bundle

| Chunk | Target |
|-------|--------|
| Initial JS (cap 0+1) | < 90KB gzipped |
| Per capitolo lazy | < 40KB gzipped |
| Total su load iniziale | < 200KB |

### Rischio non ovvio (da Codex)
`outputFileTracingExcludes` in `next.config.ts` esclude `./public/static/**` dal tracing delle serverless functions. **Mai** fare `readFile` da `/public/static/` a runtime in un Server Component. Tutti i blur placeholder devono essere generati a build time e baked come base64 in `book-data.ts`.

---

## 9. Implementation Phases

### Phase 1 — Foundation (1-2 giorni)
1. `(book)/layout.tsx` — shell, font, BookShell, no blog nav
2. `(book)/book/page.tsx` — SSG, renders `<BookPage>`
3. `components/book/book-data.ts` — tutti i dati statici tipizzati
4. `BookShell.tsx` — scroll container + IntersectionObserver URL sync
5. `BookNav.tsx` — sidebar dots + mobile bottom bar
6. `ChapterSection.tsx` — wrapper con `content-visibility`

### Phase 2 — Core Components (2-3 giorni)
7. `ChapterHero.tsx` — parallax + framer-motion entrance
8. `StatsCounter.tsx` — react-countup + IntersectionObserver
9. `PullQuoteBlock.tsx` + `ShareButton.tsx`
10. `VideoBackground.tsx` — deferred + bandwidth detection
11. `ZantaraCTA.tsx` — trigger ZantaraWidget context

### Phase 3 — Interactive Components (2-3 giorni)
12. `TeamGrid.tsx` + `TeamModal.tsx` — Radix Dialog
13. `TimelineComponent.tsx` — SVG stroke-dashoffset
14. `ServicePricingCard.tsx` — SWR + AnimateHeight + WhatsApp

### Phase 4 — OG + PDF (1 giorno)
15. `/api/og/book/route.tsx` — Edge OG generator
16. `scripts/generate-book-og.ts` — static PNG build-time
17. `generateStaticParams` + `generateMetadata` in `/book/[chapter]/page.tsx`
18. Aggiornare `generate_brochure.py` — QR code back cover

### Phase 5 — Performance Pass (1 giorno)
19. Convert AI art → AVIF via `scripts/convert-book-assets.ts`
20. Switch `motion.div` → `m.div` + `LazyMotion` ovunque
21. Verify bundle: `ANALYZE=true npm run build`

---

## 10. Assets Disponibili

### AI cinematic (già in `/public/static/image_art/`)
- Cover: `zantara_brain_transparent.png` su `Luxury_gold_to_black_gradient.png`
- Origin: `Stressed_expat_couple.png`, `Young_Indonesian_entrepreneur.png`
- Technology: `Abstract_AI_brain.png`, `Elegant_data_flow.png`
- Decorativo: `zantara_ornate_corner_transparent.png`, `zantara_gold_black_gradient_transparent.png`

### Team (da aggiungere)
- Path: `/public/static/team/` — foto quadrate, min 400×400px
- Oppure usare `/public/avatars/` (già popolato da CRM pipeline)

### Brand tokens (NON duplicare)
- `packages/core/styles/bz-tokens.css` — `--bz-base: #0c0c0e`, `--bz-accent: #d4845a`
- Import in `(book)/layout.tsx` — non riscrivere i colori

---

## 11. Data Sources

| Dato | Sorgente | Pattern |
|------|----------|---------|
| Prezzi servizi | `/api/pricing/calculate` via SWR | Live, fallback statico |
| Team | `book-data.ts` array statico | Aggiornato manualmente |
| Timeline milestones | `book-data.ts` array statico | — |
| Stats (5.000+ clienti) | `book-data.ts` statico | Brand statement, non live ticker |
| Foto team | `/public/static/team/` | Già nella repo |
| AI art | `/public/static/image_art/` | Già nella repo |

---

_Spec approvata il 2026-03-27. Prossimo step: writing-plans per piano implementazione dettagliato._
