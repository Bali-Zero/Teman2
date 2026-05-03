"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Search, Newspaper } from "lucide-react";
import type { ArticleListItem } from "@/lib/blog/types";
import { NewsHero } from "@/app/v2/_components/NewsHero";

interface NewsPageClientProps {
  articles: ArticleListItem[];
}

const SECTIONS = [
  {
    title: "Visas",
    description: "KITAS, Golden Visa, Digital Nomad, E33G.",
    href: "/visa",
    accent: "#c8102e",
  },
  {
    title: "Business",
    description: "PT PMA, KBLI 2025, licensing, compliance.",
    href: "/kbli",
    accent: "#d4a017",
  },
  {
    title: "Taxes",
    description: "CoreTax, SPT, deadlines per regency.",
    href: "/tax-calendar",
    accent: "#3a6dff",
  },
  {
    title: "Property",
    description: "Zoning, PT PMA property, eligibility.",
    href: "/property/eligibility",
    accent: "#22c55e",
  },
  {
    title: "Living",
    description: "Digital nomads, daily life, costs, Bali ground truth.",
    href: "/living",
    accent: "#ec4899",
  },
  {
    title: "Tech & Trends",
    description: "AI, SaaS, startup stories from Indonesia.",
    href: "/tech",
    accent: "#a78bfa",
  },
];

const TOPICS = [
  { id: "kitas", name: "KITAS", href: "/visas" },
  { id: "golden", name: "Golden Visa", href: "/visas" },
  { id: "e33g", name: "Digital Nomad", href: "/visas" },
  { id: "ptpma", name: "PT PMA", href: "/business" },
  { id: "kbli", name: "KBLI 2025", href: "/kbli" },
  { id: "coretax", name: "CoreTax", href: "/tax-calendar" },
  { id: "property", name: "Property", href: "/property/eligibility" },
  { id: "ai", name: "AI & SaaS", href: "/tech" },
];

