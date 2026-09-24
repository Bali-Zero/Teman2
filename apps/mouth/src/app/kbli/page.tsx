import type { Metadata } from "next";
import Image from "next/image";
import { getAllCodes, getBaliCensus, getSections } from "@/lib/kbli-data";
import { baliBlockedHint } from "@/lib/kbli-bali-block";
import { KBLISearch } from "@/components/kbli/KBLISearch";
import { KBLISectorBrowser } from "@/components/kbli/KBLISectorBrowser";
import { ZantaraChat } from "@/components/kbli/ZantaraChat";
import { KBLIPersonaDoors } from "@/components/kbli/KBLIPersonaDoors";
import { FunnelFrame } from "@balizero/core";
import {
  GOOGLE_MAPS_URL,
  GOOGLE_RATING,
  GOOGLE_REVIEW_COUNT,
  MEASURED_ON,
} from "@/lib/trust-figures";

export const metadata: Metadata = {
  title: "KBLI 2025 Navigator — Indonesia Business Classification Guide",
  description:
    "Navigate Indonesia's 1,559 KBLI 2025 business codes. PMA investment rules, licensing requirements, and 2020→2025 transition mapping. Powered by Zantara AI.",
  openGraph: {
    title: "KBLI 2025 Navigator — Zantara by Bali Zero",
    description:
      "The definitive guide to Indonesia's KBLI 2025 business classification. 1,559 codes, PMA rules, and AI-powered analysis.",
    type: "website",
  },
  alternates: {
    canonical: "https://balizero.com/kbli",
  },
};

