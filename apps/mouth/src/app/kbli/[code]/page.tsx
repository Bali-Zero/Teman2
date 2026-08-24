import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense, lazy } from "react";
import {
  getAllCodes,
  getCode,
  getRelatedCodes,
  getSectionMeta,
  getHeroStyle,
} from "@/lib/kbli-data";
import {
  getGoldContent,
  getKbliDatasetLastModified,
} from "@/lib/kbli-data.server";
import { formatTimeframe } from "@/lib/kbli-derive";
import { baliBlockClause, isNationalClosure } from "@/lib/kbli-bali-block";
import {
  isLicensingVerificationPending,
  isPmaVerdictVerified,
} from "@/lib/kbli-provenance";
import { kbliMetaDescription, kbliMetaTitle } from "@/lib/kbli-meta";
import { formatPmaOwnership } from "@/lib/kbli-pma-disclosure";
import {
  discloseKbliBaliReason,
  discloseKbliEditorial,
  neutralKbliChatOpener,
} from "@/lib/kbli-pma-editorial";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";
import { PMABadge } from "@/components/kbli/PMABadge";
import { RiskBadge } from "@/components/kbli/RiskBadge";
import { TransitionBadge } from "@/components/kbli/TransitionBadge";
import { BaliStatusBadge } from "@/components/kbli/BaliStatusBadge";
import { ProvenanceBadge } from "@/components/kbli/ProvenanceBadge";
import { KBLIDivergence } from "@/components/kbli/KBLIDivergence";
import { KBLIProvenancePanel } from "@/components/kbli/KBLIProvenancePanel";
import { cn } from "@/lib/utils";
import { KBLICard } from "@/components/kbli/KBLICard";
import {
  KBLICodeJsonLd,
  KBLIBreadcrumbJsonLd,
  KBLIFaqJsonLd,
} from "@/components/kbli/KBLIStructuredData";
import { LicensingSection } from "@/components/kbli/LicensingSection";
import { KBLIBaliContext } from "@/components/kbli/KBLIBaliContext";
import { KBLIEditorial } from "@/components/kbli/KBLIEditorial";
import { KBLIYoullAlsoNeed } from "@/components/kbli/KBLIYoullAlsoNeed";
import { KBLITransitionSources } from "@/components/kbli/KBLITransitionSources";
import { getRelatedArticle } from "@/lib/kbli-articles";
import { GOLD_HERO_IMAGES } from "@/lib/kbli-hero-images";
import { MarkdownClient } from "@/components/kbli/MarkdownClient";
import { KBLIPageTracker } from "@/components/kbli/KBLIPageTracker";
import { KBLIConsultationCTA } from "@/components/kbli/KBLIConsultationCTA";
import { KBLICommonQuestions } from "@/components/kbli/KBLICommonQuestions";
import { FunnelFrame } from "@balizero/core";
import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";

const ZantaraChat = lazy(() =>
  import("@/components/kbli/ZantaraChat").then((mod) => ({
    default: mod.ZantaraChat,
  })),
);

// Full SSG: every code is pre-rendered at build time. With ISR-on-demand the
// Vercel cache reset on each deploy (several/day) served Googlebot cold SSR
// renders — the TTFB spikes behind the /kbli/* crawl-priority gap (GSC
// clean-window investigation 2026-07-03). dynamicParams=false also turns
// invalid codes (e.g. /kbli/10314) into true 404s instead of soft-404 renders.
export const dynamicParams = false;

