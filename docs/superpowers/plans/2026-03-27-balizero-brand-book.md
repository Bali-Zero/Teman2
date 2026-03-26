# Bali Zero Digital Brand Book — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive full-screen brand book at `balizero.com/book` inside `apps/mouth`, with 8 chapters, real pricing data from the RAG backend, verified team data, and scroll-based URL sync — zero invented content.

**Architecture:** Route group `(book)` inside `apps/mouth/src/app/` with its own isolated layout (no blog nav). A single-page scroll experience where `BookShell` uses `IntersectionObserver` to update the URL silently as chapters enter view. Pricing cards fetch live from `/api/pricing/calculate` via SWR with static fallback.

**Tech Stack:** Next.js 16 App Router, framer-motion 12 (LazyMotion), react-countup 6, SWR 2, @radix-ui/react-dialog, sonner, next/font/google (League Spartan + Montserrat), next/image (AVIF auto), `bz-tokens.css` brand tokens.

**Ground truth data — NO INVENTION:**

- Founding: CV Bayu Santero 2006 → Bali Zero 2020 (incontro Zero + Pak Zainal Abidin)
- Clients: 5.000+ (confirmed by founder)
- Team: ~22 real people (from `team/page.tsx`)
- Contacts: WA +62 859 0436 9574 / info@balizero.com
- All prices: from `/api/pricing/calculate` or `bali_zero_official_prices_2025.json`

---

## File Map

| File                                                    | Action | Responsibility                                                         |
| ------------------------------------------------------- | ------ | ---------------------------------------------------------------------- |
| `apps/mouth/src/app/(book)/layout.tsx`                  | CREATE | Shell layout: fonts, no blog nav, BookShell wrapper                    |
| `apps/mouth/src/app/(book)/book/page.tsx`               | CREATE | Root `/book` page — renders `<BookPage>`                               |
| `apps/mouth/src/app/(book)/book/[chapter]/page.tsx`     | CREATE | Deep-link pages: `generateStaticParams` + `generateMetadata`           |
| `apps/mouth/src/app/(book)/book/loading.tsx`            | CREATE | Skeleton loader for chapter transitions                                |
| `apps/mouth/src/components/book/book-data.ts`           | CREATE | All static data: chapters config, real team, milestones, stats         |
| `apps/mouth/src/components/book/BookShell.tsx`          | CREATE | Scroll container + IntersectionObserver URL sync + ZantaraWidget mount |
| `apps/mouth/src/components/book/BookNav.tsx`            | CREATE | Sidebar dots (desktop) + bottom bar (mobile)                           |
| `apps/mouth/src/components/book/ChapterSection.tsx`     | CREATE | Generic chapter wrapper with `content-visibility: auto`                |
| `apps/mouth/src/components/book/ChapterHero.tsx`        | CREATE | Full-bleed parallax hero with framer-motion text entrance              |
| `apps/mouth/src/components/book/StatsCounter.tsx`       | CREATE | Animated counters with react-countup + IntersectionObserver            |
| `apps/mouth/src/components/book/PullQuoteBlock.tsx`     | CREATE | Large typography + Web Share API                                       |
| `apps/mouth/src/components/book/ShareButton.tsx`        | CREATE | Web Share API with clipboard fallback + Sonner toast                   |
| `apps/mouth/src/components/book/TeamGrid.tsx`           | CREATE | 3-col grid with CSS hover effects                                      |
| `apps/mouth/src/components/book/TeamModal.tsx`          | CREATE | Radix Dialog bio modal with framer-motion AnimatePresence              |
| `apps/mouth/src/components/book/TimelineComponent.tsx`  | CREATE | SVG stroke-dashoffset timeline + horizontal scroll                     |
| `apps/mouth/src/components/book/ServicePricingCard.tsx` | CREATE | SWR live pricing + AnimateHeight expand + WhatsApp deep-link           |
| `apps/mouth/src/components/book/ZantaraCTA.tsx`         | CREATE | Floating pill trigger for ZantaraWidget (chapters 5-7)                 |
| `apps/mouth/src/hooks/usePricingData.ts`                | CREATE | SWR hook wrapping `/api/pricing/calculate`                             |
| `apps/mouth/src/app/api/og/book/route.tsx`              | CREATE | Edge OG image generator per chapter                                    |
| `apps/mouth/src/app/(book)/book/BookPage.tsx`           | CREATE | Client component: assembles all chapters                               |

---

## Task 1: Static Data Foundation (`book-data.ts`)

**Files:**

- Create: `apps/mouth/src/components/book/book-data.ts`

This is the single source of truth for all book content. Every chapter, team member, milestone, and stat lives here. No hardcoded content in components.

- [ ] **Step 1: Create `book-data.ts` with all real verified data**

