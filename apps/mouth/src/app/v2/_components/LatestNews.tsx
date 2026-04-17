import Link from "next/link";
import { Calendar, Clock, ArrowUpRight, type LucideIcon } from "lucide-react";
import type { ArticleListItem } from "@/lib/blog/types";

const CATEGORY_ACCENT: Record<string, { accent: string; label: string }> = {
  immigration: { accent: "#ff2d4c", label: "Immigration" },
  visas: { accent: "#ff2d4c", label: "Immigration" },
  visa: { accent: "#ff2d4c", label: "Immigration" },
  tax: { accent: "#3b82f6", label: "Tax" },
  "tax-legal": { accent: "#3b82f6", label: "Tax" },
  business: { accent: "#f59e0b", label: "Business" },
  business_regulations: { accent: "#f59e0b", label: "Business" },
  property: { accent: "#22c55e", label: "Property" },
  tech: { accent: "#06b6d4", label: "Tech" },
  lifestyle: { accent: "#ec4899", label: "Lifestyle" },
  bali_news: { accent: "#ec4899", label: "Bali" },
  "digital-nomad": { accent: "#ff2d4c", label: "Digital Nomad" },
  emerging_trends: { accent: "#8b5cf6", label: "Trends" },
  news: { accent: "#ffffff", label: "News" },
};

interface LatestNewsProps {
  articles: ArticleListItem[];
  limit?: number;
  title?: string;
  eyebrow?: string;
}

export function LatestNews({
  articles,
  limit = 5,
  eyebrow = "Latest from Bali Zero",
  title = "Fresh intelligence for expats and investors",
}: LatestNewsProps) {
  const items = articles.slice(0, limit);
  if (items.length === 0) return null;

  return (
    <section
      className="py-20 px-10"
      style={{ background: "var(--surface-base)" }}
    >
      <div className="flex items-end justify-between mb-10">
        <div>
          <div
            className="text-[11px] font-semibold uppercase tracking-widest mb-2"
            style={{ color: "var(--text-tertiary)" }}
          >
            {eyebrow}
          </div>
          <h3
            className="text-[26px] font-extrabold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            {title}
          </h3>
        </div>
        <a
          href="/news"
          className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-secondary)" }}
        >
          View all <ArrowUpRight size={14} strokeWidth={2} />
        </a>
      </div>

      <div
        className="grid gap-4"
        style={{
          gridTemplateColumns: `repeat(${Math.min(items.length, 5)}, minmax(0, 1fr))`,
        }}
      >
        {items.map((a) => {
          const meta =
            CATEGORY_ACCENT[a.category ?? ""] ?? CATEGORY_ACCENT.news;
          const accent = meta.accent;
          const href = `/${a.category}/${a.slug}`;
          const cover = a.coverImage || "";
          const date =
            a.publishedAt instanceof Date
              ? a.publishedAt.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })
              : typeof a.publishedAt === "string"
                ? new Date(a.publishedAt).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })
                : "";
          return (
            <Link
              key={a.id}
              href={href}
              className="rounded-2xl p-0 overflow-hidden transition-all hover:-translate-y-1 block focus-visible:outline-none focus-visible:ring-2"
              style={{
                background: `linear-gradient(135deg, color-mix(in srgb, ${accent} 18%, transparent) 0%, rgba(255,255,255,0.04) 100%)`,
                border: `1px solid color-mix(in srgb, ${accent} 35%, transparent)`,
                backdropFilter: "blur(24px) saturate(160%)",
                WebkitBackdropFilter: "blur(24px) saturate(160%)",
                boxShadow: `0 10px 40px rgba(0,0,0,0.25), 0 0 30px color-mix(in srgb, ${accent} 15%, transparent)`,
              }}
            >
              <div className="h-36 relative overflow-hidden">
                {cover ? (
                  <img
                    src={cover}
                    alt=""
                    loading="lazy"
                    className="absolute inset-0 w-full h-full object-cover"
                    aria-hidden="true"
                  />
                ) : (
                  <div
                    className="absolute inset-0"
                    style={{
                      background: `linear-gradient(135deg, color-mix(in srgb, ${accent} 70%, #000) 0%, color-mix(in srgb, ${accent} 22%, #0a0a10) 100%)`,
                    }}
                  />
                )}
                <div
                  className="absolute inset-0"
                  style={{
                    background:
                      "linear-gradient(0deg, rgba(0,0,0,0.55) 0%, transparent 60%)",
                  }}
                />
                <div
                  className="absolute top-3 left-3 inline-flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
                  style={{
                    background: `color-mix(in srgb, ${accent} 32%, rgba(0,0,0,0.55))`,
                    border: `1px solid color-mix(in srgb, ${accent} 55%, transparent)`,
                    color: "#ffffff",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    boxShadow: `0 0 12px color-mix(in srgb, ${accent} 40%, transparent)`,
                  }}
                >
                  <span
                    className="w-1 h-1 rounded-full"
                    style={{
                      background: accent,
                      boxShadow: `0 0 6px ${accent}`,
                    }}
                  />
                  {meta.label}
                </div>
              </div>
              <div className="p-5">
                <h4
                  className="text-[14px] font-bold leading-snug tracking-tight mb-2 line-clamp-3"
                  style={{ color: "var(--text-primary)" }}
                >
                  {a.title}
                </h4>
                <p
                  className="text-[12px] leading-relaxed mb-4 line-clamp-3"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {a.excerpt}
                </p>
                <MetaRow date={date} readTime={`${a.readingTime ?? 3} min`} />
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function MetaRow({ date, readTime }: { date: string; readTime: string }) {
  return (
    <div
      className="flex items-center gap-3 text-[10px]"
      style={{ color: "var(--text-tertiary)" }}
    >
      <span className="inline-flex items-center gap-1">
        <MetaIcon Icon={Calendar} /> {date}
      </span>
      <span>·</span>
      <span className="inline-flex items-center gap-1">
        <MetaIcon Icon={Clock} /> {readTime}
      </span>
    </div>
  );
}

function MetaIcon({ Icon }: { Icon: LucideIcon }) {
  return <Icon width={11} height={11} strokeWidth={1.8} />;
}
