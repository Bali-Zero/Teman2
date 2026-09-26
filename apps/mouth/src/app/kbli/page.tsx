import type { Metadata } from "next";
import { getAllCodes, getBaliCensus, getSections } from "@/lib/kbli-data";
import { baliBlockedHint } from "@/lib/kbli-bali-block";
import { SECTION_VISUALS } from "@/lib/kbli-cover-design";
import { KBLISearch } from "@/components/kbli/KBLISearch";
import { KBLISectorBrowser } from "@/components/kbli/KBLISectorBrowser";
import { KBLISectorDial } from "@/components/kbli/KBLISectorDial";
import { ZantaraChat } from "@/components/kbli/ZantaraChat";
import { KBLIPersonaDoors } from "@/components/kbli/KBLIPersonaDoors";
import { BZLogo, FunnelFrame } from "@balizero/core";
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

/**
 * /kbli — «La bussola» (BRIEF-v2 §3.4). The landing is an instrument printed
 * on watermarked paper: the lockup, one line, the search needle, the readings
 * line, and the sector dial — all above the fold at 390px. Every figure is
 * computed here at render from the served dataset; none is a literal.
 */
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
  // Added 2026-09-16 (W-J B1 disclose): the readings line reads the
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
  const dialSections = sections.map((s) => ({
    id: s.id,
    nameEn: s.nameEn,
    shortName: SECTION_VISUALS[s.id]?.label ?? s.nameEn,
    codeCount: s.codeCount,
  }));

  return (
    <FunnelFrame funnel="kbli" sessionId="SSR">
      <div className="space-y-12 sm:space-y-16">
        {/* ── THE INSTRUMENT. No z-index and no overflow clip on the plate:
            the results dropdown must open over the page (a stacking context
            would trap its z-50 under the sticky handoff pill, z-40). The
            guilloché sits in its own clipped, aria-hidden layer. ── */}
        <section
          aria-labelledby="kbli-title"
          className="relative -mx-4 border-y border-[var(--kbli-border)] bg-[var(--kbli-bg-surface)] sm:-mx-6 sm:rounded-[var(--kbli-radius-xl)] sm:border lg:-mx-8"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 overflow-hidden sm:rounded-[var(--kbli-radius-xl)]"
          >
            <div className="kbli-guilloche" />
          </div>

          <div className="relative grid gap-6 px-5 pb-8 pt-5 sm:gap-8 sm:px-10 sm:pb-10 sm:pt-9 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] lg:gap-12 lg:px-12 lg:pb-12">
            <div className="min-w-0">
              {/* Lockup — the mark BESIDE the wordmark, never as a letter
                  (design corner §3.6; BRIEF-v2 §2.1). */}
              <div className="r19-lockup">
                <BZLogo variant="mark" size={28} className="r19-lockup__mark" />
                <span className="flex flex-col">
                  <span className="r19-lockup__wordmark">Bali Zero</span>
                  <span className="r19-lockup__product">KBLI Navigator</span>
                </span>
              </div>

              <h1
                id="kbli-title"
                style={{ fontFamily: "var(--font-serif)" }}
                className="mt-4 max-w-[16ch] text-[30px] font-[450] leading-[1.08] tracking-[-0.035em] text-[var(--kbli-text-primary)] sm:mt-8 sm:text-[48px] lg:text-[56px]"
              >
                Find the KBLI 2025 code for your business
              </h1>

              <div id="search" className="mt-4 scroll-mt-24 sm:mt-7">
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

              {/* The readings line — proof is a line, not a section (design
                  corner R4). Every figure keeps its source: the served code
                  list, the sections the dial draws, the Bali census, and
                  trust-figures.ts (the rating links to the live profile). */}
              <p
                data-kbli-readings=""
                className="mt-4 flex flex-wrap items-center gap-x-2.5 gap-y-1 border-t sm:mt-6 border-[var(--kbli-border)] pt-3 text-[13px] tabular-nums text-[var(--kbli-text-secondary)]"
              >
                <span>{codeCount} codes</span>
                <span aria-hidden="true">·</span>
                <span>{sections.length} sections</span>
                <span aria-hidden="true">·</span>
                <span title={baliBlockedHint(allCodes, baliCensus)}>
                  ~{baliBlockedPct}% blocked in Bali
                </span>
                <span aria-hidden="true">·</span>
                <a
                  href={GOOGLE_MAPS_URL}
                  target="_blank"
                  rel="noreferrer"
                  title={`Read on ${MEASURED_ON}`}
                  className="text-[var(--kbli-text-secondary)] underline decoration-[var(--kbli-border-hover)] underline-offset-4 hover:text-[var(--kbli-text-primary)]"
                >
                  ★ {GOOGLE_RATING} ·{" "}
                  {GOOGLE_REVIEW_COUNT.toLocaleString("en-US")} Google reviews
                </a>
              </p>
            </div>

            <div className="min-w-0 lg:border-l lg:border-[var(--kbli-border)] lg:pl-10">
              <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--kbli-text-secondary)]">
                The {sections.length} sections, by number of codes
              </h2>
              <KBLISectorDial
                sections={dialSections}
                totalCodes={allCodes.length}
              />
            </div>
          </div>
        </section>

        <KBLIPersonaDoors />

        <hr aria-hidden="true" className="kbli-tumpal" />

        {/* ── SECTORS ── */}
        <section
          id="sectors"
          aria-labelledby="kbli-sectors"
          className="scroll-mt-20"
        >
          <h2
            id="kbli-sectors"
            style={{ fontFamily: "var(--font-serif)" }}
            className="text-[30px] font-[450] leading-[1.13] tracking-[-0.03em] text-[var(--kbli-text-primary)] sm:text-[38px]"
          >
            Browse by sector
          </h2>
          <p className="mb-6 mt-2 max-w-2xl text-sm text-[var(--kbli-text-secondary)]">
            Each bar compares a sector&apos;s number of codes with the largest,{" "}
            {largest.nameEn} ({largest.codeCount.toLocaleString("en-US")}{" "}
            codes).
          </p>
          <KBLISectorBrowser sections={sections} />
        </section>

        <hr aria-hidden="true" className="kbli-tumpal" />

        {/* ── ZANTARA: a quiet line that opens the chat, not a panel ── */}
        <section aria-labelledby="kbli-ask">
          <details className="group">
            <summary className="flex min-h-[44px] cursor-pointer list-none items-center gap-2 text-[15px] text-[var(--kbli-text-secondary)] [&::-webkit-details-marker]:hidden">
              <h2
                id="kbli-ask"
                className="text-[15px] font-normal text-[var(--kbli-text-secondary)]"
              >
                Still unsure which code fits?{" "}
                <span className="font-semibold text-[var(--kbli-accent)] underline decoration-[var(--kbli-border-accent)] underline-offset-4 group-open:no-underline">
                  Ask Zantara, our KBLI assistant
                </span>
              </h2>
            </summary>
            <div className="mt-4">
              <ZantaraChat
                opener="I'm Zantara, your KBLI expert. Ask me anything about Indonesian business codes — which ones you need, PMA rules, what changed in 2025, or how to set up in Bali."
                suggestions={[
                  "What KBLI do I need for a restaurant in Bali?",
                  "Can foreigners own a villa rental business?",
                  "What changed from KBLI 2020 to 2025?",
                  "What's the difference between 55101 and 55203?",
                ]}
              />
            </div>
          </details>
        </section>
      </div>
    </FunnelFrame>
  );
}