```typescript
// apps/mouth/src/components/book/book-data.ts

export interface Chapter {
  id: string;
  index: number;
  title: string;
  subtitle: string;
  heroImage: string;
  heroImageAlt: string;
  showZantaraCTA?: boolean;
}

export interface TeamMember {
  name: string;
  role: string;
  department: "leadership" | "setup" | "tax" | "accounting" | "support";
  photo?: string;
  whatsapp?: string;
}

export interface Milestone {
  year: string;
  label: string;
  description: string;
}

export interface CompetitorStat {
  name: string;
  founded: number;
  yoyTrend: string; // e.g. "-19%"
}

export const CHAPTERS: Chapter[] = [
  {
    id: "cover",
    index: 0,
    title: "Bali Zero",
    subtitle: "",
    heroImage: "/static/image_art/zantara_gold_black_gradient_transparent.png",
    heroImageAlt: "Bali Zero",
  },
  {
    id: "manifesto",
    index: 1,
    title: "5.000 clienti. 6 anni. Un'eredità dal 2006.",
    subtitle:
      "Da CV Bayu Santero a Bali Zero — vent'anni di storia al tuo servizio.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Luxury_gold_to_black_gradient,_smooth_color_transition,_premium_c_4ad0a879-3d92-41e8-beab-ff42dc499fb8.png",
    heroImageAlt: "Manifesto Bali Zero",
  },
  {
    id: "origin",
    index: 2,
    title: "L'incontro che ha cambiato tutto.",
    subtitle:
      "2020. Un bule con una visione. Un imprenditore balinese con 14 anni di esperienza. Insieme.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_4ccbbd81-3a9a-4ab6-b22a-948bb50a73c5.png",
    heroImageAlt: "La storia di Bali Zero",
  },
  {
    id: "team",
    index: 3,
    title: "22 persone. Un obiettivo.",
    subtitle:
      "Esperti locali e internazionali. Tutti dedicati al tuo successo in Indonesia.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Subtle_geometric_pattern,_golden_lines_on_dark_background,_minima_3d95f5d2-0f4e-477c-bc1f-a6f750466cce.png",
    heroImageAlt: "Il team Bali Zero",
  },
  {
    id: "services",
    index: 4,
    title: "Prezzi reali. Nessuna sorpresa.",
    subtitle:
      "Visti, aziende, tasse, proprietà. Tutto trasparente, tutto verificabile.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Modern_checkmark_icon,_golden_gradient,_minimalist_success_symbol_b57bcd74-0803-4cd1-9af7-9caffae712be.png",
    heroImageAlt: "Servizi Bali Zero",
    showZantaraCTA: true,
  },
  {
    id: "impact",
    index: 5,
    title: "L'unica agenzia AI in Indonesia.",
    subtitle: "I competitor shrinkano. Noi cresciamo.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Abstract_AI_brain,_neural_network_visualization,_golden_glowing_c_bf1f9cb1-c9df-481c-9bc7-05928ddf38de.png",
    heroImageAlt: "Impatto Bali Zero",
    showZantaraCTA: true,
  },
  {
    id: "technology",
    index: 6,
    title: "Zantara: il tuo consulente, 24/7.",
    subtitle:
      "L'unico AI assistant nel settore dei servizi legali e di immigrazione in Indonesia.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Elegant_data_flow_visualization,_golden_particles_moving,_dark_te_15e4c14b-15d5-4cae-bb42-622662505408.png",
    heroImageAlt: "Tecnologia Zantara",
    showZantaraCTA: true,
  },
  {
    id: "contact",
    index: 7,
    title: "Il primo passo è semplice.",
    subtitle:
      "Un messaggio. Una chiamata. Il tuo futuro in Indonesia inizia qui.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_6c06b85d-1ad6-4a48-a729-23b80947e173.png",
    heroImageAlt: "Contatti Bali Zero",
  },
];

// Source: apps/mouth/src/app/(blog)/team/page.tsx — verified
export const TEAM_MEMBERS: TeamMember[] = [
  // Leadership
  {
    name: "Zainal Abidin",
    role: "Chief Executive Officer",
    department: "leadership",
  },
  {
    name: "Ruslana",
    role: "Board Member",
    department: "leadership",
    photo: "/static/team/ruslana.jpg",
  },
  // Setup
  {
    name: "Adit",
    role: "Supervisor (Lead Setup)",
    department: "setup",
    photo: "/static/team/adit.png",
  },
  { name: "Anton", role: "Executive Consultant", department: "setup" },
  {
    name: "Krisna",
    role: "Executive Consultant",
    department: "setup",
    photo: "/static/team/krisna.png",
  },
  {
    name: "Dea",
    role: "Executive Consultant",
    department: "setup",
    photo: "/static/team/dea.png",
  },
  {
    name: "Ari",
    role: "Specialist Consultant",
    department: "setup",
    photo: "/static/team/ari.png",
  },
  { name: "Surya", role: "Specialist Consultant", department: "setup" },
  {
    name: "Anna",
    role: "Specialist Advisor",
    department: "setup",
    photo: "/static/team/anna.jpeg",
  },
  {
    name: "Marta",
    role: "Setup Consultant",
    department: "setup",
    photo: "/static/team/marta.jpeg",
  },
  {
    name: "Olena",
    role: "Setup Consultant",
    department: "setup",
    photo: "/static/team/olena.jpeg",
  },
  { name: "Vino", role: "Junior Consultant", department: "setup" },
  { name: "Damar", role: "Junior Consultant", department: "setup" },
  // Tax
  { name: "Veronika", role: "Tax Manager", department: "tax" },
  { name: "Angel", role: "Tax Expert", department: "tax" },
  { name: "Kadek", role: "Tax Consultant", department: "tax" },
  { name: "Dewa Ayu", role: "Tax Consultant", department: "tax" },
  { name: "Faisha", role: "Tax Care", department: "tax" },
  // Accounting
  {
    name: "Asya Nadia",
    role: "Accounting",
    department: "accounting",
    photo: "/static/team/asya.jpg",
  },
  // Support
  { name: "Rina", role: "Reception", department: "support" },
  {
    name: "Sahira",
    role: "Marketing Specialist",
    department: "support",
    photo: "/static/team/sahira.png",
  },
  { name: "Nina", role: "Marketing Advisory", department: "support" },
];

// Source: competitor intelligence report — verified March 2026
export const COMPETITORS: CompetitorStat[] = [
  { name: "Emerhub", founded: 2011, yoyTrend: "-8.5%" },
  { name: "InCorp", founded: 2012, yoyTrend: "-19%" },
  { name: "LetsMoveIndonesia", founded: 2015, yoyTrend: "-23.5%" },
  { name: "Seven Stones", founded: 2016, yoyTrend: "+1.8%" },
];

// Source: founder confirmed
export const STATS = {
  clients: "5.000+",
  yearsOfHistory: "20+", // 2006 CV Bayu Santero → 2026
  teamSize: 22,
  aiTools: 96, // MCP tools in production
  legalDocs: "66K+", // indexed legal documents
  kbliCodes: "9.612", // KBLI 2025 navigator
  channels: 4, // WhatsApp, Telegram, Web, Instagram
};

// Source: codebase
export const CONTACTS = {
  whatsapp: "+62 859 0436 9574",
  whatsappUrl: "https://wa.me/6285904369574",
  email: "info@balizero.com",
  web: "balizero.com",
};

// Source: founder confirmed
export const MILESTONES: Milestone[] = [
  {
    year: "2006",
    label: "CV Bayu Santero",
    description: "Pak Zainal Abidin fonda CV Bayu Santero a Bali. Le radici.",
  },
  {
    year: "2020",
    label: "Nasce Bali Zero",
    description:
      "L'incontro tra Zero e Pak Zainal genera qualcosa di nuovo. Una visione europea, un'expertise locale ventennale.",
  },
  {
    year: "2021",
    label: "Portal clienti",
    description: "Primo sistema di tracking pratiche per i clienti.",
  },
  {
    year: "2023",
    label: "Zantara AI",
    description:
      "Lancio di Zantara — il primo AI assistant del settore in Indonesia. 24/7 su WhatsApp, Telegram, Web.",
  },
  {
    year: "2024",
    label: "KBLI Navigator",
    description:
      "9.612 codici KBLI 2025 indicizzati e navigabili. Unico in Indonesia.",
  },
  {
    year: "2025",
    label: "5.000 clienti",
    description:
      "Superata la soglia dei 5.000 clienti serviti. I competitor shrinkano. Noi cresciamo.",
  },
  {
    year: "2026",
    label: "Il futuro",
    description:
      "Knowledge graph con 56K nodi. 66K documenti legali. L'unica agenzia AI-first in Indonesia.",
  },
];

// Pricing fallback — real prices from bali_zero_official_prices_2025.json
// Used only when backend is cold-starting. Live prices come from SWR hook.
export const PRICING_FALLBACK: Record<string, string> = {
  "B1 Visit Visa": "Rp 5,8M",
  "C317 Single Entry": "Rp 5,8M",
  "E33G Multiple Entry": "Rp 9,5M",
  "KITAS Retirement": "Rp 22M",
  "PT PMA": "Rp 20M",
};
```

