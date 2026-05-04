# Tour Codebase — Fokus apps/mouth/

Tour ini ngebahas struktur `apps/mouth/`, frontend Bali Zero (Next.js 16
+ React 19). Itu scope VERDE Subhi, jadi paling penting kamu kenal.

Untuk app lain (`backend-rag`, `cell`, `organism`, dll), kita liat
sekilas saja — itu scope GIALLO/ROSSO, kamu tidak akan edit langsung.

## Lokasi

- **Repo lavoro Subhi:** `~/Projects/nuzantara/`
- **Yang akan kita bedah:** `~/Projects/nuzantara/apps/mouth/`

Buka VSCode di repo, lalu navigate ke `apps/mouth/`.

## Struktur top-level apps/mouth/

```
apps/mouth/
├── src/
│   ├── app/              # Routes Next.js App Router
│   ├── components/       # React components reusable
│   ├── lib/              # Utility libs (analytics, format, etc.)
│   ├── content/          # Content: 149 articles markdown
│   └── styles/           # Tailwind global CSS
├── public/               # Static assets, llms*.txt files
├── e2e/                  # Playwright end-to-end tests
├── next.config.ts        # Next.js config
├── tailwind.config.ts    # Tailwind theme
├── package.json          # Dependencies + scripts
└── README.md             # App-level docs
```

### Direktori paling penting buat Subhi

#### `src/app/` — Next.js App Router

Ini di mana semua routes hidup. Convention App Router: file
`page.tsx` di folder = URL.

Contoh:

- `src/app/(blog)/blog/[slug]/page.tsx` → `https://kita.balizero.com/blog/[slug]`
- `src/app/visa/page.tsx` → `https://kita.balizero.com/visa`
- `src/app/property/eligibility/page.tsx` → `https://kita.balizero.com/property/eligibility`

Folder `(blog)`, `(marketing)`, `(tax-calendar)` pakai parentesis =
**route group** (tidak masuk URL). Ini pengelompokan logis tanpa
mempengaruhi path.

Folder `v2/_components/` underscored = ignored by Next.js routing,
hanya komponen.

#### `src/components/` — React components

```
src/components/
├── blog/                 # Komponen khusus blog
├── funnel/               # Funnel-related components (CTA, conversion forms)
├── ui/                   # Generic UI (Button, Card, Input)
├── layout/               # Header, Footer, Sidebar
└── seo/                  # SEO components (Schema.org JSON-LD, OG tags)
```

#### `src/lib/` — Utility libraries

```
src/lib/
├── analytics.ts          # ⭐ KEY FILE — GA4 tracking helpers
├── api/                  # API client functions
├── format/               # Date, currency, slug formatters
└── seo/                  # SEO utilities (canonical URL, robots)
```

#### `src/content/articles/` — 149 artikel

Markdown files structured per category:

```
src/content/articles/
├── immigration/          # Visa, KITAS, KITAP articles
├── business/             # PT PMA, KBLI, company setup
├── tax/                  # CoreTax, NPWP, SPT articles
├── property/             # Hak Pakai, freehold, sewa
└── general/              # Other / cross-cutting
```

Each article = 1 markdown file dengan frontmatter (title, slug, date,
category, etc.) + body markdown.

#### `e2e/` — Playwright tests

End-to-end tests. Most relevant for Subhi:

- `e2e/funnel-ctas.spec.ts` — verifikasi 4 funnel CTA klik kerja
- `e2e/blog-rendering.spec.ts` — verifikasi blog page rendering
- `e2e/analytics.spec.ts` — verifikasi GA4 events firing

Run dengan `npm run test:e2e` (di-detail di `06_SANCHO_BRANCH_WORKFLOW.md`).

## Key files — yang akan sering kamu sentuh

### `src/app/v2/_components/FunnelFeature.tsx`

⭐ **Day 1 mission**. Komponen yang render 4 funnel CTA di homepage
Bali Zero. Subhi bakal fix tracking GA4 di sini hari pertama.

Bug yang udah-udah-udah:

