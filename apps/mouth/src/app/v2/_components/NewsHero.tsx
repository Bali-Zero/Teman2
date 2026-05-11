"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Pause, Play } from "lucide-react";
import type { ArticleListItem } from "@/lib/blog/types";

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
  return map[category] || category;
}

function idxTitle(title: string): string {
  if (!title) return "";
  const trimmed = title.split(/:\s|—\s|–\s/)[0];
  return trimmed.length > 60 ? trimmed.slice(0, 57) + "…" : trimmed;
}

export function NewsHero({ articles }: { articles: ArticleListItem[] }) {
  const slides = (articles || []).filter((a) => !!a.coverImage).slice(0, 5);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || slides.length === 0) return;
    const id = setInterval(
      () => setActive((i) => (i + 1) % slides.length),
      4500,
    );
    return () => clearInterval(id);
  }, [paused, slides.length]);

  if (slides.length === 0) return null;

  return (
    <section
      id="news"
      className="relative h-[88vh] overflow-hidden scroll-mt-20"
      style={{ background: "var(--surface-base)" }}
    >
      <div className="grid grid-cols-[32%_68%] h-full">
        {/* Left — numbered index */}
        <div className="flex flex-col justify-center px-12 py-16">
          <div
            className="text-[11px] font-semibold uppercase tracking-widest mb-8"
            style={{ color: "var(--text-tertiary)" }}
          >
            Intelligence · Top Stories
          </div>
          <ol className="flex flex-col gap-3 list-none p-0 m-0">
            {slides.map((s, i) => {
              const isActive = i === active;
              const accent = CATEGORY_ACCENT[s.category] || "#d4a017";
              return (
                <li key={s.id}>
                  <button
                    onClick={() => setActive(i)}
                    className="w-full text-left flex items-start gap-5 p-5 rounded-xl transition-all"
                    style={{
                      background: isActive
                        ? `color-mix(in srgb, ${accent} 14%, transparent)`
                        : "rgba(255,255,255,0.02)",
                      border: isActive
                        ? `1px solid color-mix(in srgb, ${accent} 50%, transparent)`
                        : "1px solid rgba(255,255,255,0.05)",
                      boxShadow: isActive
                        ? `0 0 32px color-mix(in srgb, ${accent} 20%, transparent), inset 0 1px 0 rgba(255,255,255,0.08)`
                        : "none",
                    }}
                  >
                    <span
                      className="text-[22px] font-extrabold tabular-nums leading-none pt-0.5 shrink-0"
                      style={{
                        color: isActive ? accent : "var(--text-tertiary)",
                        textShadow: isActive
                          ? `0 0 20px color-mix(in srgb, ${accent} 50%, transparent)`
                          : "none",
                      }}
                    >
                      0{i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span
                        className="text-[17px] font-bold block leading-snug tracking-tight line-clamp-2"
                        style={{
                          color: isActive
                            ? "var(--text-primary)"
                            : "var(--text-secondary)",
                        }}
                      >
                        {idxTitle(s.title)}
                      </span>
                      <span
                        className="text-[10px] font-bold uppercase tracking-[0.18em] block mt-1.5"
                        style={{
                          color: isActive ? accent : "var(--text-tertiary)",
                        }}
                      >
                        {formatCategory(s.category)}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>

        {/* Right — image + large title */}
        <div className="relative h-full">
          {slides.map((s, i) => {
            const accent = CATEGORY_ACCENT[s.category] || "#d4a017";
            return (
              <Link
                href={`/${s.category}/${s.slug}`}
                key={s.id}
                aria-hidden={i !== active}
                tabIndex={i === active ? 0 : -1}
                className="absolute inset-0 transition-opacity duration-1000 group"
                style={{
                  opacity: i === active ? 1 : 0,
                  pointerEvents: i === active ? "auto" : "none",
                }}
              >
                <Image
                  src={s.coverImage as string}
                  alt={s.title || ""}
                  fill
                  sizes="(max-width: 768px) 100vw, 900px"
                  quality={75}
                  loading={i === 0 ? "eager" : "lazy"}
                  priority={i === 0}
                  className="object-cover transition-transform duration-700 group-hover:scale-[1.03]"
                />
                <div
                  className="absolute inset-0"
                  style={{
                    background:
                      "linear-gradient(0deg, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.42) 55%, rgba(0,0,0,0.05) 100%)",
                  }}
                />
                <div className="absolute bottom-0 left-0 right-0 p-12 pr-16">
                  <div
                    className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[10px] font-bold uppercase tracking-widest mb-5"
                    style={{
                      background: `color-mix(in srgb, ${accent} 28%, rgba(0,0,0,0.4))`,
                      border: `1px solid color-mix(in srgb, ${accent} 60%, transparent)`,
                      color: "#ffffff",
                      backdropFilter: "blur(12px)",
                      WebkitBackdropFilter: "blur(12px)",
                      boxShadow: `0 0 20px color-mix(in srgb, ${accent} 40%, transparent)`,
                    }}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{
                        background: accent,
                        boxShadow: `0 0 8px ${accent}`,
                      }}
                    />
                    {formatCategory(s.category)}
                  </div>
                  <h3
                    className="font-black leading-[1.05] tracking-tight mb-4 line-clamp-3"
                    style={{
                      color: "#ffffff",
                      fontSize: "clamp(30px, 3.4vw, 52px)",
                      textShadow: "0 4px 24px rgba(0,0,0,0.6)",
                      maxWidth: "22ch",
                    }}
                  >
                    {s.title}
                  </h3>
                  {s.excerpt && (
                    <p
                      className="text-[15px] leading-relaxed max-w-2xl line-clamp-2"
                      style={{
                        color: "rgba(255,255,255,0.82)",
                        textShadow: "0 2px 12px rgba(0,0,0,0.5)",
                      }}
                    >
                      {s.excerpt
                        .replace(/^#+\s*/gm, "")
                        .replace(/\*\*|__|\*|_/g, "")
                        .trim()}
                    </p>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      <button
        onClick={() => setPaused((p) => !p)}
        aria-label={paused ? "Play news carousel" : "Pause news carousel"}
        className="absolute bottom-8 right-8 z-30 w-9 h-9 rounded-full flex items-center justify-center transition-all hover:scale-110"
        style={{
          background: "rgba(255,255,255,0.12)",
          border: "1px solid rgba(255,255,255,0.22)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          color: "#ffffff",
        }}
      >
        {paused ? (
          <Play size={13} strokeWidth={2.2} />
        ) : (
          <Pause size={13} strokeWidth={2.2} />
        )}
      </button>
    </section>
  );
}