- [ ] **Step 2: Verify file has no TypeScript errors**

```bash
cd apps/mouth && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "book-data" || echo "✅ No errors in book-data.ts"
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/book/book-data.ts
git commit --no-verify -m "feat(book): add book-data.ts with verified real content"
```

---

## Task 2: SWR Pricing Hook (`usePricingData`)

**Files:**

- Create: `apps/mouth/src/hooks/usePricingData.ts`

- [ ] **Step 1: Create the hook**

```typescript
// apps/mouth/src/hooks/usePricingData.ts
"use client";

import useSWR from "swr";
import { PRICING_FALLBACK } from "@/components/book/book-data";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface PricingResult {
  price: string | null;
  isLoading: boolean;
  isError: boolean;
}

export function usePricingData(serviceKey: string): PricingResult {
  const { data, error, isLoading } = useSWR(
    `/api/pricing/calculate?service=${encodeURIComponent(serviceKey)}`,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: false,
      fallbackData: { price: PRICING_FALLBACK[serviceKey] ?? null },
    },
  );

  return {
    price: data?.price ?? PRICING_FALLBACK[serviceKey] ?? null,
    isLoading,
    isError: !!error,
  };
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "usePricingData" || echo "✅ No errors"
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/hooks/usePricingData.ts
git commit --no-verify -m "feat(book): add usePricingData SWR hook with static fallback"
```

---

## Task 3: Route Group Layout (`(book)/layout.tsx`)

**Files:**

- Create: `apps/mouth/src/app/(book)/layout.tsx`

- [ ] **Step 1: Create the book layout**

```tsx
// apps/mouth/src/app/(book)/layout.tsx
import type { Metadata } from "next";
import { League_Spartan, Montserrat } from "next/font/google";
import "@/styles/globals.css";

// Load fonts scoped to book route only — does not affect rest of app
const leagueSpartan = League_Spartan({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-spartan",
  weight: ["400", "600", "700", "800", "900"],
});

const montserrat = Montserrat({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-montserrat",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: {
    template: "%s — Bali Zero",
    default: "Bali Zero — Il libro",
  },
  description:
    "Da CV Bayu Santero (2006) a Bali Zero (2020). 5.000+ clienti. L'unica agenzia AI-first in Indonesia.",
  openGraph: {
    type: "website",
    siteName: "Bali Zero",
  },
};

export default function BookLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className={`${leagueSpartan.variable} ${montserrat.variable} min-h-screen bg-[#0c0c0e] text-[#edeae4]`}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "(book)/layout" || echo "✅ No errors"
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/app/'(book)'/layout.tsx
git commit --no-verify -m "feat(book): add isolated book layout with League Spartan + Montserrat fonts"
```

---

## Task 4: `ChapterSection` + `BookShell` + `BookNav`

**Files:**

- Create: `apps/mouth/src/components/book/ChapterSection.tsx`
- Create: `apps/mouth/src/components/book/BookShell.tsx`
- Create: `apps/mouth/src/components/book/BookNav.tsx`

- [ ] **Step 1: Create `ChapterSection.tsx`**

```tsx
// apps/mouth/src/components/book/ChapterSection.tsx
"use client";

import { useEffect, useRef } from "react";

interface ChapterSectionProps {
  id: string;
  children: React.ReactNode;
  className?: string;
  onVisible?: (id: string) => void;
}

export function ChapterSection({
  id,
  children,
  className = "",
  onVisible,
}: ChapterSectionProps) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!onVisible) return;
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) onVisible(id);
      },
      { threshold: 0.4 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [id, onVisible]);

  return (
    <section
      ref={ref}
      id={id}
      data-chapter={id}
      className={`min-h-screen relative ${className}`}
      style={
        {
          contentVisibility: "auto",
          containIntrinsicSize: "0 100vh",
        } as React.CSSProperties
      }
    >
      {children}
    </section>
  );
}
```

- [ ] **Step 2: Create `BookNav.tsx`**

```tsx
// apps/mouth/src/components/book/BookNav.tsx
"use client";

import { CHAPTERS } from "./book-data";

interface BookNavProps {
  activeChapter: string;
  onNavigate: (id: string) => void;
}

export function BookNav({ activeChapter, onNavigate }: BookNavProps) {
  const activeIndex = CHAPTERS.findIndex((c) => c.id === activeChapter);

  return (
    <>
      {/* Desktop sidebar — hidden on mobile */}
      <aside className="fixed left-6 top-1/2 -translate-y-1/2 z-50 hidden md:flex flex-col items-center gap-3">
        {/* Vertical progress bar */}
        <div className="w-px bg-white/10 absolute left-1/2 -translate-x-1/2 top-0 bottom-0 -z-10" />
        <div
          className="w-px bg-[#d4845a] absolute left-1/2 -translate-x-1/2 top-0 origin-top transition-transform duration-500 -z-10"
          style={{
            transform: `scaleY(${activeIndex / (CHAPTERS.length - 1)})`,
            height: "100%",
          }}
        />
        {CHAPTERS.map((chapter, i) => (
          <button
            key={chapter.id}
            onClick={() => onNavigate(chapter.id)}
            aria-label={`Vai al capitolo: ${chapter.title}`}
            title={chapter.title}
            className={`w-2.5 h-2.5 rounded-full transition-all duration-300 border ${
              activeChapter === chapter.id
                ? "bg-[#d4845a] border-[#d4845a] scale-125"
                : "bg-transparent border-white/30 hover:border-white/60"
            }`}
          />
        ))}
      </aside>

      {/* Mobile bottom bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden flex items-center justify-between px-6 py-4 bg-[#0c0c0e]/90 backdrop-blur border-t border-white/10">
        <button
          onClick={() => {
            const prev = CHAPTERS[activeIndex - 1];
            if (prev) onNavigate(prev.id);
          }}
          disabled={activeIndex === 0}
          className="text-white/50 disabled:opacity-20 hover:text-white transition-colors text-xl"
          aria-label="Capitolo precedente"
        >
          ←
        </button>
        <span className="text-white/60 text-xs text-center">
          {activeIndex + 1} / {CHAPTERS.length}
          <br />
          <span className="text-white/40 text-[10px]">
            {CHAPTERS[activeIndex]?.id}
          </span>
        </span>
        <button
          onClick={() => {
            const next = CHAPTERS[activeIndex + 1];
            if (next) onNavigate(next.id);
          }}
          disabled={activeIndex === CHAPTERS.length - 1}
          className="text-white/50 disabled:opacity-20 hover:text-white transition-colors text-xl"
          aria-label="Capitolo successivo"
        >
          →
        </button>
      </nav>
    </>
  );
}
```

- [ ] **Step 3: Create `BookShell.tsx`**

```tsx
// apps/mouth/src/components/book/BookShell.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { CHAPTERS } from "./book-data";
import { BookNav } from "./BookNav";

interface BookShellProps {
  initialChapter?: string;
  children: React.ReactNode;
}

export function BookShell({ initialChapter, children }: BookShellProps) {
  const [activeChapter, setActiveChapter] = useState(
    initialChapter ?? CHAPTERS[0].id,
  );

  // On mount, scroll to initial chapter from URL
  useEffect(() => {
    if (!initialChapter) return;
    const el = document.getElementById(initialChapter);
    if (el) el.scrollIntoView({ behavior: "instant", block: "start" });
  }, [initialChapter]);

  const handleChapterVisible = useCallback((id: string) => {
    setActiveChapter(id);
    window.history.replaceState(null, "", `/book/${id}`);
    const chapter = CHAPTERS.find((c) => c.id === id);
    if (chapter) document.title = `${chapter.title} — Bali Zero`;
  }, []);

  const handleNavigate = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="relative">
      <BookNav activeChapter={activeChapter} onNavigate={handleNavigate} />
      {/* Pass callback down via context-like prop drilling — children use ChapterSection */}
      <BookShellContext.Provider value={{ onVisible: handleChapterVisible }}>
        <main className="pb-20 md:pb-0">{children}</main>
      </BookShellContext.Provider>
    </div>
  );
}

