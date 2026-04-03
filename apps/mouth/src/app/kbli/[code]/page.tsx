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
import { getGoldContent } from "@/lib/kbli-data.server";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";
import { PMABadge } from "@/components/kbli/PMABadge";
import { RiskBadge } from "@/components/kbli/RiskBadge";
import { TransitionBadge } from "@/components/kbli/TransitionBadge";
import { KBLICard } from "@/components/kbli/KBLICard";
import {
  KBLICodeJsonLd,
  KBLIBreadcrumbJsonLd,
  KBLIFaqJsonLd,
} from "@/components/kbli/KBLIStructuredData";
import { LicensingSection } from "@/components/kbli/LicensingSection";
import { getRelatedArticle } from "@/lib/kbli-articles";
import { GOLD_HERO_IMAGES } from "@/lib/kbli-hero-images";
import Link from "next/link";
import dynamic from "next/dynamic";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

const ZantaraChat = lazy(() =>
  import("@/components/kbli/ZantaraChat").then((mod) => ({
    default: mod.ZantaraChat,
  })),
);

// ISR: Generate pages on-demand, cache for 1 week
export const dynamicParams = true;
export const revalidate = 604800;

export async function generateStaticParams() {
  const codes = getAllCodes();
  return codes.slice(0, 50).map((c) => ({ code: c.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: codeParam } = await params;
  const kbli = getCode(codeParam);
  if (!kbli) return { title: "KBLI Code Not Found" };

  const pmaLabel =
    kbli.pma.status === "open"
      ? "100% Foreign Ownership"
      : kbli.pma.status === "restricted"
        ? `Restricted (max ${kbli.pma.maxForeign}% foreign)`
        : "Closed to Foreign Investment";

  const title = `KBLI ${kbli.code} — ${kbli.titleEn} | KBLI 2025 Navigator`;
  const description = `KBLI 2025: ${kbli.code} — ${kbli.titleEn} (${kbli.titleId}). ${pmaLabel}. Full licensing requirements, PMA rules, and risk level under Indonesian business classification 2025. Expert setup via Bali Zero.`;

  return {
    title,
    description,
    keywords: `KBLI ${kbli.code}, ${kbli.titleId}, ${kbli.titleEn}, KBLI 2025, Indonesian business classification, PT PMA Bali, company registration Indonesia`,
    openGraph: {
      title,
      description,
      type: "article",
      url: `https://balizero.com/kbli/${kbli.code}`,
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

  const gold = getGoldContent(kbli.code);
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
      <KBLICodeJsonLd code={kbli} />
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

      <article className="pb-16">
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
                {sectionMeta.icon} Section {kbli.section} — {sectionMeta.nameEn}
              </p>
            )}

            {/* Badge strip */}
            <div className="mt-5 flex flex-wrap gap-2.5">
              <PMABadge
                status={kbli.pma.status}
                maxForeign={kbli.pma.maxForeign}
              />
              {kbli.licensing[0] && (
                <RiskBadge category={kbli.licensing[0].riskCategory} />
              )}
              <TransitionBadge status={kbli.transition.mappingStatus} />
            </div>
          </div>
        </div>

        {/* GOLD CONTENT — editorial magazine layout */}
        {gold ? (
          <div className="space-y-0">
            {/* THE LEAD */}
            <section className="pb-10">
              <p
                className="text-xl leading-relaxed text-[var(--foreground-secondary)] sm:text-[22px] sm:leading-[1.7]"
                style={{ maxWidth: "680px" }}
              >
                {gold.whatItMeans}
              </p>
            </section>

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

                <div className="space-y-5" style={{ maxWidth: "780px" }}>
                  {gold.baliContext.split(/\n---\n/).map((block, idx) => {
                    const trimmed = block.trim();
                    if (!trimmed) return null;

                    const isMistakes = trimmed
                      .toLowerCase()
                      .includes("common client mistakes");
                    const isNumbers =
                      trimmed.toLowerCase().includes("governor") ||
                      trimmed.toLowerCase().includes("numbers");
                    const isReality =
                      trimmed.toLowerCase().includes("reality") ||
                      trimmed.toLowerCase().includes("market");

                    const titleMatch = trimmed.match(/^\*\*([^*]+?):\*\*/);
                    const cardTitle = titleMatch ? titleMatch[1] : null;
                    const bodyText = cardTitle
                      ? trimmed.replace(/^\*\*[^*]+?:\*\*\s*/, "")
                      : trimmed;

                    const accentColor = isMistakes
                      ? "var(--kbli-pma-restricted)"
                      : "var(--kbli-accent)";
                    const blockIcon = isMistakes
                      ? "⚠"
                      : isNumbers
                        ? "📊"
                        : isReality
                          ? "🏝"
                          : "💡";
                    const blockBg = isMistakes
                      ? "rgba(232, 168, 73, 0.03)"
                      : "rgba(212, 132, 90, 0.02)";

                    return (
                      <div
                        key={idx}
                        className="rounded-xl p-5"
                        style={{
                          background: blockBg,
                          border: `1px solid ${isMistakes ? "rgba(232, 168, 73, 0.1)" : "var(--kbli-border)"}`,
                        }}
                      >
                        {cardTitle && (
                          <div className="mb-4 flex items-center gap-2.5">
                            <span className="text-base">{blockIcon}</span>
                            <span
                              className="text-sm font-bold tracking-wide"
                              style={{ color: accentColor }}
                            >
                              {cardTitle}
                            </span>
                          </div>
                        )}
                        <div className="kbli-prose">
                          <ReactMarkdown>{bodyText}</ReactMarkdown>
                        </div>
                      </div>
                    );
                  })}
                </div>
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
                    kita.balizero.com
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
                        Kepmenaker 228/2019 — Category {gold.tkaInfo.categoryId}
                        : {gold.tkaInfo.categoryName}
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
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => {
                      if (href?.startsWith("/kbli/")) {
                        return (
                          <Link
                            href={href}
                            className="inline-flex items-center gap-1 font-mono font-bold text-[var(--kbli-accent)] transition-colors hover:text-[var(--kbli-accent-hover)]"
                          >
                            {children}
                            <span className="text-[10px] opacity-50">→</span>
                          </Link>
                        );
                      }
                      return <a href={href}>{children}</a>;
                    },
                  }}
                >
                  {gold.youllAlsoNeed}
                </ReactMarkdown>
              </div>
            </section>
          </div>
        ) : (
          /* NON-GOLD — enhanced standard layout */
          <div className="space-y-0">
            {kbli.intel_2026?.whatItMeans ? (
              <>
                <section className="pb-10">
                  <p
                    className="text-lg leading-relaxed text-[var(--foreground-secondary)] sm:text-xl sm:leading-[1.7]"
                    style={{ maxWidth: "680px" }}
                  >
                    {kbli.intel_2026.whatItMeans}
                  </p>
                </section>

                {kbli.intel_2026.whatChanged && (
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
                      {kbli.intel_2026.whatChanged}
                    </p>
                  </div>
                )}

                {kbli.intel_2026.whatYouNeed && (
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
                      {kbli.intel_2026.whatYouNeed}
                    </div>
                  </div>
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
                          {kbli.pma.status === "open"
                            ? `${kbli.pma.maxForeign}% Open`
                            : kbli.pma.status === "restricted"
                              ? `Max ${kbli.pma.maxForeign}%`
                              : "Closed"}
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
                          {kbli.licensing[0].timeframe || "Otomatis"}
                        </span>
                      </div>
                    </div>
                  </div>
                </section>
              </>
            )}

            {/* Transition note */}
            {kbli.transition.previousCodes.length > 0 && (
              <div
                className="flex items-start gap-3 rounded-xl p-4"
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
                <div className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                  <span>Previous codes: </span>
                  {kbli.transition.previousCodes.map((c, i) => (
                    <span key={c}>
                      <Link
                        href={`/kbli/${c}`}
                        className="font-mono font-bold text-[var(--kbli-accent)] hover:text-[var(--kbli-accent-hover)]"
                      >
                        {c}
                      </Link>
                      {i < kbli.transition.previousCodes.length - 1 && ", "}
                    </span>
                  ))}
                  {kbli.transition.mappingNote && (
                    <span className="ml-1 text-[var(--foreground-muted)]">
                      — {kbli.transition.mappingNote}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Q&A Section — visible text for AI extractability */}
            <section className="mt-8">
              <div className="flex items-center gap-4 py-2 mb-6">
                <div
                  className="h-px flex-1"
                  style={{ background: "var(--kbli-border)" }}
                />
                <span className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                  Common Questions
                </span>
                <div
                  className="h-px flex-1"
                  style={{ background: "var(--kbli-border)" }}
                />
              </div>
              <div className="space-y-4">
                <details
                  className="rounded-xl border border-[var(--border)] overflow-hidden"
                  open
                >
                  <summary
                    className="cursor-pointer px-5 py-3.5 text-sm font-semibold text-[var(--foreground)] transition-colors hover:text-[var(--kbli-accent)]"
                    style={{ background: "var(--kbli-bg-elevated)" }}
                  >
                    Can foreigners operate a {kbli.titleEn.toLowerCase()}{" "}
                    business in Indonesia?
                  </summary>
                  <div
                    className="px-5 py-4 text-sm leading-relaxed text-[var(--foreground-secondary)]"
                    style={{ background: "var(--kbli-bg-surface)" }}
                  >
                    {kbli.pma.status === "open"
                      ? `Yes. KBLI ${kbli.code} (${kbli.titleId}) is classified as TERBUKA — open to 100% foreign ownership through a PT PMA company. You do not need a local Indonesian partner.`
                      : kbli.pma.status === "restricted"
                        ? `Partially. KBLI ${kbli.code} (${kbli.titleId}) is classified as TERBATAS — foreign ownership is capped at ${kbli.pma.maxForeign}%. You will need an Indonesian partner for the remaining shares.${kbli.pma.condition ? ` Condition: ${kbli.pma.condition}` : ""}`
                        : `No. KBLI ${kbli.code} (${kbli.titleId}) is classified as TERTUTUP — closed to foreign investment. This business activity is reserved for Indonesian nationals.`}
                  </div>
                </details>
                <details className="rounded-xl border border-[var(--border)] overflow-hidden">
                  <summary
                    className="cursor-pointer px-5 py-3.5 text-sm font-semibold text-[var(--foreground)] transition-colors hover:text-[var(--kbli-accent)]"
                    style={{ background: "var(--kbli-bg-elevated)" }}
                  >
                    What license do I need for KBLI {kbli.code}?
                  </summary>
                  <div
                    className="px-5 py-4 text-sm leading-relaxed text-[var(--foreground-secondary)]"
                    style={{ background: "var(--kbli-bg-surface)" }}
                  >
                    {kbli.licensing.length > 0
                      ? `KBLI ${kbli.code} has a ${kbli.licensing[0].riskCategory} risk classification. You need: ${kbli.licensing[0].licenseType || "NIB (Nomor Induk Berusaha)"}. ${kbli.licensing[0].timeframe ? `Processing time: ${kbli.licensing[0].timeframe}.` : "Processing is typically handled through the OSS (Online Single Submission) system."}`
                      : `KBLI ${kbli.code} requires a NIB (Nomor Induk Berusaha) obtained through the OSS (Online Single Submission) system. Contact a licensed consultant for specific requirements.`}
                  </div>
                </details>
                {kbli.transition.previousCodes.length > 0 && (
                  <details className="rounded-xl border border-[var(--border)] overflow-hidden">
                    <summary
                      className="cursor-pointer px-5 py-3.5 text-sm font-semibold text-[var(--foreground)] transition-colors hover:text-[var(--kbli-accent)]"
                      style={{ background: "var(--kbli-bg-elevated)" }}
                    >
                      How did KBLI {kbli.code} change from 2020 to 2025?
                    </summary>
                    <div
                      className="px-5 py-4 text-sm leading-relaxed text-[var(--foreground-secondary)]"
                      style={{ background: "var(--kbli-bg-surface)" }}
                    >
                      KBLI {kbli.code} was mapped from previous code
                      {kbli.transition.previousCodes.length > 1
                        ? "s"
                        : ""}: {kbli.transition.previousCodes.join(", ")} (KBLI
                      2020).
                      {kbli.transition.mappingNote
                        ? ` ${kbli.transition.mappingNote}`
                        : ""}
                      {kbli.transition.mappingStatus === "MATCH_LANGSUNG"
                        ? " This is a direct match — the code number and scope remained the same."
                        : kbli.transition.mappingStatus === "CODICE_RINUMERATO"
                          ? " The code was renumbered but the business activity scope is essentially unchanged."
                          : kbli.transition.mappingStatus ===
                              "MATCH_CON_AGGREGAZIONE"
                            ? " Multiple 2020 codes were merged into this single 2025 code."
                            : ""}{" "}
                      All businesses must migrate to KBLI 2025 by June 18, 2026
                      (BPS Regulation 7/2025).
                    </div>
                  </details>
                )}
              </div>
            </section>

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
                    kita.balizero.com
                  </span>
                </div>
              </a>
            )}
          </div>
        )}

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
              opener={
                gold?.zantaraOpener ??
                `Ask me anything about KBLI ${kbli.code} — ${kbli.titleEn}. Licensing, PMA rules, what changed in 2025, or how it works in Bali.`
              }
              suggestions={[
                `What do I need to start a ${kbli.titleEn.toLowerCase()} business?`,
                `Can foreigners own this business?`,
                `What changed from 2020 to 2025?`,
              ]}
            />
          </Suspense>
        </section>
      </article>
    </>
  );
}
