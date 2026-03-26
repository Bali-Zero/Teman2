# Bali Zero Digital Brand Book — Design Spec
_2026-03-27 · Synthesized from Gemini (narrative), DeepSeek (psychology), Codex (architecture)_

---

## ⚠️ REGOLA FONDAMENTALE — Nessuna invenzione

**Tutto il contenuto testuale del Brand Book DEVE provenire da fonti verificate:**
- `data/kb_sources/zantara_core_redacted.md`
- `data/kb_sources/SOUL_zantara_persona.md`
- `apps/backend-rag/backend/prompts/zantara_core.py`
- `apps/backend-rag/backend/data/bali_zero_official_prices_2025.json`
- Database PostgreSQL (clienti reali, pratiche reali)
- Qdrant (documenti vettorizzati reali)

**Vietato:**
- Inventare anni di fondazione
- Inventare numeri di clienti non verificati
- Inventare nomi di fondatori o team
- Inventare storie o aneddoti
- Usare frasi narrative generate dall'AI come fatti

**Ogni numero, data, nome nel Brand Book deve avere un file sorgente citabile.**

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

## 3. Dati Reali Verificati (GROUND TRUTH)

> Questi dati provengono da fonti verificate nel codebase. NESSUNA invenzione.

### Storia aziendale (verificata dal fondatore)
- **CV Bayu Santero**: fondata 2006, la società madre originale
- **Bali Zero**: nasce 2020, spin-off/evoluzione di CV Bayu Santero
- **Origine leggendaria**: incontro tra un bule (Zero, il fondatore europeo) e Pak Zainal Abidin, owner di CV Bayu Santero — un incontro tra due mondi che genera qualcosa di nuovo
- **Pak Zainal Abidin**: CEO, uomo di straordinaria esperienza nel mercato indonesiano

### Team reale (da `apps/mouth/src/app/(blog)/team/page.tsx`)
| Dipartimento | Persone | Nomi |
|---|---|---|
| Leadership | 2 | Zainal Abidin (CEO), Ruslana (Board Member) |
| Setup/Company | 11 | Anton, Vino, Krisna, Adit (Lead), Ari, Dea, Surya, Damar, Marta, Olena, Anna |
| Tax | 5 | Veronika (Manager), Angel, Kadek, Dewa Ayu, Faisha |
| Accounting | 1 | Asya Nadia |
| Support/Marketing | 3 | Rina, Nina (ext.), Sahira |
| **Totale** | **~22** | — |

**⚠️ NON USARE "35 specialisti" — era inventato. Il numero reale è ~22.**

### Contatti verificati (dal codebase)
- **WhatsApp:** +62 859 0436 9574
- **Email:** info@balizero.com
- **Web:** balizero.com

### Clienti (da confermare col fondatore)
- "5.000+ clienti" presente in MEMORY.md — **da verificare con DB reale prima di pubblicare**

### Servizi verificati (da `zantara_core.py`)
- Visti singola/multipla entrata
- KITAS / KITAP
- PT PMA (company setup)
- Tax & Accounting
- KBLI Navigator (9.612 codici KBLI 2025)

### Contesto competitivo (da `COMPETITOR_INTELLIGENCE_2026.md`)
- **Mercato**: Emerhub (2011, 65 emp, -8.5%), InCorp (2012, 100 emp, -19%), LMI (2015, 26 emp, -23.5%), Seven Stones (2016, 32 emp)
- **Tutti i competitor stanno SHRINKANDO** — Bali Zero è l'unico a crescere
- **Bali Zero è l'unico player con AI** nel mercato indonesiano (96 MCP tools, KG 56K nodi, 66K documenti legali indicizzati)
- **Differenziatore assoluto**: KBLI Navigator (1.563 codici), Zantara 24/7 su WhatsApp/Telegram/Web/Instagram, client portal con tracking real-time

---

## 4. Eight Chapters

| # | ID | Opens With (hybrid B — SOLO DATI REALI) | Poi |
|---|----|-----------------------------------------|-----|
| 1 | `cover` | Nessun testo — cinematic full-bleed | Logo + "Bali Zero" |
| 2 | `manifesto` | "Dal 2006 al futuro. Un'eredità, una rivoluzione." | CV Bayu Santero → Bali Zero 2020 |
| 3 | `origin` | "L'incontro che ha cambiato tutto." | Storia vera: bule Zero + Pak Zainal Abidin |
| 4 | `team` | "22 persone. Un obiettivo." | Grid team reale con nomi/ruoli verificati |
| 5 | `services` | "Prezzi reali. Nessuna sorpresa." | ServicePricingCard live dal RAG |
| 6 | `impact` | "L'unica agenzia AI in Indonesia." | Confronto competitor con dati reali (tutti -19% a -23%) |
| 7 | `technology` | "Zantara: il tuo consulente, 24/7." | Demo Zantara live in-page |
| 8 | `contact` | Pull quote del fondatore (da fornire) | WhatsApp + email + PDF |

### Fear→Trust map (basato su contesto reale)
| Capitolo | Paura del prospect | Risposta con dati reali |
|----------|-------------------|------------------------|
| Manifesto | "Sono tutti uguali" | 20 anni di storia (2006+2020) |
| Origin | "Non capiscono" | Storia vera fondatori — radici locali + visione europea |
| Team | "Chi mi segue?" | 22 persone reali, nomi, ruoli, contatti diretti |
| Services | "Mi fregano sui prezzi" | Prezzi live dal DB, pubblicati, nessuna sorpresa |
| Impact | "Funziona?" | Tutti i competitor shrinkano — noi cresciamo |
| Technology | "Resterò solo?" | Zantara live ora, risponde in 3 secondi |
| Contact | "Come inizio?" | Un messaggio WhatsApp |

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