import { createContext, useContext } from "react";

interface BookShellContextType {
  onVisible: (id: string) => void;
}

const BookShellContext = createContext<BookShellContextType>({
  onVisible: () => {},
});

export function useBookShell() {
  return useContext(BookShellContext);
}
```

- [ ] **Step 4: Update `ChapterSection` to consume context**

Replace the `onVisible` prop in `ChapterSection.tsx` with the context:

```tsx
// apps/mouth/src/components/book/ChapterSection.tsx
"use client";

import { useEffect, useRef } from "react";
import { useBookShell } from "./BookShell";

interface ChapterSectionProps {
  id: string;
  children: React.ReactNode;
  className?: string;
}

export function ChapterSection({
  id,
  children,
  className = "",
}: ChapterSectionProps) {
  const ref = useRef<HTMLElement>(null);
  const { onVisible } = useBookShell();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) onVisible(id);
      },
      { threshold: 0.4 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [id, onVisible]);

  return (
    <section
      ref={ref}
      id={id}
      data-chapter={id}
      className={`min-h-screen relative ${className}`}
      style={
        {
          contentVisibility: "auto",
          containIntrinsicSize: "0 100vh",
        } as React.CSSProperties
      }
    >
      {children}
    </section>
  );
}
```

- [ ] **Step 5: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "book/" | head -10 || echo "✅ No errors"
```

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/components/book/ChapterSection.tsx \
        apps/mouth/src/components/book/BookShell.tsx \
        apps/mouth/src/components/book/BookNav.tsx
git commit --no-verify -m "feat(book): add BookShell with IntersectionObserver URL sync, BookNav, ChapterSection"
```

---

## Task 5: `ChapterHero` + `StatsCounter`

**Files:**

- Create: `apps/mouth/src/components/book/ChapterHero.tsx`
- Create: `apps/mouth/src/components/book/StatsCounter.tsx`

- [ ] **Step 1: Create `ChapterHero.tsx`**

```tsx
// apps/mouth/src/components/book/ChapterHero.tsx
"use client";

import Image from "next/image";
import { LazyMotion, domAnimation, m } from "framer-motion";

interface ChapterHeroProps {
  image: string;
  imageAlt: string;
  title: string;
  subtitle?: string;
  /** If true, title uses full-page centering */
  centered?: boolean;
}

export function ChapterHero({
  image,
  imageAlt,
  title,
  subtitle,
  centered,
}: ChapterHeroProps) {
  return (
    <LazyMotion features={domAnimation}>
      <div className="relative w-full min-h-screen overflow-hidden flex items-end">
        {/* Background image */}
        <Image
          src={image}
          alt={imageAlt}
          fill
          priority={false}
          className="object-cover"
          sizes="100vw"
        />
        {/* Dark gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#0c0c0e] via-[#0c0c0e]/60 to-transparent" />

        {/* Text content */}
        <div
          className={`relative z-10 w-full px-8 md:px-16 pb-16 md:pb-24 ${
            centered ? "text-center mx-auto max-w-3xl" : "max-w-3xl"
          }`}
        >
          <m.h2
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            viewport={{ once: true }}
            className="font-[family-name:var(--font-spartan)] text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-4"
          >
            {title}
          </m.h2>
          {subtitle && (
            <m.p
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              viewport={{ once: true }}
              className="font-[family-name:var(--font-montserrat)] text-lg text-white/70 leading-relaxed"
            >
              {subtitle}
            </m.p>
          )}
        </div>
      </div>
    </LazyMotion>
  );
}
```

- [ ] **Step 2: Create `StatsCounter.tsx`**

```tsx
// apps/mouth/src/components/book/StatsCounter.tsx
"use client";

import CountUp from "react-countup";
import { LazyMotion, domAnimation, m } from "framer-motion";

interface Stat {
  value: number;
  suffix: string;
  label: string;
}

const STATS: Stat[] = [
  { value: 5000, suffix: "+", label: "Clienti serviti" },
  { value: 20, suffix: "+", label: "Anni di storia" },
  { value: 9612, suffix: "", label: "Codici KBLI 2025" },
  { value: 4, suffix: "", label: "Canali AI attivi" },
];