function formatCategory(category: string): string {
  const map: Record<string, string> = {
    immigration: "Visas",
    visas: "Visas",
    business: "Business",
    tax: "Taxes",
    taxes: "Taxes",
    property: "Property",
    "digital-nomad": "Digital Nomad",
    lifestyle: "Living",
    living: "Living",
    tech: "Tech",
    trends: "Trends",
  };
  return (
    map[category] ||
    category.replace("-", " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

const CATEGORY_ACCENT: Record<string, string> = {
  immigration: "#c8102e",
  visas: "#c8102e",
  business: "#d4a017",
  tax: "#3a6dff",
  taxes: "#3a6dff",
  property: "#22c55e",
  "digital-nomad": "#ec4899",
  lifestyle: "#ec4899",
  living: "#ec4899",
  tech: "#a78bfa",
  trends: "#a78bfa",
};

export default function NewsPageClient({
  articles: serverArticles,
}: NewsPageClientProps) {
  const [query, setQuery] = useState("");

  const articles = serverArticles || [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return articles;
    return articles.filter(
      (a) =>
        a.title?.toLowerCase().includes(q) ||
        a.excerpt?.toLowerCase().includes(q) ||
        a.category?.toLowerCase().includes(q),
    );
  }, [articles, query]);

  // NewsHero carousel uses the top 5; grid shows the rest.
  const gridArticles = filtered.slice(5, 17);

  return (
    <div
      className="min-h-screen"
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      {/* Hero — NewsHero carousel (reused from homepage) */}
      <NewsHero articles={articles.slice(0, 5)} />

      {/* Search bar strip */}
      <section
        style={{
          padding: "clamp(20px, 3vw, 32px) clamp(24px, 4vw, 40px) 8px",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <label
            className="flex items-center gap-3 rounded-full pl-4 pr-2 py-2 max-w-[720px] mx-auto"
            style={{
              background:
                "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
              border:
                "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 22%, transparent)",
              backdropFilter: "blur(20px) saturate(160%)",
              WebkitBackdropFilter: "blur(20px) saturate(160%)",
            }}
          >
            <Search
              size={16}
              strokeWidth={2.2}
              style={{ color: "var(--text-tertiary)" }}
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search KITAS, KBLI, tax deadline, zoning…"
              aria-label="Search articles"
              className="flex-1 bg-transparent border-0 outline-none text-[14px]"
              style={{ color: "var(--text-primary)" }}
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="text-[11px] font-semibold px-3 py-1.5 rounded-full"
                style={{
                  background: "var(--accent-funnel, #3a6dff)",
                  color: "#fff",
                }}
              >
                Clear
              </button>
            )}
          </label>
        </div>
      </section>

      {/* Topic pills */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          borderBottom: "1px solid var(--border-subtle)",
          padding: "20px clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1400px] mx-auto flex flex-wrap gap-2">
          {TOPICS.map((t) => (
            <Link
              key={t.id}
              href={t.href}
              className="text-[12px] font-semibold px-3.5 py-1.5 rounded-full transition"
              style={{
                background:
                  "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 22%, transparent)",
                color: "var(--text-primary)",
              }}
            >
              {t.name}
            </Link>
          ))}
        </div>
      </section>

      {/* Section cards (6 colorful) */}
      <section
        style={{
          padding: "clamp(32px, 4vw, 56px) clamp(24px, 4vw, 40px)",
          borderTop: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-5"
            style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
          >
            Browse by topic
          </div>
          <h2
            className="font-extrabold tracking-tight mb-8"
            style={{
              fontSize: "clamp(26px, 2.8vw, 36px)",
              lineHeight: 1.1,
              color: "var(--text-primary)",
            }}
          >
            Six sections. Every regulation that affects expats and investors in
            Indonesia.
          </h2>
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            }}
          >
            {SECTIONS.map((s) => (
              <Link
                key={s.title}
                href={s.href}
                className="group relative rounded-2xl p-6 transition-all hover:-translate-y-1 overflow-hidden"
                style={{
                  background: `color-mix(in srgb, ${s.accent} 10%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${s.accent} 32%, transparent)`,
                  boxShadow: `0 10px 30px color-mix(in srgb, ${s.accent} 16%, transparent)`,
                  backdropFilter: "blur(20px) saturate(160%)",
                  WebkitBackdropFilter: "blur(20px) saturate(160%)",
                }}
              >
                <div
                  className="text-[11px] font-semibold uppercase tracking-[0.22em] mb-2"
                  style={{ color: s.accent }}
                >
                  {s.title}
                </div>
                <div
                  className="text-[20px] font-extrabold tracking-tight mb-3"
                  style={{ color: "var(--text-primary)", lineHeight: 1.15 }}
                >
                  {s.description}
                </div>
                <div
                  className="inline-flex items-center gap-1.5 text-[12px] font-semibold opacity-80 group-hover:opacity-100 transition"
                  style={{ color: s.accent }}
                >
                  Explore
                  <ArrowRight size={12} strokeWidth={2.2} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Latest grid */}
      <section
        style={{
          padding:
            "clamp(32px, 4vw, 64px) clamp(24px, 4vw, 40px) clamp(56px, 6vw, 96px)",
          borderTop: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div className="flex items-end justify-between mb-8 flex-wrap gap-3">
            <div>
              <div
                className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-2"
                style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
              >
                Latest intelligence
              </div>
              <h2
                className="font-extrabold tracking-tight"
                style={{
                  fontSize: "clamp(22px, 2.4vw, 30px)",
                  color: "var(--text-primary)",
                }}
              >
                {query
                  ? `${filtered.length} result${filtered.length === 1 ? "" : "s"} for "${query}"`
                  : "What's new this week"}
              </h2>
            </div>
          </div>
          {gridArticles.length === 0 && !query && (
            <p
              className="text-[14px]"
              style={{ color: "var(--text-secondary)" }}
            >
              Fresh pieces are publishing daily. Check back soon.
            </p>
          )}
          <div
            className="grid gap-6"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            }}
          >
            {gridArticles.map((a) => (
              <Link
                key={a.id}
                href={`/${a.category}/${a.slug}`}
                className="group rounded-2xl overflow-hidden flex flex-col"
                style={{
                  background:
                    "color-mix(in srgb, var(--accent-funnel, #3a6dff) 4%, transparent)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div className="relative" style={{ aspectRatio: "16 / 10" }}>
                  {a.coverImage ? (
                    <Image
                      src={a.coverImage}
                      alt={a.title || ""}
                      fill
                      className="object-cover transition-transform duration-700 group-hover:scale-105"
                      sizes="(max-width: 768px) 100vw, 400px"
                    />
                  ) : (
                    <div
                      className="w-full h-full flex items-center justify-center"
                      style={{ background: "var(--surface-elev-1)" }}
                    >
                      <Newspaper
                        size={32}
                        style={{ color: "var(--text-tertiary)" }}
                      />
                    </div>
                  )}
                </div>
                <div className="p-5 flex flex-col gap-2">
                  <div
                    className="text-[10px] font-semibold uppercase tracking-[0.2em]"
                    style={{
                      color: CATEGORY_ACCENT[a.category] || "#d4a017",
                    }}
                  >
                    {formatCategory(a.category)}
                  </div>
                  <h3
                    className="text-[16px] font-bold tracking-tight leading-[1.25] line-clamp-3"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {a.title}
                  </h3>
                  {a.excerpt && (
                    <p
                      className="text-[13px] leading-[1.5] line-clamp-2"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {a.excerpt
                        .replace(/^#+\s*/gm, "")
                        .replace(/\*\*|__|\*|_/g, "")
                        .trim()}
                    </p>
                  )}
                  <div
                    className="flex items-center gap-2 text-[11.5px] mt-1"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    <span>{a.readingTime} min read</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