export default async function KBLIHomePage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const initialQuery = q ? decodeURIComponent(q) : "";
  const sections = getSections().filter((s) => s.codeCount > 0);
  const allCodes = getAllCodes();
  const codeCount = allCodes.length.toLocaleString("en-US");
  // Added 2026-09-16 (W-J B1 disclose): the trust-bar stat now reads the
  // canonical Bali status census (`getBaliCensus()`), not the served subset
  // (`allCodes` withholds `baliL4` on most unlocated records) — the served
  // subset alone used to understate the true population ("~1%"/14 of 1559
  // vs. the working census of 135, already published on the honest-map
  // article at /business/the-honest-map-blocked-bali-codes).
  const baliCensus = getBaliCensus();
  const baliBlockedPct = Math.round(
    (baliCensus.filter((c) => c.blocked).length / baliCensus.length) * 100,
  );
  // The sector bars are codeCount / the largest sector's codeCount
  // (KBLISectorGrid); the caption names that reference so the bar reads.
  const largest = sections.reduce((a, b) =>
    b.codeCount > a.codeCount ? b : a,
  );

  return (
    <FunnelFrame funnel="kbli" sessionId="SSR">
      <div className="space-y-14 sm:space-y-16">
        {/* ── HERO: the search is the promise, so it is the peak of the
            first viewport on every width. The hero does not clip its
            children — the results dropdown must open over the page — so
            the ornament and photograph are clipped in their own layer. No
            z-index here: a stacking context would trap the dropdown's z-50
            below the sticky handoff pill (z-40). ── */}
        <section
          aria-labelledby="kbli-title"
          className="relative -mx-4 rounded-3xl border border-white/[0.06] bg-[var(--kbli-ink)] sm:-mx-6 lg:-mx-8"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl"
          >
            <div
              className="absolute inset-0 hidden lg:block"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='none'/%3E%3Crect x='0' y='0' width='200' height='200' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='50' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='30' fill='none' stroke='rgba(255,255,255,0.025)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='8' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='2' fill='rgba(255,255,255,0.05)'/%3E%3Cpath d='M100,50 Q120,70 100,90 Q80,70 100,50Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Cpath d='M100,150 Q120,130 100,110 Q80,130 100,150Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Cpath d='M50,100 Q70,120 90,100 Q70,80 50,100Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Cpath d='M150,100 Q130,120 110,100 Q130,80 150,100Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3C/svg%3E")`,
                backgroundSize: "200px 200px",
              }}
            />
            {/* The editorial still (812x572, see git history for why it is
                not a video) now sits behind the right half as a masked
                backdrop instead of inside a tilted tablet frame. Decorative
                here, so alt is empty; lg+ only, so phones never fetch it. */}
            <div className="absolute inset-y-0 right-0 hidden w-[48%] lg:block">
              <Image
                src="/images/kbli-navigator-hero.jpg"
                alt=""
                fill
                sizes="560px"
                className="object-cover opacity-70"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    "linear-gradient(90deg, var(--kbli-ink) 0%, color-mix(in srgb, var(--kbli-ink) 55%, transparent) 45%, color-mix(in srgb, var(--kbli-ink) 20%, transparent) 100%)",
                }}
              />
            </div>
          </div>

          {/* Phones: the hero fills the first screen and stops just above the
              floating handoff pill, so in the first viewport the pill lands
              on empty ground. Hero top 80px = nav 56 + frame padding 24; the
              pill spans 44px starting 12px above the fold. Bottom edge =
              100svh - 60px, 4px above the pill; the 56px section gap puts the
              first door 8px below it. */}
          <div className="relative flex flex-col px-5 py-8 max-sm:min-h-[calc(100svh-140px)] sm:px-12 sm:py-12 lg:px-16 lg:py-14">
            {/* Product lockup — the mark BESIDE the wordmark, never as a
                letter of it (design corner §3.6). */}
            <div className="flex items-center gap-3">
              <Image
                src="/assets/logo/balizero-logo-clean.png"
                alt="Bali Zero"
                width={36}
                height={36}
                className="rounded-full"
              />
              <span className="text-[13px] font-semibold uppercase tracking-[0.16em] text-white">
                KBLI Navigator
              </span>
            </div>

            <h1
              id="kbli-title"
              className="mt-6 max-w-2xl text-[2.5rem] leading-[1.05] text-white sm:text-5xl lg:max-w-none lg:text-6xl"
            >
              Find your KBLI 2025 business code
            </h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-zinc-300 sm:text-lg">
              Search by activity, keyword or code number, then check foreign
              ownership (PMA), licensing and what changed from KBLI 2020.
            </p>

            <div id="search" className="mt-6 max-w-2xl scroll-mt-24 sm:mt-8">
              <KBLISearch
                autoFocus
                initialQuery={initialQuery}
                placeholder="Search KBLI codes"
                quickFilters={[
                  "Restaurant",
                  "Tech",
                  "Real Estate",
                  "Retail",
                  "Manufacturing",
                ]}
              />
            </div>

            {/* Proof is a line, not a section (design corner R4). Every
                figure keeps its previous source: the served code list, the
                sector count this page always printed, the Bali census, and
                trust-figures.ts (the rating links to the live profile). */}
            <p className="mt-auto flex max-w-2xl flex-wrap items-center gap-x-3 gap-y-1 pt-8 text-[13px] tabular-nums text-zinc-400">
              <span>{codeCount} codes</span>
              <span aria-hidden="true">·</span>
              <span>22 sectors</span>
              <span aria-hidden="true" className="hidden sm:inline">
                ·
              </span>
              <span
                title={baliBlockedHint(allCodes, baliCensus)}
                className="basis-full sm:basis-auto"
              >
                ~{baliBlockedPct}% blocked in Bali
              </span>
              <span aria-hidden="true" className="hidden sm:inline">
                ·
              </span>
              <a
                href={GOOGLE_MAPS_URL}
                target="_blank"
                rel="noreferrer"
                title={`Read on ${MEASURED_ON}`}
                className="basis-full underline decoration-white/20 underline-offset-4 hover:text-zinc-200 hover:decoration-white/50 sm:basis-auto"
              >
                ★ {GOOGLE_RATING} ·{" "}
                {GOOGLE_REVIEW_COUNT.toLocaleString("en-US")} Google reviews
              </a>
            </p>
          </div>
        </section>

        <KBLIPersonaDoors />

        {/* ── SECTORS ── */}
        <section
          id="sectors"
          aria-labelledby="kbli-sectors"
          className="scroll-mt-20"
        >
          <h2 id="kbli-sectors" className="text-3xl text-white">
            Browse by sector
          </h2>
          <p className="mt-2 mb-6 max-w-2xl text-sm text-zinc-300">
            Each bar compares a sector&apos;s number of codes with the largest,{" "}
            {largest.nameEn} ({largest.codeCount.toLocaleString("en-US")}{" "}
            codes).
          </p>
          <KBLISectorBrowser sections={sections} />
        </section>

        {/* ── ZANTARA AI ── */}
        <section aria-labelledby="kbli-ask">
          <h2 id="kbli-ask" className="mb-6 text-3xl text-white">
            Ask Zantara
          </h2>
          <ZantaraChat
            opener="I'm Zantara, your KBLI expert. Ask me anything about Indonesian business codes — which ones you need, PMA rules, what changed in 2025, or how to set up in Bali."
            suggestions={[
              "What KBLI do I need for a restaurant in Bali?",
              "Can foreigners own a villa rental business?",
              "What changed from KBLI 2020 to 2025?",
              "What's the difference between 55101 and 55203?",
            ]}
          />
        </section>
      </div>
    </FunnelFrame>
  );
}
