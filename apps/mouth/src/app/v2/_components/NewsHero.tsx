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
    // P0.2 fix: remove md:h-[88vh] overflow-hidden. At 88vh=867px the left column
    // (5 stories ≈1030px) was hidden behind overflow:hidden — 472px invisible.
    // min-h lets it grow; overflow-hidden moves only to the photo column.
    <section
      id="news"
      className="relative md:min-h-[88vh] scroll-mt-20"
      style={{ background: "var(--surface-base)" }}
    >
      {/* B2R2 mobile: the 32/68 two-col grid stacks — photo card first
          (it carries the active title), numbered story list below, both
          full-width. Desktop (md+) is byte-identical to before. */}
      <div className="grid grid-cols-1 md:grid-cols-[32%_68%]">
        {/* Left — numbered index. P0.2: flex flex-col, no h-full constraint
            (grows with content; all 5 stories visible at every viewport height). */}
        <div className="order-2 md:order-1 flex flex-col justify-center px-5 py-10 md:px-12 md:py-16">
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
                  {/* MYTHOS B2R: on the light homepage the --rp-* hooks turn
                      this list ink-on-paper with a single navy active state
                      (chromatic calm); /news + /v2 keep the per-category
                      accents + glow via the var() fallbacks. */}
                  <button
                    onClick={() => setActive(i)}
                    className="w-full text-left flex items-start gap-5 p-5 rounded-xl transition-all"
                    style={{
                      background: isActive
                        ? `var(--rp-active-bg, color-mix(in srgb, ${accent} 14%, transparent))`
                        : "var(--rp-list-bg, rgba(255,255,255,0.02))",
                      border: isActive
                        ? `1px solid var(--rp-active-border, color-mix(in srgb, ${accent} 50%, transparent))`
                        : "1px solid var(--rp-list-border, rgba(255,255,255,0.05))",
                      boxShadow: isActive
                        ? `var(--rp-glow, 0 0 32px color-mix(in srgb, ${accent} 20%, transparent), inset 0 1px 0 rgba(255,255,255,0.08))`
                        : "none",
                    }}
                  >
                    <span
                      className="text-[22px] font-extrabold tabular-nums leading-none pt-0.5 shrink-0"
                      style={{
                        color: isActive
                          ? `var(--rp-accent, ${accent})`
                          : "var(--text-tertiary)",
                        textShadow: isActive
                          ? `var(--rp-glow, 0 0 20px color-mix(in srgb, ${accent} 50%, transparent))`
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
                          color: isActive
                            ? `var(--rp-accent, ${accent})`
                            : "var(--text-tertiary)",
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

        {/* Right — image + large title. P0.2: sticky so photo stays in view
            while the story list grows below md breakpoint. overflow-hidden
            moved HERE (not on the section) so clip only affects the photo box. */}
        <div className="order-1 md:order-2 relative h-[55vh] md:sticky md:top-14 md:self-start md:max-h-[calc(88vh-3.5rem)] md:overflow-hidden">
          <div
            className="absolute overflow-hidden"
            style={{
              inset: "var(--rp-photo-inset, 0)",
              borderRadius: "var(--rp-photo-radius, 0)",
            }}
          >
            {slides.map((s, i) => {
              const accent = CATEGORY_ACCENT[s.category] || "#d4a017";
              return (
                // P0.4 fix: the whole Link was transitioning opacity — both headline
                // and pill were 50% visible during the 1000ms cross-fade, creating
                // overlapping ghost text. Now only the image fades; text/pill are
                // in a separate non-transitioning layer that swaps instantly.
                // inactive slides: visibility:hidden (delayed) prevents AT reading
                // invisible text and stops any residual pixel-bleed.
                <Link
                  href={`/${s.category}/${s.slug}`}
                  key={s.id}
                  data-homepage-position={
                    i === 0 ? "hero_main" : `hero_${i + 1}`
                  }
                  aria-hidden={i !== active}
                  tabIndex={i === active ? 0 : -1}
                  className="absolute inset-0 group"
                  style={{
                    // visibility delayed so it hides AFTER the opacity fade completes
                    visibility: i === active ? "visible" : "hidden",
                    transition: i === active ? "none" : "visibility 0s 0.3s",
                    pointerEvents: i === active ? "auto" : "none",
                  }}
                >
                  {/* P0.4: placeholder hidden once the real image is visible.
                      Previously it showed through during load on every slide. */}
                  {i !== active ? null : (
                    <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface-muted)]">
                      <span className="text-[var(--text-tertiary)] text-[11px] font-semibold uppercase tracking-[0.15em]">
                        {s.category ?? "Bali Zero"}
                      </span>
                    </div>
                  )}
                  {/* P0.4: image-only fade wrapper. opacity here, NOT on the Link.
                      Duration 300ms (was 1000ms). prefers-reduced-motion disables. */}
                  <div
                    className="absolute inset-0"
                    style={{
                      opacity: i === active ? 1 : 0,
                      transition: "opacity 0.3s ease",
                    }}
                  >
                    <Image
                      src={s.coverImage as string}
                      alt={s.title || ""}
                      fill
                      // P3: corrected sizes — this is a 68vw portrait slot, not 900px wide
                      sizes="(max-width: 768px) 100vw, 68vw"
                      quality={75}
                      loading={i === 0 ? "eager" : "lazy"}
                      priority={i === 0}
                      className="object-cover transition-transform duration-700 group-hover:scale-[1.03]"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  </div>
                  {/* Scrim */}
                  <div
                    className="absolute inset-0"
                    style={{
                      background:
                        "linear-gradient(0deg, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.42) 55%, rgba(0,0,0,0.05) 100%)",
                    }}
                  />
                  {/* Text overlay — outside the fading div so it swaps instantly (no ghost overlap) */}
                  <div className="absolute bottom-0 left-0 right-0 p-6 md:p-12 md:pr-16">
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
                    {/* B2R2: 25px on mobile, original clamp from md up —
                        desktop output is byte-identical. */}
                    <h3
                      className="font-black leading-[1.05] tracking-tight mb-4 line-clamp-3 text-[25px] md:text-[clamp(30px,3.4vw,52px)]"
                      style={{
                        color: "#ffffff",
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
      </div>

      <button
        onClick={() => setPaused((p) => !p)}
        aria-label={paused ? "Play news carousel" : "Pause news carousel"}
        className="absolute top-4 right-4 md:top-auto md:bottom-8 md:right-8 z-30 w-11 h-11 md:w-9 md:h-9 rounded-full flex items-center justify-center transition-all hover:scale-110"
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