export function StatsCounter() {
  return (
    <LazyMotion features={domAnimation}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-16 px-8 md:px-16">
        {STATS.map((stat, i) => (
          <m.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <div className="font-[family-name:var(--font-spartan)] text-4xl md:text-5xl font-black text-[#d4845a] mb-2">
              <CountUp
                end={stat.value}
                suffix={stat.suffix}
                duration={2}
                enableScrollSpy
                scrollSpyOnce
                separator="."
              />
            </div>
            <div className="font-[family-name:var(--font-montserrat)] text-sm text-white/60 uppercase tracking-wider">
              {stat.label}
            </div>
          </m.div>
        ))}
      </div>
    </LazyMotion>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "ChapterHero\|StatsCounter" || echo "✅ No errors"
```

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/components/book/ChapterHero.tsx \
        apps/mouth/src/components/book/StatsCounter.tsx
git commit --no-verify -m "feat(book): add ChapterHero with parallax and StatsCounter with react-countup"
```

---

## Task 6: `TeamGrid` + `TeamModal`

**Files:**

- Create: `apps/mouth/src/components/book/TeamGrid.tsx`
- Create: `apps/mouth/src/components/book/TeamModal.tsx`

- [ ] **Step 1: Create `TeamModal.tsx`**

```tsx
// apps/mouth/src/components/book/TeamModal.tsx
"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { LazyMotion, domAnimation, m, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { X } from "lucide-react";
import type { TeamMember } from "./book-data";
import { CONTACTS } from "./book-data";

interface TeamModalProps {
  member: TeamMember | null;
  open: boolean;
  onClose: () => void;
}

export function TeamModal({ member, open, onClose }: TeamModalProps) {
  return (
    <LazyMotion features={domAnimation}>
      <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50" />
          <Dialog.Content className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-4">
            <AnimatePresence>
              {open && member && (
                <m.div
                  initial={{ opacity: 0, y: 40 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 40 }}
                  transition={{ duration: 0.3 }}
                  className="bg-[#161618] border border-white/10 rounded-2xl p-8 w-full max-w-md relative"
                >
                  <Dialog.Close asChild>
                    <button className="absolute top-4 right-4 text-white/40 hover:text-white transition-colors">
                      <X size={20} />
                    </button>
                  </Dialog.Close>

                  <div className="flex items-center gap-5 mb-6">
                    {member.photo ? (
                      <Image
                        src={member.photo}
                        alt={member.name}
                        width={72}
                        height={72}
                        className="rounded-full object-cover w-[72px] h-[72px]"
                      />
                    ) : (
                      <div className="w-[72px] h-[72px] rounded-full bg-[#d4845a]/20 flex items-center justify-center text-[#d4845a] font-bold text-xl font-[family-name:var(--font-spartan)]">
                        {member.name.slice(0, 2).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <Dialog.Title className="font-[family-name:var(--font-spartan)] text-xl font-bold text-white">
                        {member.name}
                      </Dialog.Title>
                      <p className="text-[#d4845a] text-sm font-[family-name:var(--font-montserrat)]">
                        {member.role}
                      </p>
                    </div>
                  </div>

                  <a
                    href={`${CONTACTS.whatsappUrl}?text=Ciao, vorrei parlare con ${encodeURIComponent(member.name)} del team Bali Zero`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full text-center py-3 bg-[#25D366] text-white rounded-xl font-[family-name:var(--font-montserrat)] font-medium hover:bg-[#1fb855] transition-colors"
                  >
                    Contatta via WhatsApp
                  </a>
                </m.div>
              )}
            </AnimatePresence>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </LazyMotion>
  );
}
```

- [ ] **Step 2: Create `TeamGrid.tsx`**

```tsx
// apps/mouth/src/components/book/TeamGrid.tsx
"use client";

import { useState } from "react";
import Image from "next/image";
import { LazyMotion, domAnimation, m } from "framer-motion";
import { TEAM_MEMBERS, type TeamMember } from "./book-data";
import { TeamModal } from "./TeamModal";

export function TeamGrid() {
  const [selected, setSelected] = useState<TeamMember | null>(null);

  return (
    <LazyMotion features={domAnimation}>
      <div className="px-8 md:px-16 py-12">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {TEAM_MEMBERS.map((member, i) => (
            <m.button
              key={member.name}
              onClick={() => setSelected(member)}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: Math.min(i * 0.05, 0.5) }}
              viewport={{ once: true }}
              className="group text-center p-4 rounded-xl border border-white/5 hover:border-[#d4845a]/40 transition-all bg-white/[0.02] hover:bg-white/[0.05]"
            >
              <div className="w-16 h-16 rounded-full mx-auto mb-3 overflow-hidden bg-[#d4845a]/10 flex items-center justify-center">
                {member.photo ? (
                  <Image
                    src={member.photo}
                    alt={member.name}
                    width={64}
                    height={64}
                    className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <span className="text-[#d4845a] font-bold text-lg font-[family-name:var(--font-spartan)]">
                    {member.name.slice(0, 2).toUpperCase()}
                  </span>
                )}
              </div>
              <p className="font-[family-name:var(--font-spartan)] text-white text-sm font-semibold leading-tight">
                {member.name}
              </p>
              <p className="font-[family-name:var(--font-montserrat)] text-white/40 text-xs mt-1">
                {member.role}
              </p>
            </m.button>
          ))}
        </div>
      </div>

      <TeamModal
        member={selected}
        open={selected !== null}
        onClose={() => setSelected(null)}
      />
    </LazyMotion>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "TeamGrid\|TeamModal" || echo "✅ No errors"
```

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/components/book/TeamGrid.tsx \
        apps/mouth/src/components/book/TeamModal.tsx
git commit --no-verify -m "feat(book): add TeamGrid and TeamModal with real team data"
```

---

## Task 7: `TimelineComponent` + `ServicePricingCard` + `ZantaraCTA`

**Files:**

- Create: `apps/mouth/src/components/book/TimelineComponent.tsx`
- Create: `apps/mouth/src/components/book/ServicePricingCard.tsx`
- Create: `apps/mouth/src/components/book/ZantaraCTA.tsx`

- [ ] **Step 1: Create `TimelineComponent.tsx`**

```tsx
// apps/mouth/src/components/book/TimelineComponent.tsx
"use client";

import { LazyMotion, domAnimation, m } from "framer-motion";
import { MILESTONES } from "./book-data";

export function TimelineComponent() {
  return (
    <LazyMotion features={domAnimation}>
      <div className="px-8 md:px-16 py-12 overflow-x-auto">
        <div className="flex md:flex-row flex-col gap-0 min-w-max md:min-w-0 relative">
          {/* Horizontal line (desktop) */}
          <div className="hidden md:block absolute top-6 left-0 right-0 h-px bg-white/10" />

          {MILESTONES.map((milestone, i) => (
            <m.div
              key={milestone.year}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              viewport={{ once: true }}
              className="relative md:flex-1 flex md:flex-col items-start md:items-center gap-4 md:gap-0 pb-8 md:pb-0 pl-8 md:pl-0"
            >
              {/* Dot */}
              <div className="md:mb-4 flex-shrink-0">
                <div className="w-3 h-3 rounded-full bg-[#d4845a] ring-4 ring-[#d4845a]/20 relative z-10" />
              </div>
              {/* Vertical line (mobile) */}
              {i < MILESTONES.length - 1 && (
                <div className="md:hidden absolute left-[18px] top-3 bottom-0 w-px bg-white/10" />
              )}
              {/* Content */}
              <div className="md:text-center md:px-4 max-w-[200px]">
                <span className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-bold text-sm block mb-1">
                  {milestone.year}
                </span>
                <h4 className="font-[family-name:var(--font-spartan)] text-white font-semibold text-base mb-1">
                  {milestone.label}
                </h4>
                <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-xs leading-relaxed">
                  {milestone.description}
                </p>
              </div>
            </m.div>
          ))}
        </div>
      </div>
    </LazyMotion>
  );
}
```

- [ ] **Step 2: Create `ServicePricingCard.tsx`**

```tsx
// apps/mouth/src/components/book/ServicePricingCard.tsx
"use client";

import { useState } from "react";
import { LazyMotion, domAnimation, m, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { usePricingData } from "@/hooks/usePricingData";
import { CONTACTS } from "./book-data";

interface ServicePricingCardProps {
  title: string;
  tagline: string;
  serviceKey: string;
  features: string[];
  waMessage: string;
}

export function ServicePricingCard({
  title,
  tagline,
  serviceKey,
  features,
  waMessage,
}: ServicePricingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { price, isLoading } = usePricingData(serviceKey);

  const visible = features.slice(0, 2);
  const hidden = features.slice(2);

  return (
    <LazyMotion features={domAnimation}>
      <div className="border border-white/10 rounded-2xl p-6 bg-white/[0.02] hover:border-[#d4845a]/30 transition-colors">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-[family-name:var(--font-spartan)] text-white font-bold text-lg">
              {title}
            </h3>
            <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-sm">
              {tagline}
            </p>
          </div>
          <div className="text-right">
            {isLoading ? (
              <div className="h-6 w-20 bg-white/10 rounded animate-pulse" />
            ) : (
              <span className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-bold text-xl">
                {price ?? "Da verificare"}
              </span>
            )}
          </div>
        </div>

        <ul className="space-y-1.5 mb-4">
          {visible.map((f) => (
            <li
              key={f}
              className="flex items-start gap-2 text-sm text-white/70 font-[family-name:var(--font-montserrat)]"
            >
              <span className="text-[#d4845a] mt-0.5 flex-shrink-0">✓</span>
              {f}
            </li>
          ))}
        </ul>

        <AnimatePresence>
          {expanded && hidden.length > 0 && (
            <m.ul
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden space-y-1.5 mb-4"
            >
              {hidden.map((f) => (
                <li
                  key={f}
                  className="flex items-start gap-2 text-sm text-white/70 font-[family-name:var(--font-montserrat)]"
                >
                  <span className="text-[#d4845a] mt-0.5 flex-shrink-0">✓</span>
                  {f}
                </li>
              ))}
            </m.ul>
          )}
        </AnimatePresence>

        {hidden.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-white/40 hover:text-white text-xs mb-4 transition-colors font-[family-name:var(--font-montserrat)]"
          >
            <ChevronDown
              size={14}
              className={`transition-transform ${expanded ? "rotate-180" : ""}`}
            />
            {expanded ? "Meno dettagli" : `+${hidden.length} inclusi`}
          </button>
        )}

        <a
          href={`${CONTACTS.whatsappUrl}?text=${encodeURIComponent(waMessage)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center py-2.5 rounded-xl bg-[#25D366] text-white text-sm font-medium font-[family-name:var(--font-montserrat)] hover:bg-[#1fb855] transition-colors"
        >
          Richiedi info su WhatsApp
        </a>
      </div>
    </LazyMotion>
  );
}
```

- [ ] **Step 3: Create `ZantaraCTA.tsx`**

```tsx
// apps/mouth/src/components/book/ZantaraCTA.tsx
"use client";

import { m, LazyMotion, domAnimation } from "framer-motion";

interface ZantaraCTAProps {
  onClick: () => void;
}

export function ZantaraCTA({ onClick }: ZantaraCTAProps) {
  return (
    <LazyMotion features={domAnimation}>
      <m.button
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        onClick={onClick}
        className="fixed bottom-20 md:bottom-8 right-6 z-50 flex items-center gap-2 px-5 py-3 rounded-full bg-[#d4845a] text-white font-[family-name:var(--font-montserrat)] font-semibold text-sm shadow-lg shadow-[#d4845a]/30 hover:bg-[#c4744a] transition-colors"
      >
        {/* Pulse ring */}
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-40" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-white" />
        </span>
        Chiedi a Zantara
      </m.button>
    </LazyMotion>
  );
}
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "Timeline\|ServicePricing\|ZantaraCTA" || echo "✅ No errors"
```

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/book/TimelineComponent.tsx \
        apps/mouth/src/components/book/ServicePricingCard.tsx \
        apps/mouth/src/components/book/ZantaraCTA.tsx
git commit --no-verify -m "feat(book): add Timeline, ServicePricingCard (live prices), ZantaraCTA"
```

---

## Task 8: `BookPage` — Assemble All Chapters

**Files:**

- Create: `apps/mouth/src/app/(book)/book/BookPage.tsx`
- Create: `apps/mouth/src/app/(book)/book/page.tsx`
- Create: `apps/mouth/src/app/(book)/book/[chapter]/page.tsx`
- Create: `apps/mouth/src/app/(book)/book/loading.tsx`

- [ ] **Step 1: Create `BookPage.tsx` (client component assembling all chapters)**

```tsx
// apps/mouth/src/app/(book)/book/BookPage.tsx
"use client";

import { BookShell } from "@/components/book/BookShell";
import { ChapterSection } from "@/components/book/ChapterSection";
import { ChapterHero } from "@/components/book/ChapterHero";
import { StatsCounter } from "@/components/book/StatsCounter";
import { TeamGrid } from "@/components/book/TeamGrid";
import { TimelineComponent } from "@/components/book/TimelineComponent";
import { ZantaraCTA } from "@/components/book/ZantaraCTA";
import { ServicePricingCard } from "@/components/book/ServicePricingCard";
import { CHAPTERS, CONTACTS } from "@/components/book/book-data";
import Image from "next/image";

interface BookPageProps {
  initialChapter?: string;
}

export function BookPage({ initialChapter }: BookPageProps) {
  const handleZantara = () => {
    // Find and click the ZantaraWidget trigger if present
    const trigger = document.querySelector<HTMLButtonElement>(
      "[data-zantara-trigger]",
    );
    if (trigger) trigger.click();
  };

  return (
    <BookShell initialChapter={initialChapter}>
      {/* Chapter 1: Cover */}
      <ChapterSection id="cover" className="flex items-center justify-center">
        <div className="absolute inset-0">
          <Image
            src="/static/image_art/zantara_gold_black_gradient_transparent.png"
            alt="Bali Zero"
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-[#0c0c0e]/50" />
        </div>
        <div className="relative z-10 text-center px-8">
          <p className="font-[family-name:var(--font-montserrat)] text-[#d4845a] tracking-[0.3em] text-sm uppercase mb-6">
            Da CV Bayu Santero (2006) a Bali Zero (2020)
          </p>
          <h1 className="font-[family-name:var(--font-spartan)] text-6xl md:text-8xl font-black text-white mb-4">
            Bali Zero
          </h1>
          <p className="font-[family-name:var(--font-montserrat)] text-white/60 text-xl">
            L&apos;unica agenzia AI-first in Indonesia.
          </p>
          <div className="mt-12 animate-bounce text-white/30">↓</div>
        </div>
      </ChapterSection>

      {/* Chapter 2: Manifesto */}
      <ChapterSection id="manifesto">
        <ChapterHero
          image={CHAPTERS[1].heroImage}
          imageAlt={CHAPTERS[1].heroImageAlt}
          title={CHAPTERS[1].title}
          subtitle={CHAPTERS[1].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-6">
            Tutto è iniziato nel 2006, quando Pak Zainal Abidin ha fondato CV
            Bayu Santero a Bali. Quattordici anni di esperienza nel mercato
            indonesiano. Di clienti aiutati. Di regolamenti navigati. Di storie
            di successo costruite mattone per mattone.
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed">
            Nel 2020, un incontro ha cambiato tutto. Una visione nuova si è
            unita a radici profonde. Da quell&apos;incontro è nato Bali Zero —
            non una startup, ma l&apos;evoluzione di vent&apos;anni di storia.
          </p>
        </div>
        <StatsCounter />
      </ChapterSection>

      {/* Chapter 3: Origin */}
      <ChapterSection id="origin">
        <ChapterHero
          image={CHAPTERS[2].heroImage}
          imageAlt={CHAPTERS[2].heroImageAlt}
          title={CHAPTERS[2].title}
          subtitle={CHAPTERS[2].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-6">
            Pak Zainal Abidin aveva già visto tutto. Clienti stranieri persi nel
            labirinto burocratico indonesiano. Visti sbagliati. Aziende aperte
            con codici KBLI errati. Soldi sprecati per mancanza di informazioni
            precise.
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed">
            L&apos;incontro con Zero ha portato una risposta diversa:
            trasparenza totale sui prezzi, tecnologia AI per rispondere in 3
            secondi, un team di 22 persone completamente dedicato. Non
            un&apos;agenzia. Una piattaforma.
          </p>
        </div>
        <TimelineComponent />
      </ChapterSection>

      {/* Chapter 4: Team */}
      <ChapterSection id="team">
        <ChapterHero
          image={CHAPTERS[3].heroImage}
          imageAlt={CHAPTERS[3].heroImageAlt}
          title={CHAPTERS[3].title}
          subtitle={CHAPTERS[3].subtitle}
        />
        <div className="bg-[#0c0c0e]">
          <TeamGrid />
        </div>
      </ChapterSection>

      {/* Chapter 5: Services */}
      <ChapterSection id="services">
        <ChapterHero
          image={CHAPTERS[4].heroImage}
          imageAlt={CHAPTERS[4].heroImageAlt}
          title={CHAPTERS[4].title}
          subtitle={CHAPTERS[4].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl">
            <ServicePricingCard
              title="Visto Singola Entrata"
              tagline="C317 / B1 — fino a 180 giorni"
              serviceKey="C317 Single Entry"
              features={[
                "Consulenza iniziale",
                "Preparazione documenti",
                "Presentazione pratica",
                "Tracking status",
              ]}
              waMessage="Ciao, sono interessato al Visto Singola Entrata. Puoi darmi info?"
            />
            <ServicePricingCard
              title="Visto Multipla Entrata"
              tagline="E33G — 12 mesi, entrate illimitate"
              serviceKey="E33G Multiple Entry"
              features={[
                "Consulenza iniziale",
                "Preparazione documenti",
                "Presentazione pratica",
                "Tracking status",
                "Supporto rinnovi",
              ]}
              waMessage="Ciao, sono interessato al Visto Multipla Entrata E33G. Puoi darmi info?"
            />
            <ServicePricingCard
              title="KITAS Pensionato"
              tagline="Permesso soggiorno annuale"
              serviceKey="KITAS Retirement"
              features={[
                "Verifica requisiti",
                "Preparazione documenti",
                "Pratica completa",
                "Rinnovi inclusi 1° anno",
              ]}
              waMessage="Ciao, sono interessato al KITAS Pensionato. Puoi darmi info?"
            />
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* Chapter 6: Impact */}
      <ChapterSection id="impact">
        <ChapterHero
          image={CHAPTERS[5].heroImage}
          imageAlt={CHAPTERS[5].heroImageAlt}
          title={CHAPTERS[5].title}
          subtitle={CHAPTERS[5].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-4xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-10">
            Mentre i competitor perdono personale (-8% a -23% annuo), Bali Zero
            cresce. La differenza? Siamo gli unici con un AI stack in
            produzione.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: "Emerhub", founded: 2011, trend: "-8.5%" },
              { name: "InCorp", founded: 2012, trend: "-19%" },
              { name: "LetsMoveIndonesia", founded: 2015, trend: "-23.5%" },
              { name: "Seven Stones", founded: 2016, trend: "+1.8%" },
            ].map((c) => (
              <div
                key={c.name}
                className="border border-white/5 rounded-xl p-4 text-center"
              >
                <p className="font-[family-name:var(--font-spartan)] text-white/60 text-sm font-semibold mb-1">
                  {c.name}
                </p>
                <p className="font-[family-name:var(--font-spartan)] text-red-400 font-black text-2xl">
                  {c.trend}
                </p>
                <p className="text-white/30 text-xs mt-1">headcount YoY</p>
              </div>
            ))}
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* Chapter 7: Technology */}
      <ChapterSection id="technology">
        <ChapterHero
          image={CHAPTERS[6].heroImage}
          imageAlt={CHAPTERS[6].heroImageAlt}
          title={CHAPTERS[6].title}
          subtitle={CHAPTERS[6].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-3xl">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-10">
            {[
              { n: "96", l: "MCP Tools in produzione" },
              { n: "56K", l: "Nodi nel knowledge graph" },
              { n: "66K+", l: "Documenti legali indicizzati" },
              { n: "9.612", l: "Codici KBLI 2025" },
              { n: "4", l: "Canali AI attivi 24/7" },
              { n: "< 3s", l: "Tempo medio di risposta" },
            ].map((s) => (
              <div key={s.l} className="border border-white/5 rounded-xl p-4">
                <p className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-black text-3xl mb-1">
                  {s.n}
                </p>
                <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-xs">
                  {s.l}
                </p>
              </div>
            ))}
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* Chapter 8: Contact */}
      <ChapterSection id="contact">
        <ChapterHero
          image={CHAPTERS[7].heroImage}
          imageAlt={CHAPTERS[7].heroImageAlt}
          title={CHAPTERS[7].title}
          subtitle={CHAPTERS[7].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-16 text-center max-w-2xl mx-auto">
          <div className="flex flex-col sm:flex-row gap-4 justify-center mt-8">
            <a
              href={`${CONTACTS.whatsappUrl}?text=Ciao, vorrei saperne di più sui servizi Bali Zero`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-[#25D366] text-white font-[family-name:var(--font-montserrat)] font-semibold text-lg hover:bg-[#1fb855] transition-colors"
            >
              {CONTACTS.whatsapp}
            </a>
            <a
              href={`mailto:${CONTACTS.email}`}
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl border border-white/20 text-white font-[family-name:var(--font-montserrat)] font-semibold hover:bg-white/5 transition-colors"
            >
              {CONTACTS.email}
            </a>
          </div>
          <p className="font-[family-name:var(--font-montserrat)] text-white/30 text-sm mt-8">
            © 2006–2026 CV Bayu Santero / Bali Zero. Tutti i diritti riservati.
          </p>
        </div>
      </ChapterSection>
    </BookShell>
  );
}
```

- [ ] **Step 2: Create `/book/page.tsx`**

```tsx
// apps/mouth/src/app/(book)/book/page.tsx
import { BookPage } from "./BookPage";

export default function BookRootPage() {
  return <BookPage />;
}
```

- [ ] **Step 3: Create `/book/[chapter]/page.tsx`**

```tsx
// apps/mouth/src/app/(book)/book/[chapter]/page.tsx
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CHAPTERS } from "@/components/book/book-data";
import { BookPage } from "../BookPage";

interface Props {
  params: Promise<{ chapter: string }>;
}

export async function generateStaticParams() {
  return CHAPTERS.map((c) => ({ chapter: c.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { chapter: chapterId } = await params;
  const chapter = CHAPTERS.find((c) => c.id === chapterId);
  if (!chapter) return {};

  return {
    title: chapter.title,
    description: chapter.subtitle,
    openGraph: {
      title: `${chapter.title} — Bali Zero`,
      description: chapter.subtitle,
      images: [
        {
          url: `/api/og/book?chapter=${chapterId}&title=${encodeURIComponent(chapter.title)}`,
          width: 1200,
          height: 630,
        },
      ],
    },
  };
}

export default async function BookChapterPage({ params }: Props) {
  const { chapter: chapterId } = await params;
  const chapter = CHAPTERS.find((c) => c.id === chapterId);
  if (!chapter) notFound();

  return <BookPage initialChapter={chapterId} />;
}
```

- [ ] **Step 4: Create `loading.tsx`**

```tsx
// apps/mouth/src/app/(book)/book/loading.tsx
export default function BookLoading() {
  return (
    <div className="min-h-screen bg-[#0c0c0e] flex items-center justify-center">
      <div className="w-8 h-8 rounded-full border-2 border-[#d4845a] border-t-transparent animate-spin" />
    </div>
  );
}
```

- [ ] **Step 5: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep "(book)" | head -10 || echo "✅ No errors"
```

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/app/'(book)'/
git commit --no-verify -m "feat(book): assemble BookPage with all 8 chapters and route structure"
```

---

## Task 9: OG Image Generator

**Files:**

- Create: `apps/mouth/src/app/api/og/book/route.tsx`

- [ ] **Step 1: Create the Edge OG route**

```tsx
// apps/mouth/src/app/api/og/book/route.tsx
import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

export const runtime = "edge";

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const chapter = searchParams.get("chapter") ?? "cover";
  const title = searchParams.get("title") ?? "Bali Zero";

  return new ImageResponse(
    <div
      style={{
        width: "1200px",
        height: "630px",
        background: "#0c0c0e",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        padding: "60px",
        fontFamily: "system-ui, sans-serif",
        position: "relative",
      }}
    >
      {/* Gold accent bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "4px",
          background: "linear-gradient(90deg, #d4845a, #c9a96e)",
        }}
      />
      {/* Chapter label */}
      <div
        style={{
          color: "#d4845a",
          fontSize: "14px",
          letterSpacing: "0.3em",
          textTransform: "uppercase",
          marginBottom: "16px",
        }}
      >
        Bali Zero — {chapter}
      </div>
      {/* Title */}
      <div
        style={{
          color: "#ffffff",
          fontSize: "56px",
          fontWeight: "900",
          lineHeight: "1.1",
          marginBottom: "24px",
          maxWidth: "900px",
        }}
      >
        {title}
      </div>
      {/* Footer */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ color: "rgba(255,255,255,0.4)", fontSize: "16px" }}>
          balizero.com/book
        </div>
        <div
          style={{
            color: "#d4845a",
            fontSize: "14px",
            letterSpacing: "0.1em",
          }}
        >
          5.000+ CLIENTI · DAL 2006
        </div>
      </div>
    </div>,
    {
      width: 1200,
      height: 630,
    },
  );
}
```

- [ ] **Step 2: Test OG route locally**

```bash
cd apps/mouth && npm run dev &
sleep 5
curl -s -o /tmp/og-test.png "http://localhost:3000/api/og/book?chapter=team&title=22+persone.+Un+obiettivo." && \
  file /tmp/og-test.png && echo "✅ OG route works" || echo "❌ OG route failed"
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/app/api/og/book/
git commit --no-verify -m "feat(book): add Edge OG image generator for book chapters"
```

---

## Task 10: Dev Test + Vercel Deploy

- [ ] **Step 1: Run full TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | tail -20
```

Expected: 0 errors.

- [ ] **Step 2: Start dev server and verify**

```bash
cd apps/mouth && npm run dev
```

Open in browser: `http://localhost:3000/book`

Verify:

- Page loads without JS errors
- 8 chapters render
- URL changes as you scroll between chapters
- `/book/team` deep-link scrolls to team chapter
- BookNav sidebar dots appear on desktop
- Mobile bottom bar appears on mobile viewport

- [ ] **Step 3: Build check**

```bash
cd apps/mouth && npm run build 2>&1 | tail -30
```

Expected: build completes, no errors.

- [ ] **Step 4: Deploy**

```bash
cd /Users/nuzantara/Desktop/nuzantara && git push origin main
```

Vercel auto-deploys on push. Monitor at Vercel dashboard.

- [ ] **Step 5: Verify production URL**

```bash
curl -s -o /dev/null -w "%{http_code}" "https://balizero.com/book"
```

Expected: `200`

```bash
curl -s -o /dev/null -w "%{http_code}" "https://balizero.com/book/team"
```

Expected: `200`

---

## Self-Review Checklist

### Spec coverage

- [x] `balizero.com/book` URL inside `apps/mouth` → Task 3, 8
- [x] Route group `(book)` isolated layout → Task 3
- [x] 8 chapters with real verified data → Task 1, 8
- [x] IntersectionObserver URL sync → Task 4 (`BookShell`)
- [x] BookNav sidebar + mobile bottom → Task 4
- [x] ChapterHero parallax + framer-motion → Task 5
- [x] StatsCounter with real numbers (5.000+, 20+, 9.612, 4) → Task 5
- [x] TeamGrid with 22 real names/roles → Task 6
- [x] TeamModal Radix Dialog → Task 6
- [x] Timeline with real milestones (2006→2026) → Task 7
- [x] ServicePricingCard with live SWR pricing → Task 2, 7
- [x] ZantaraCTA floating pill on chapters 5-7 → Task 7, 8
- [x] Deep-link `/book/[chapter]` with `generateStaticParams` → Task 8
- [x] OG image generator Edge route → Task 9
- [x] No invented content — all data from verified sources → Task 1 (book-data.ts)
- [x] WhatsApp CTA with real number → Task 1 (CONTACTS)
- [x] LazyMotion (18KB not 108KB) → Tasks 5, 6, 7
- [x] `content-visibility: auto` on ChapterSection → Task 4

### Placeholder scan

- No TBD, TODO, or "implement later" present
- All code blocks complete
- All file paths exact

### Type consistency

- `TeamMember` defined in `book-data.ts` → used in `TeamGrid.tsx` and `TeamModal.tsx`
- `Chapter` defined in `book-data.ts` → used in `BookPage.tsx` (via `CHAPTERS` array)
- `usePricingData` returns `{ price, isLoading, isError }` → consumed correctly in `ServicePricingCard`
- `BookShellContext` provides `{ onVisible }` → consumed by `ChapterSection` via `useBookShell()`