export async function generateStaticParams() {
  const codes = getAllCodes();
  return codes.map((c) => ({ code: c.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: codeParam } = await params;
  const kbli = getCode(codeParam);
  if (!kbli) return { title: "KBLI Code Not Found" };

  // Metadata surface uses titleEnMeta (full-coverage EN map since the
  // NEXT_PUBLIC_KBLI_META_EN flip, 2026-07-13); the page body below uses
  // titleEn. Batch 3 (v3) replaces the fixed "Indonesia Business Guide 2025"
  // suffix — identical on all 1,559 pages — with the datum the long-tail query
  // is asking for. Composition + its provenance gate live in @/lib/kbli-meta so
  // they are unit-testable: a <title> is a regulatory assertion Google indexes,
  // and unlike the body it cannot carry a "verification pending" qualifier.
  const metaTitleEn = kbli.titleEnMeta ?? kbli.titleEn;
  const title = kbliMetaTitle(kbli, metaTitleEn);
  const description = kbliMetaDescription(kbli, metaTitleEn);

  // Never repeat the Indonesian title twice when no distinct English title exists.
  const keywordTitles =
    metaTitleEn === kbli.titleId
      ? kbli.titleId
      : `${kbli.titleId}, ${metaTitleEn}`;

  return {
    title,
    description,
    keywords: `KBLI ${kbli.code}, ${keywordTitles}, KBLI 2025, Indonesian business classification, PT PMA Bali, company registration Indonesia`,
    openGraph: {
      title,
      description,
      type: "article",
      url: `https://balizero.com/kbli/${kbli.code}`,
      images: [
        {
          // Deterministic editorial cover — kbli-cover-design.ts DNA rendered
          // at request time by /api/og/kbli/[code] (fresh per request).
          url: `https://balizero.com/api/og/kbli/${kbli.code}`,
          width: 1200,
          height: 630,
          alt: `KBLI ${kbli.code} — ${metaTitleEn}`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [`https://balizero.com/api/og/kbli/${kbli.code}`],
    },
    alternates: {
      canonical: `https://balizero.com/kbli/${kbli.code}`,
    },
  };
}

export default async function KBLICodePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code: codeParam } = await params;
  const kbli = getCode(codeParam);
  if (!kbli) notFound();
  const pmaVerdictVerified = isPmaVerdictVerified(kbli);

  const rawGold = getGoldContent(kbli.code);
  const { gold, intel } = discloseKbliEditorial(kbli, rawGold);
  const related = getRelatedCodes(kbli.code, 6);
  const sectionMeta = kbli.section ? getSectionMeta(kbli.section) : null;

  const breadcrumbs = [
    { label: "KBLI Navigator", href: "/kbli" },
    ...(kbli.section
      ? [
          {
            label: `Section ${kbli.section}`,
            href: `/kbli/sectors/${kbli.section}`,
          },
        ]
      : []),
    { label: kbli.code },
  ];

  const isGold = !!gold;
  const heroStyle = getHeroStyle(kbli.section);
  const heroImage = GOLD_HERO_IMAGES[kbli.code] ?? null;
  const article = getRelatedArticle(kbli.code);

  return (
    <>
      <KBLIPageTracker code={kbli.code} tier={kbli.tier} />
      <KBLICodeJsonLd code={kbli} dateModified={getKbliDatasetLastModified()} />
      <KBLIFaqJsonLd code={kbli} />
      <KBLIBreadcrumbJsonLd
        items={[
          { name: "KBLI Navigator", url: "https://balizero.com/kbli" },
          ...(kbli.section
            ? [
                {
                  name: `Section ${kbli.section}`,
                  url: `https://balizero.com/kbli/sectors/${kbli.section}`,
                },
              ]
            : []),
          {
            name: kbli.code,
            url: `https://balizero.com/kbli/${kbli.code}`,
          },
        ]}
      />

      <FunnelFrame
        funnel="kbli"
        sessionId="SSR"
        trust={{
          rating: GOOGLE_RATING,
          reviewCount: GOOGLE_REVIEW_COUNT,
        }}
      >
        <article className="pb-28">
          {/* BREADCRUMB */}
          <KBLIBreadcrumb items={breadcrumbs} />

          {/* HERO ZONE */}
          <div className="relative -mx-4 mb-10 mt-4 overflow-hidden rounded-2xl sm:-mx-6 lg:-mx-8">
            {heroImage ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={heroImage.src}
                  alt={heroImage.alt}
                  className="absolute inset-0 h-full w-full object-cover object-center"
                  loading="eager"
                />
                <div
                  className="absolute inset-0"
                  style={{ background: heroImage.overlay }}
                />
                <div
                  className="absolute inset-0"
                  style={{
                    background: `linear-gradient(to bottom, transparent 20%, rgba(0,0,0,0.15) 55%, var(--kbli-bg-base) 100%)`,
                  }}
                />
              </>
            ) : (
              <>
                <div
                  className="absolute inset-0"
                  style={{
                    background: `linear-gradient(${heroStyle.gradient})`,
                  }}
                />
                <div
                  className="absolute inset-0"
                  style={{ background: heroStyle.pattern }}
                />
                <div
                  className="absolute inset-0"
                  style={{
                    background: `linear-gradient(to bottom, transparent 30%, rgba(43,43,43,0.4) 60%, var(--kbli-bg-base) 100%)`,
                  }}
                />
              </>
            )}
            {/* Noise texture */}
            <div
              className="absolute inset-0 opacity-[0.03]"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
              }}
            />

            {/* Hero content */}
            <div
              className={`relative px-6 pb-8 sm:px-8 lg:px-10 ${isGold ? "pt-24 sm:pt-32" : "pt-16 sm:pt-20"}`}
            >
              {/* Code pill */}
              <div className="mb-4 flex items-center gap-3">
                <span
                  className="inline-flex items-center rounded-full px-3.5 py-1 font-mono text-sm font-bold tracking-wide"
                  style={{
                    background: "rgba(212, 132, 90, 0.15)",
                    color: "var(--kbli-accent)",
                    border: "1px solid rgba(212, 132, 90, 0.25)",
                    backdropFilter: "blur(8px)",
                  }}
                >
                  KBLI {kbli.code}
                </span>
                {isGold && (
                  <span className="text-xs text-amber-400 font-medium">
                    ★ Gold-Tier Intel
                  </span>
                )}
              </div>

              {/* Title with text-shadow for visibility */}
              <h1
                className={`font-black tracking-tight text-white ${isGold ? "text-3xl sm:text-4xl lg:text-5xl" : "text-2xl sm:text-3xl lg:text-4xl"}`}
                style={{ textShadow: "0 2px 8px rgba(0,0,0,0.5)" }}
              >
                {kbli.titleEn}
              </h1>
              <p
                className="mt-2 text-lg text-white/60"
                style={{ textShadow: "0 1px 4px rgba(0,0,0,0.4)" }}
              >
                {kbli.titleId}
              </p>

              {/* Section line */}
              {sectionMeta && (
                <p className="mt-3 text-sm text-white/40">
                  {sectionMeta.icon} Section {kbli.section} —{" "}
                  {sectionMeta.nameEn}
                </p>
              )}

              {/* PMA verdict banner — the binding answer for a PT PMA, aligned with the native app */}
              {(() => {
                const baliBlocked = kbli.baliL4?.blocked === true;
                const exactSpecialCap =
                  kbli.pma.capVerified === true &&
                  kbli.pma.capSpecial === true &&
                  kbli.pma.maxForeign === "special";
                // `pma.status` / `pma.maxForeign` are the annex-default fill,
                // so they say TERBUKA/100 on records whose L4 verdict is a
                // NATIONAL closure — the central bank among them. Reading them
                // alone put "does not apply to a PT PMA in Bali" above an
                // article saying the bar is nationwide. See isNationalClosure.
                const nationallyClosed =
                  isNationalClosure(kbli.baliL4?.status, kbli.code) ||
                  (!exactSpecialCap &&
                    (kbli.pma.status === "closed" ||
                      (kbli.pma.capVerified && kbli.pma.maxForeign === 0)));
                const pmaBlocked =
                  pmaVerdictVerified && (baliBlocked || nationallyClosed);
                const baliVerdictMissing =
                  pmaVerdictVerified &&
                  !nationallyClosed &&
                  kbli.baliL4 === undefined;
                return (
                  <>
                    <div
                      className={cn(
                        "mt-5 rounded-xl border px-4 py-3",
                        !pmaVerdictVerified || baliVerdictMissing
                          ? "border-slate-400/30 bg-slate-400/10"
                          : pmaBlocked
                            ? "border-[var(--kbli-pma-closed)]/30 bg-[var(--kbli-pma-closed-bg)]"
                            : "border-[var(--kbli-pma-open)]/30 bg-[var(--kbli-pma-open-bg)]",
                      )}
                    >
                      <p
                        className={cn(
                          "text-base font-semibold",
                          !pmaVerdictVerified || baliVerdictMissing
                            ? "text-white/70"
                            : pmaBlocked
                              ? "text-[var(--kbli-pma-closed)]"
                              : "text-[var(--kbli-pma-open)]",
                        )}
                      >
                        {!pmaVerdictVerified
                          ? "PMA status not yet verified for this KBLI 2025 code"
                          : nationallyClosed
                            ? `Closed to PMA (national)${kbli.pma.routeTo ? ` — route to the private code ${kbli.pma.routeTo}` : ""}`
                            : baliVerdictMissing
                              ? "Bali-specific status not verified — do not infer registrability from a missing Bali record"
                              : baliBlocked
                                ? "In Bali: a PT PMA cannot register this code"
                                : "Bali record: not blocked by the provincial restriction; national ownership and licensing rules still apply"}
                      </p>
                    </div>
                    {pmaVerdictVerified && baliBlocked && !nationallyClosed && (
                      <div className="mt-3 rounded-xl border border-[var(--kbli-pma-restricted)]/30 bg-[var(--kbli-pma-restricted-bg)] px-4 py-3">
                        <p className="text-sm font-semibold text-[var(--kbli-pma-restricted)]">
                          National procedure — does not apply to a PT PMA in
                          Bali
                        </p>
                        {/* This sentence used to assert ONE cause — "reserved
                            for MSMEs" — for every blocked code, while the Bali
                            badge a few lines below derived the real one from
                            the status. 456 pages render this notice and only
                            39 are MSME-reserved, so 417 contradicted their own
                            badge above the fold. The cause is now derived from
                            the same total function the licensing frame uses. */}
                        <p className="mt-1 text-sm text-[var(--kbli-text-muted)]">
                          In Bali this activity is{" "}
                          {baliBlockClause(kbli.baliL4?.status)}. The national
                          procedure below applies only to non-PMA operators.
                        </p>
                      </div>
                    )}
                  </>
                );
              })()}

              {/* The ARTICLE behind the verdict above.
                  Until 2026-08-02 every one of the 1,559 pages attributed its
                  PMA verdict to "Perpres 10/2021, 49/2021" — the instrument,
                  never the article — so a reader had no way to check it. The
                  citation is computed once, in the compiler that owns the
                  precedence rule, and only read here. Absent artifact → no
                  line: a missing citation costs a reader context, a stale one
                  would tell them the law says something it does not. */}
              {pmaVerdictVerified && kbli.pma.citation && (
                <p className="mt-3 text-xs text-[var(--kbli-text-muted)]">
                  Instrument locator:{" "}
                  <span className="font-medium">{kbli.pma.citation}</span>
                </p>
              )}

              {/* Badge strip */}
              <div className="mt-5 flex flex-wrap gap-2.5">
                <PMABadge
                  status={kbli.pma.status}
                  maxForeign={kbli.pma.maxForeign}
                  verdictVerified={pmaVerdictVerified}
                  capSpecial={kbli.pma.capSpecial}
                  capVerified={kbli.pma.capVerified}
                  baliBlocked={kbli.baliL4?.blocked === true}
                />
                {kbli.licensing[0] && (
                  <RiskBadge
                    category={kbli.licensing[0].riskCategory}
                    verificationPending={isLicensingVerificationPending(kbli)}
                  />
                )}
                <TransitionBadge transition={kbli.transition} />
                {pmaVerdictVerified && kbli.baliL4 && (
                  <BaliStatusBadge
                    status={kbli.baliL4.status}
                    reason={discloseKbliBaliReason(kbli)}
                    confidence={kbli.baliL4.confidence}
                    needsReview={kbli.baliL4.needsReview}
                    pmaStatus={pmaVerdictVerified ? kbli.pma.status : "unknown"}
                  />
                )}
                {kbli.provenance && (
                  <ProvenanceBadge state={kbli.provenance.state} />
                )}
              </div>
            </div>
          </div>

          {/* LOOP-2 EDITORIAL — the magazine article leads every code that has one */}
          {intel?.editorial && (
            <section className="pb-10 pt-2">
              <KBLIEditorial editorial={intel.editorial} />
            </section>
          )}

          {/* GOLD CONTENT — editorial magazine layout */}
          {gold ? (
            <div className="space-y-0">
              {/* THE LEAD — subsumed by the editorial article when one exists */}
              {!intel?.editorial && (
                <section className="pb-10">
                  <p
                    className="text-xl leading-relaxed text-[var(--foreground-secondary)] sm:text-[22px] sm:leading-[1.7]"
                    style={{ maxWidth: "680px" }}
                  >
                    {gold.whatItMeans}
                  </p>
                </section>
              )}

              {/* VISUAL DIVIDER */}
              <div className="flex items-center gap-4 py-2">
                <div
                  className="h-px flex-1"
                  style={{ background: "var(--kbli-border)" }}
                />
                <span className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                  Licensing & Requirements
                </span>
                <div
                  className="h-px flex-1"
                  style={{ background: "var(--kbli-border)" }}
                />
              </div>

              {/* WHAT YOU NEED */}
              <section className="py-10">
                <h2 className="mb-6 text-sm font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
                  What You Need
                </h2>
                <LicensingSection kbli={kbli} gold={gold} />

                {/* Transition note */}
                <div
                  className="mt-8 flex items-start gap-3 rounded-xl p-4"
                  style={{
                    background: "var(--kbli-bg-elevated)",
                    border: "1px solid var(--kbli-border)",
                  }}
                >
                  <span
                    className="mt-0.5 shrink-0 inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold"
                    style={{
                      background: "rgba(139, 156, 247, 0.1)",
                      color: "var(--kbli-accent2)",
                      border: "1px solid rgba(139, 156, 247, 0.2)",
                    }}
                  >
                    2020 → 2025
                  </span>
                  <p className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                    {gold.whatChanged}
                  </p>
                </div>
              </section>

              {/* BALI CONTEXT — centrepiece */}
              <section className="relative -mx-4 sm:-mx-6 lg:-mx-8">
                <div
                  className="absolute inset-0 rounded-2xl"
                  style={{
                    background:
                      "linear-gradient(135deg, rgba(212, 132, 90, 0.04), rgba(139, 156, 247, 0.02), transparent 60%)",
                  }}
                />

                <div className="relative px-6 py-10 sm:px-8 lg:px-10">
                  <div className="mb-8 flex items-center gap-3">
                    <div
                      className="h-8 w-1 rounded-full"
                      style={{
                        background:
                          "linear-gradient(to bottom, var(--kbli-accent), var(--kbli-accent2))",
                      }}
                    />
                    <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
                      Bali Intelligence
                    </h2>
                  </div>

                  <KBLIBaliContext baliContext={gold.baliContext} />
                </div>
              </section>

              {/* ARTICLE CARD */}
              {article && (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative mt-10 flex overflow-hidden rounded-2xl transition-all duration-300 hover:shadow-xl"
                  style={{ border: "1px solid rgba(255,255,255,0.06)" }}
                >
                  <div
                    className="relative flex h-auto w-28 shrink-0 items-center justify-center overflow-hidden sm:w-36"
                    style={{
                      background: `linear-gradient(135deg, ${article.gradient[0]}, ${article.gradient[1]})`,
                    }}
                  >
                    <div
                      className="absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-20"
                      style={{ background: article.gradient[1] }}
                    />
                    <div
                      className="absolute -bottom-3 -left-3 h-14 w-14 rounded-full opacity-15"
                      style={{ background: "white" }}
                    />
                    <div
                      className="absolute right-2 bottom-2 h-8 w-8 rounded-full opacity-10"
                      style={{ background: "white" }}
                    />
                    <span className="relative text-3xl drop-shadow-lg transition-transform duration-300 group-hover:scale-110 sm:text-4xl">
                      {article.icon}
                    </span>
                  </div>

                  <div
                    className="flex flex-1 flex-col justify-center gap-2 px-5 py-4"
                    style={{ background: "var(--kbli-bg-elevated)" }}
                  >
                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--kbli-accent)]">
                      <span>Read Full Guide on Bali Zero</span>
                      <span className="text-sm opacity-50 transition-transform duration-300 group-hover:translate-x-0.5">
                        ↗
                      </span>
                    </span>
                    <p className="line-clamp-2 text-sm font-semibold leading-snug text-[var(--kbli-text-primary)] transition-colors duration-300 group-hover:text-[var(--kbli-accent)]">
                      {article.title}
                    </p>
                    <span className="text-[11px] text-[var(--kbli-text-muted)]">
                      balizero.com
                    </span>
                  </div>
                </a>
              )}

              {/* TKA / FOREIGN WORKERS */}
              {gold.tkaInfo && (
                <>
                  <div className="flex items-center gap-4 py-2 pt-10">
                    <div
                      className="h-px flex-1"
                      style={{ background: "var(--kbli-border)" }}
                    />
                    <span className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                      Foreign Workers
                    </span>
                    <div
                      className="h-px flex-1"
                      style={{ background: "var(--kbli-border)" }}
                    />
                  </div>

                  <section className="py-10">
                    <div className="mb-6 flex items-center gap-3">
                      <div
                        className="h-8 w-1 rounded-full"
                        style={{
                          background:
                            "linear-gradient(to bottom, var(--kbli-accent2), var(--kbli-accent))",
                        }}
                      />
                      <div>
                        <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
                          TKA Eligible Positions
                        </h2>
                        <p className="text-xs text-[var(--foreground-muted)]">
                          Kepmenaker 228/2019 — Category{" "}
                          {gold.tkaInfo.categoryId}: {gold.tkaInfo.categoryName}
                        </p>
                      </div>
                      <span className="ml-auto rounded-full border border-[var(--border)] px-2.5 py-0.5 text-xs text-[var(--foreground-muted)]">
                        {gold.tkaInfo.totalInCategory} in category
                      </span>
                    </div>

                    {gold.tkaInfo.relevantPositions.length > 0 ? (
                      <div
                        className="overflow-hidden rounded-xl border border-[var(--border)]"
                        style={{ background: "var(--kbli-bg-elevated)" }}
                      >
                        {gold.tkaInfo.relevantPositions.map((pos, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-2.5 last:border-b-0"
                          >
                            <span
                              className="shrink-0 font-mono text-[11px] font-bold"
                              style={{
                                color: "var(--kbli-accent2)",
                                minWidth: "36px",
                              }}
                            >
                              {pos.isco}
                            </span>
                            <span className="text-sm font-medium text-[var(--foreground)]">
                              {pos.titleEn}
                              {pos.temporary && (
                                <span
                                  className="ml-1.5 inline-flex rounded px-1 py-0.5 text-[9px] font-bold uppercase"
                                  style={{
                                    background: "rgba(232, 168, 73, 0.1)",
                                    color: "var(--kbli-pma-restricted)",
                                  }}
                                >
                                  Temp
                                </span>
                              )}
                            </span>
                            <span className="ml-auto text-xs text-[var(--foreground-muted)] hidden sm:inline">
                              {pos.titleId}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div
                        className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center"
                        style={{ background: "var(--kbli-bg-elevated)" }}
                      >
                        <p className="text-sm text-[var(--foreground-muted)]">
                          Position data for this category is being transcribed.
                        </p>
                      </div>
                    )}

                    <div
                      className="mt-5 rounded-xl p-4"
                      style={{
                        background: "rgba(139, 156, 247, 0.04)",
                        border: "1px solid rgba(139, 156, 247, 0.1)",
                      }}
                    >
                      <p className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                        {gold.tkaInfo.insight}
                      </p>
                    </div>

                    <details className="mt-4 rounded-xl border border-[var(--border)] overflow-hidden">
                      <summary
                        className="cursor-pointer px-4 py-3 text-xs font-medium text-[var(--foreground-muted)] transition-colors hover:text-[var(--foreground-secondary)]"
                        style={{ background: "var(--kbli-bg-elevated)" }}
                      >
                        KEDUA Provision — Directors & Commissioners Exemption
                      </summary>
                      <div
                        className="px-4 py-3 text-xs leading-relaxed text-[var(--foreground-secondary)]"
                        style={{ background: "var(--kbli-bg-surface)" }}
                      >
                        {gold.tkaInfo.keduaNote}
                      </div>
                    </details>
                  </section>
                </>
              )}

              {/* COMPLEMENTARY CODES */}
              <section
                className="mt-10 rounded-xl border border-[var(--border)] overflow-hidden"
                style={{ background: "var(--kbli-bg-elevated)" }}
              >
                <div
                  className="px-5 py-3.5 border-b border-[var(--border)]"
                  style={{ background: "var(--kbli-bg-surface)" }}
                >
                  <span className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
                    Complementary Codes
                  </span>
                </div>
                <div className="px-5 py-4 kbli-prose">
                  <MarkdownClient withKbliLinks>
                    {gold.youllAlsoNeed}
                  </MarkdownClient>
                </div>
              </section>
            </div>
          ) : (
            /* NON-GOLD — enhanced standard layout */
            <div className="space-y-0">
              {intel?.whatItMeans ? (
                <>
                  {/* LEAD — subsumed by the editorial article when one exists */}
                  {!intel?.editorial && (
                    <section className="pb-10">
                      <p
                        className="text-lg leading-relaxed text-[var(--foreground-secondary)] sm:text-xl sm:leading-[1.7]"
                        style={{ maxWidth: "680px" }}
                      >
                        {intel.whatItMeans}
                      </p>
                    </section>
                  )}

                  {intel.whatChanged && (
                    <div
                      className="flex items-start gap-3 rounded-xl p-4 mb-6"
                      style={{
                        background: "var(--kbli-bg-elevated)",
                        border: "1px solid var(--kbli-border)",
                      }}
                    >
                      <span
                        className="mt-0.5 shrink-0 inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold"
                        style={{
                          background: "rgba(139, 156, 247, 0.1)",
                          color: "var(--kbli-accent2)",
                          border: "1px solid rgba(139, 156, 247, 0.2)",
                        }}
                      >
                        What Changed
                      </span>
                      <p className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                        {intel.whatChanged}
                      </p>
                    </div>
                  )}

                  {intel.whatYouNeed && (
                    <div
                      className="rounded-xl p-5 mb-6"
                      style={{
                        background: "var(--kbli-bg-elevated)",
                        border: "1px solid var(--kbli-border)",
                      }}
                    >
                      <h3 className="mb-3 text-xs font-bold uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                        What You Need
                      </h3>
                      <div className="text-sm leading-relaxed text-[var(--foreground-secondary)] whitespace-pre-line">
                        {intel.whatYouNeed}
                      </div>
                    </div>
                  )}

                  {/* BALI CONTEXT — shared rendering with the gold layout */}
                  {intel.baliContext && (
                    <section className="relative -mx-4 mb-6 sm:-mx-6 lg:-mx-8">
                      <div
                        className="absolute inset-0 rounded-2xl"
                        style={{
                          background:
                            "linear-gradient(135deg, rgba(212, 132, 90, 0.04), rgba(139, 156, 247, 0.02), transparent 60%)",
                        }}
                      />
                      <div className="relative px-6 py-10 sm:px-8 lg:px-10">
                        <div className="mb-8 flex items-center gap-3">
                          <div
                            className="h-8 w-1 rounded-full"
                            style={{
                              background:
                                "linear-gradient(to bottom, var(--kbli-accent), var(--kbli-accent2))",
                            }}
                          />
                          <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
                            Bali Intelligence
                          </h2>
                        </div>
                        <KBLIBaliContext baliContext={intel.baliContext} />
                      </div>
                    </section>
                  )}

                  {/* WHO THIS IS FOR */}
                  {intel.whoThisIsFor && (
                    <div
                      className="rounded-xl p-5 mb-6"
                      style={{
                        background: "var(--kbli-bg-elevated)",
                        border: "1px solid var(--kbli-border)",
                      }}
                    >
                      <h3 className="mb-3 text-xs font-bold uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                        Who This Is For
                      </h3>
                      <p className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                        {intel.whoThisIsFor}
                      </p>
                    </div>
                  )}

                  {/* YOU'LL ALSO NEED */}
                  {intel.youllAlsoNeed && (
                    <section
                      className="mb-6 rounded-xl border border-[var(--border)] overflow-hidden"
                      style={{ background: "var(--kbli-bg-elevated)" }}
                    >
                      <div
                        className="px-5 py-3.5 border-b border-[var(--border)]"
                        style={{ background: "var(--kbli-bg-surface)" }}
                      >
                        <span className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
                          You&apos;ll Also Need
                        </span>
                      </div>
                      <div className="px-5 py-4">
                        <KBLIYoullAlsoNeed text={intel.youllAlsoNeed} />
                      </div>
                    </section>
                  )}
                </>
              ) : (
                <section className="pb-10">
                  <p
                    className="text-lg leading-relaxed text-[var(--foreground-secondary)] sm:text-xl sm:leading-[1.7]"
                    style={{ maxWidth: "680px" }}
                  >
                    {kbli.description}
                  </p>
                </section>
              )}

              {/* Licensing quick facts */}
              {kbli.licensing.length > 0 && (
                <>
                  <div className="flex items-center gap-4 py-2">
                    <div
                      className="h-px flex-1"
                      style={{ background: "var(--kbli-border)" }}
                    />
                    <span className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                      Licensing Overview
                    </span>
                    <div
                      className="h-px flex-1"
                      style={{ background: "var(--kbli-border)" }}
                    />
                  </div>

                  <section className="py-10">
                    <div
                      className="overflow-hidden rounded-xl border border-[var(--border)]"
                      style={{ background: "var(--kbli-bg-elevated)" }}
                    >
                      <div
                        className="grid grid-cols-2 gap-px sm:grid-cols-4"
                        style={{ background: "var(--kbli-border)" }}
                      >
                        <div
                          className="flex flex-col gap-1 p-4"
                          style={{ background: "var(--kbli-bg-elevated)" }}
                        >
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--foreground-muted)]">
                            Risk Level
                          </span>
                          <span className="text-sm font-semibold text-[var(--foreground)]">
                            {kbli.licensing[0].riskCategory}
                          </span>
                        </div>
                        <div
                          className="flex flex-col gap-1 p-4"
                          style={{ background: "var(--kbli-bg-elevated)" }}
                        >
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--foreground-muted)]">
                            License Type
                          </span>
                          <span className="text-sm font-semibold text-[var(--foreground)]">
                            {kbli.licensing[0].licenseType || "NIB"}
                          </span>
                        </div>
                        <div
                          className="flex flex-col gap-1 p-4"
                          style={{ background: "var(--kbli-bg-elevated)" }}
                        >
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--foreground-muted)]">
                            Foreign Ownership
                          </span>
                          <span className="text-sm font-semibold text-[var(--foreground)]">
                            {pmaVerdictVerified
                              ? formatPmaOwnership(kbli.pma)
                              : "Not verified — confirm in OSS"}
                          </span>
                        </div>
                        <div
                          className="flex flex-col gap-1 p-4"
                          style={{ background: "var(--kbli-bg-elevated)" }}
                        >
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--foreground-muted)]">
                            Processing
                          </span>
                          <span className="text-sm font-semibold text-[var(--foreground)]">
                            {formatTimeframe(kbli.licensing[0].timeframe) ??
                              "Through OSS"}
                          </span>
                        </div>
                      </div>
                    </div>
                    {/* One grid-level qualifier instead of per-cell noise:
                        risk, license AND processing above all come from the
                        same unverified rows (Codex gate round 5). */}
                    {isLicensingVerificationPending(kbli) && (
                      <p className="mt-2 text-[11px] text-[var(--foreground-muted)]">
                        ⏳ The licensing facts above (risk, license, processing)
                        await KBLI-2025 crosswalk verification — see Sources
                        &amp; Verification below.
                      </p>
                    )}
                  </section>
                </>
              )}

              {/* Article card for non-Gold pages */}
              {article && (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative mt-8 flex overflow-hidden rounded-2xl transition-all duration-300 hover:shadow-xl"
                  style={{ border: "1px solid rgba(255,255,255,0.06)" }}
                >
                  <div
                    className="relative flex h-auto w-28 shrink-0 items-center justify-center overflow-hidden sm:w-36"
                    style={{
                      background: `linear-gradient(135deg, ${article.gradient[0]}, ${article.gradient[1]})`,
                    }}
                  >
                    <div
                      className="absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-20"
                      style={{ background: article.gradient[1] }}
                    />
                    <div
                      className="absolute -bottom-3 -left-3 h-14 w-14 rounded-full opacity-15"
                      style={{ background: "white" }}
                    />
                    <span className="relative text-3xl drop-shadow-lg transition-transform duration-300 group-hover:scale-110 sm:text-4xl">
                      {article.icon}
                    </span>
                  </div>
                  <div
                    className="flex flex-1 flex-col justify-center gap-2 px-5 py-4"
                    style={{ background: "var(--kbli-bg-elevated)" }}
                  >
                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--kbli-accent)]">
                      <span>Read Full Guide on Bali Zero</span>
                      <span className="text-sm opacity-50 transition-transform duration-300 group-hover:translate-x-0.5">
                        ↗
                      </span>
                    </span>
                    <p className="line-clamp-2 text-sm font-semibold leading-snug text-[var(--kbli-text-primary)] transition-colors duration-300 group-hover:text-[var(--kbli-accent)]">
                      {article.title}
                    </p>
                    <span className="text-[11px] text-[var(--kbli-text-muted)]">
                      balizero.com
                    </span>
                  </div>
                </a>
              )}
            </div>
          )}

          {/* BPS/PP28 transition provenance is shared by both layouts. Keep it
              outside the gold/non-gold branch so gold pages cannot hide it. */}
          <KBLITransitionSources transition={kbli.transition} />

          {/* REGULATORY DIVERGENCE — only on collision-cured codes: the
              documented 2020-vs-2025 divergence, with citations (TRACK-P) */}
          {kbli.provenance && (
            <KBLIDivergence code={kbli.code} provenance={kbli.provenance} />
          )}

          {/* SOURCES & VERIFICATION — per-fact provenance with vintage,
              rendered on gold AND non-gold layouts (TRACK-P) */}
          {kbli.provenance && (
            <KBLIProvenancePanel
              kbli={kbli}
              lastModified={getKbliDatasetLastModified()}
            />
          )}

          {/* COMMON QUESTIONS — visible counterpart of the FAQPage JSON-LD,
              rendered on gold AND non-gold layouts (markup honesty) */}
          <KBLICommonQuestions code={kbli} />

          {/* RELATED CODES */}
          {related.length > 0 && (
            <section className="mt-12">
              <h2 className="mb-5 text-sm font-bold uppercase tracking-[0.12em] text-[var(--foreground-muted)]">
                Related Codes
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {related.map((r) => (
                  <KBLICard key={r.code} code={r} />
                ))}
              </div>
            </section>
          )}

          {/* CONSULTATION CTA — pricing + WhatsApp */}
          <KBLIConsultationCTA
            code={kbli.code}
            titleEn={kbli.titleEn}
            pmaStatus={kbli.pma.status}
            pmaVerified={pmaVerdictVerified}
          />

          {/* ZANTARA AI CHAT */}
          <section className="mt-12">
            <Suspense
              fallback={
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--kbli-bg-secondary)] p-6 animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-[var(--kbli-bg-elevated)]" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-1/3 rounded bg-[var(--kbli-bg-elevated)]" />
                      <div className="h-3 w-1/2 rounded bg-[var(--kbli-bg-elevated)]" />
                    </div>
                  </div>
                </div>
              }
            >
              <ZantaraChat
                codeContext={{
                  code: kbli.code,
                  title: kbli.titleEn,
                  section: kbli.section ?? "",
                }}
                opener={(() => {
                  const fallback = neutralKbliChatOpener(kbli);
                  const op = gold?.zantaraOpener ?? fallback;
                  // The gold/intel openers were written before the 2026 Bali moratorium
                  // and cheerfully promise a "PT PMA setup" on codes now blocked for a
                  // PT PMA in Bali. Don't greet a blocked code with a PMA go-ahead — use
                  // a neutral Bali-aware opener instead.
                  if (
                    kbli.baliL4?.blocked &&
                    /\b(PT PMA|100% foreign|foreign-owned)\b/i.test(op)
                  ) {
                    // The parenthetical named two causes at once — "reserved
                    // UMKM / 2026 moratorium" — on every blocked code. This
                    // string seeds the assistant's context, so a wrong cause
                    // here is a wrong cause in the answer. Derived instead.
                    return `Looking at KBLI ${kbli.code} — ${kbli.titleEn}? Note that in Bali this code is currently ${baliBlockClause(kbli.baliL4?.status)}. Ask me about the national procedure, the Bali restriction, or alternatives.`;
                  }
                  return op;
                })()}
                suggestions={[
                  `What do I need to start a ${kbli.titleEn.toLowerCase()} business?`,
                  `Can foreigners own this business?`,
                  `What changed from 2020 to 2025?`,
                ]}
              />
            </Suspense>
          </section>
        </article>
      </FunnelFrame>
    </>
  );
}
