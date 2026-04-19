import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { MobileNav } from "../_components/MobileNav";
import { Calendar, Clock } from "lucide-react";
import { Footer } from "../_components/Footer";
import { getAllArticles } from "@/lib/blog/articles";
import type { ArticleListItem, ArticleCategory } from "@/lib/blog/types";

export const metadata: Metadata = {
  title: "News & Dispatches",
  robots: { index: false, follow: false },
};

const TOPIC_COLORS: Record<ArticleCategory, string> = {
  visas: "#ff2d4c",
  business: "#f59e0b",
  taxes: "#06b6d4",
  property: "#22c55e",
  living: "#a78bfa",
  trends: "#e879f9",
};

const TOPICS: {
  label: string;
  slug: ArticleCategory | "all";
  accent: string;
}[] = [
  { label: "All", slug: "all", accent: "#ffffff" },
  { label: "Visas", slug: "visas", accent: TOPIC_COLORS.visas },
  { label: "Business", slug: "business", accent: TOPIC_COLORS.business },
  { label: "Taxes", slug: "taxes", accent: TOPIC_COLORS.taxes },
  { label: "Property", slug: "property", accent: TOPIC_COLORS.property },
  { label: "Living", slug: "living", accent: TOPIC_COLORS.living },
];

const NAV_ITEMS = [
  { label: "Home", href: "/v2" },
  { label: "News", href: "/v2/news" },
];

export default async function NewsPage() {
  const { articles, total } = await getAllArticles({ limit: 18, offset: 0 });

  return (
    <div
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" size={36} />}
        items={NAV_ITEMS}
        slotAfter={<MobileNav items={NAV_ITEMS} />}
        actions={null}
      />

      <main className="max-w-[1200px] mx-auto px-5 md:px-10 pt-28 pb-20">
        <div className="text-center mb-12">
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-4"
            style={{ color: "var(--text-tertiary)" }}
          >
            Bali Zero · Dispatches · {total} articles
          </div>
          <h1
            className="font-black tracking-tight mb-4"
            style={{ fontSize: "clamp(32px, 4vw, 52px)", lineHeight: 1.05 }}
          >
            Intelligence for expats{" "}
            <span style={{ color: "var(--text-secondary)" }}>
              and founders.
            </span>
          </h1>
          <p
            className="text-[15px] max-w-xl mx-auto"
            style={{ color: "var(--text-secondary)" }}
          >
            Regulation changes, tax traps, visa updates, property pitfalls.
            Written by the team that files the paperwork.
          </p>
        </div>

        {/* Topic pills */}
        <div className="flex flex-wrap justify-center gap-2 mb-12">
          {TOPICS.map((t) => (
            <Link
              key={t.slug}
              href={t.slug === "all" ? "/v2/news" : `/v2/news?topic=${t.slug}`}
              className="px-4 py-2 rounded-full text-[12px] font-semibold transition-all"
              style={{
                background:
                  t.slug === "all"
                    ? "rgba(255,255,255,0.08)"
                    : `color-mix(in srgb, ${t.accent} 12%, transparent)`,
                border: `1px solid ${
                  t.slug === "all"
                    ? "rgba(255,255,255,0.15)"
                    : `color-mix(in srgb, ${t.accent} 30%, transparent)`
                }`,
                color: t.slug === "all" ? "var(--text-primary)" : t.accent,
              }}
            >
              {t.label}
            </Link>
          ))}
        </div>

        {/* Article grid */}
        {articles.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {articles.map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>
        ) : (
          <div
            className="text-center py-20 text-[15px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            No articles found. Check back soon.
          </div>
        )}

        {total > 18 && (
          <div className="text-center mt-12">
            <span
              className="text-[13px]"
              style={{ color: "var(--text-tertiary)" }}
            >
              Showing 18 of {total} articles
            </span>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

function ArticleCard({ article: a }: { article: ArticleListItem }) {
  const accent = TOPIC_COLORS[a.category] ?? "#a78bfa";
  const dateStr = a.publishedAt
    ? new Date(a.publishedAt).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "";

  return (
    <Link
      href={`/${a.category}/${a.slug}`}
      className="group rounded-2xl overflow-hidden transition-all hover:-translate-y-1 block"
      style={{
        background: "color-mix(in srgb, var(--surface-base) 85%, #fff)",
        border: "1px solid var(--border-default)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
      }}
    >
      <div className="relative h-48 overflow-hidden">
        {a.coverImage ? (
          <Image
            src={a.coverImage}
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 380px"
            quality={75}
            loading="lazy"
            className="object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div
            className="w-full h-full"
            style={{
              background: `linear-gradient(135deg, ${accent}, color-mix(in srgb, ${accent} 40%, #000))`,
            }}
          />
        )}
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(0deg, rgba(0,0,0,0.6) 0%, transparent 50%)",
          }}
        />
        <span
          className="absolute top-3 left-3 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
          style={{
            background: `color-mix(in srgb, ${accent} 30%, rgba(0,0,0,0.5))`,
            color: "#fff",
            border: `1px solid color-mix(in srgb, ${accent} 40%, transparent)`,
          }}
        >
          {a.category}
        </span>
        {a.featured && (
          <span
            className="absolute top-3 right-3 px-2 py-0.5 rounded text-[9px] font-bold uppercase"
            style={{ background: "rgba(255,255,255,0.15)", color: "#fff" }}
          >
            Featured
          </span>
        )}
      </div>

      <div className="p-5">
        <h2
          className="text-[16px] font-bold tracking-tight mb-2 leading-snug line-clamp-2"
          style={{ color: "var(--text-primary)" }}
        >
          {a.title}
        </h2>
        <p
          className="text-[13px] leading-relaxed mb-4 line-clamp-2"
          style={{ color: "var(--text-secondary)" }}
        >
          {a.excerpt}
        </p>
        <div
          className="flex items-center gap-3 text-[11px]"
          style={{ color: "var(--text-tertiary)" }}
        >
          {dateStr && (
            <span className="inline-flex items-center gap-1">
              <Calendar size={11} strokeWidth={2} />
              {dateStr}
            </span>
          )}
          {a.readingTime > 0 && (
            <span className="inline-flex items-center gap-1">
              <Clock size={11} strokeWidth={2} />
              {a.readingTime} min
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