- Line 365: CTA "Apply Visa" — `onClick` handler missing
- Line 393: CTA "Setup Company" — `onClick` handler missing

Fix: tambah `onClick={() => trackFunnelEvent('apply_visa')}` (atau
similar). Import `trackFunnelEvent` dari `lib/analytics.ts`.

### `src/lib/analytics.ts`

Helpers GA4:

```typescript
export function trackFunnelEvent(name: string, props?: Record<string, any>) {
  if (typeof window !== "undefined" && (window as any).gtag) {
    (window as any).gtag("event", name, props);
  }
}
```

Functions yang sering dipakai:

- `trackFunnelEvent(name, props)` — generic GA4 event
- `trackPageView(path)` — manual page view
- `trackOutboundLink(url)` — link ke domain lain
- `trackWhatsAppClick(source)` — WA CTA tracking

### `src/app/(blog)/blog/[slug]/ArticleClient.tsx`

Komponen client-side untuk render article. Hydrate markdown ke React,
embed CTA di akhir article, track scroll depth.

Flow:

1. URL `/blog/<slug>` → Next.js dynamic route
2. Server fetch article markdown dari `src/content/articles/**/<slug>.md`
3. ArticleClient hydrate konten + tambah CTA
4. CTA klik → `trackFunnelEvent` → GA4

### `src/components/funnel/HeaderWhatsAppCTA.tsx`

Floating WhatsApp button di header semua pages. Pattern reference untuk
tambah WA CTA di page lain.

## Flow lengkap: blog post URL → CTA click → lead

```
1. User buka https://kita.balizero.com/blog/cara-apply-kitas
   ↓
2. Next.js dynamic route src/app/(blog)/blog/[slug]/page.tsx
   - getStaticProps (atau getStaticParams in App Router) baca markdown
   - Generate static HTML
   ↓
3. ArticleClient.tsx hydrate konten markdown ke React
   - Render heading, paragraf, image
   - Inject CTA at end of article
   ↓
4. User scroll, baca artikel
   - trackScrollDepth fires GA4 events: 25%, 50%, 75%, 100%
   ↓
5. User klik CTA "Apply KITAS sekarang"
   - onClick → trackFunnelEvent('cta_apply_kitas', {article: 'cara-apply-kitas'})
   - GA4 receive event
   - URL navigate to /visa atau WhatsApp wa.me/...
   ↓
6. Lead masuk ke WhatsApp / form
   - Sahira (sales) handoff
```

Kalau salah satu link rusak (mis. step 5 GA4 tidak fire) = tracking gap
= kita tidak tahu artikel mana yang convert. Itu Day 1 mission Subhi:
fix tracking gap di FunnelFeature.tsx.

## App lain (sekilas — bukan scope Subhi)

### `apps/backend-rag/`

Backend Python FastAPI. RAG, KBLI search, Visa Oracle, CRM API, prompts
Zantara. Scope ROSSO — Subhi tidak edit langsung, hanya pair (GIALLO)
untuk endpoint baru.

### `apps/cell/`

Cell agent runtime. Health monitoring, self-repair, observability.
Scope ROSSO.

### `apps/organism/`

Organism supervisor. Daemon orchestrator (innervation registry).
Scope ROSSO.

### `apps/admin-dashboard/`

Standalone Next.js app untuk inspect/control Nuzantara data. Scope
ROSSO untuk Subhi (admin only).

### `apps/web/`

Vercel subdomain satellite — chat AI interface. Scope GIALLO (Subhi
boleh propose UX improvements, tapi pair sama Antonello).

## Latihan — eksplorasi sendiri

Tutor bisa pandu kamu eksplor file. Coba tanya:

```
/agent zantara-onboarding tolong tunjukkan struktur apps/mouth/src/components/funnel/
```

Atau:

```
/agent zantara-onboarding apa beda antara FunnelFeature.tsx dan HeaderWhatsAppCTA.tsx?
```

Atau:

```
/agent zantara-onboarding di file analytics.ts fungsi mana yang track WhatsApp click?
```

Tujuan: kamu paham di mana cari, bukan hafal semuanya.
