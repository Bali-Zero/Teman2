"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Pause, Play } from "lucide-react";

interface NewsSlide {
  idxTitle: string; // short title in the left index
  heroTitle: string; // large title on the image
  heroSub: string; // subtitle on the image
  tag: string;
  image: string;
  accent: string; // hex color for the index item + tag pill
}

// Color coding: red=Immigration, blue=Tax, green=Property, gold=Business.
// Extras use vibrant secondaries: orange, cyan, pink, white for variety.
const SLIDES: NewsSlide[] = [
  {
    idxTitle: "Immigration Queue",
    heroTitle: "5 AM at the Immigration Office",
    heroSub:
      "Why the 2026 KITAS reform isn't solving what everyone thinks it's solving.",
    tag: "Immigration",
    image: "/assets/art/news/immigration-queue.jpg",
    accent: "#ff2d4c", // red
  },
  {
    idxTitle: "The Expat Tax Trap",
    heroTitle: "Kitchen Table, Three Residencies, One Tax Bill",
    heroSub:
      "The 183-day rule nobody explains until the first assessment arrives.",
    tag: "Tax",
    image: "/assets/art/news/expat-tax.jpg",
    accent: "#3b82f6", // blue
  },
  {
    idxTitle: "Stamping 2026",
    heroTitle: "Weathered Hands, New System",
    heroSub:
      "CoreTax and digital stamps: what the officer at the counter actually sees.",
    tag: "System",
    image: "/assets/art/news/officer-hands.jpg",
    accent: "#fb923c", // orange
  },
  {
    idxTitle: "The 2 AM Founder",
    heroTitle: "Why Setting Up a PT PMA Alone Fails",
    heroSub:
      "The five hidden compliance tracks running in parallel from day one.",
    tag: "Business",
    image: "/assets/art/news/entrepreneur-night.jpg",
    accent: "#f59e0b", // gold
  },
  {
    idxTitle: "Coastal Zoning",
    heroTitle: "The Fisherman and the Villa",
    heroSub:
      "How Bali's new spatial planning is redrawing the lines between tradition and rent.",
    tag: "Property",
    image: "/assets/art/news/fisherman-beach.jpg",
    accent: "#22c55e", // green
  },
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function NewsHero(_props?: { articles?: any[] }) {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(
      () => setActive((i) => (i + 1) % SLIDES.length),
      3000,
    );
    return () => clearInterval(id);
  }, [paused]);

  return (
    <section
      id="news"
      className="relative h-[88vh] overflow-hidden scroll-mt-20"
      style={{ background: "var(--surface-base)" }}
    >
      <div className="grid grid-cols-[32%_68%] h-full">
        {/* Left — numbered index, color-coded per topic */}
        <div className="flex flex-col justify-center px-12 py-16">
          <div
            className="text-[11px] font-semibold uppercase tracking-widest mb-8"
            style={{ color: "var(--text-tertiary)" }}
          >
            Intelligence · Top Stories
          </div>
          <ol className="flex flex-col gap-3 list-none p-0 m-0">
            {SLIDES.map((s, i) => {
              const isActive = i === active;
              return (
                <li key={s.idxTitle}>
                  <button
                    onClick={() => setActive(i)}
                    className="w-full text-left flex items-start gap-5 p-5 rounded-xl transition-all"
                    style={{
                      background: isActive
                        ? `color-mix(in srgb, ${s.accent} 14%, transparent)`
                        : "rgba(255,255,255,0.02)",
                      border: isActive
                        ? `1px solid color-mix(in srgb, ${s.accent} 50%, transparent)`
                        : "1px solid rgba(255,255,255,0.05)",
                      boxShadow: isActive
                        ? `0 0 32px color-mix(in srgb, ${s.accent} 20%, transparent), inset 0 1px 0 rgba(255,255,255,0.08)`
                        : "none",
                    }}
                  >
                    <span
                      className="text-[22px] font-extrabold tabular-nums leading-none pt-0.5 shrink-0"
                      style={{
                        color: isActive ? s.accent : "var(--text-tertiary)",
                        textShadow: isActive
                          ? `0 0 20px color-mix(in srgb, ${s.accent} 50%, transparent)`
                          : "none",
                      }}
                    >
                      0{i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span
                        className="text-[18px] font-bold block leading-snug tracking-tight"
                        style={{
                          color: isActive
                            ? "var(--text-primary)"
                            : "var(--text-secondary)",
                        }}
                      >
                        {s.idxTitle}
                      </span>
                      <span
                        className="text-[10px] font-bold uppercase tracking-[0.18em] block mt-1.5"
                        style={{
                          color: isActive ? s.accent : "var(--text-tertiary)",
                        }}
                      >
                        {s.tag}
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
          {SLIDES.map((s, i) => (
            <div
              key={s.idxTitle}
              aria-hidden={i !== active}
              className="absolute inset-0 transition-opacity duration-1000"
              style={{
                opacity: i === active ? 1 : 0,
                pointerEvents: i === active ? "auto" : "none",
              }}
            >
              <Image
                src={s.image}
                alt=""
                fill
                sizes="(max-width: 768px) 100vw, 900px"
                quality={78}
                loading={i === 0 ? "eager" : "lazy"}
                priority={i === 0}
                className="object-cover"
                aria-hidden="true"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    "linear-gradient(0deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 50%, rgba(0,0,0,0.1) 100%)",
                }}
              />
              <div className="absolute bottom-0 left-0 right-0 p-12 pr-16">
                <div
                  className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[10px] font-bold uppercase tracking-widest mb-5"
                  style={{
                    background: `color-mix(in srgb, ${s.accent} 28%, rgba(0,0,0,0.4))`,
                    border: `1px solid color-mix(in srgb, ${s.accent} 60%, transparent)`,
                    color: "#ffffff",
                    backdropFilter: "blur(12px)",
                    WebkitBackdropFilter: "blur(12px)",
                    boxShadow: `0 0 20px color-mix(in srgb, ${s.accent} 40%, transparent)`,
                  }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{
                      background: s.accent,
                      boxShadow: `0 0 8px ${s.accent}`,
                    }}
                  />
                  {s.tag}
                </div>
                <h3
                  className="font-black leading-[1] tracking-tight mb-4"
                  style={{
                    color: "#ffffff",
                    fontSize: "clamp(36px, 4vw, 60px)",
                    textShadow: "0 4px 24px rgba(0,0,0,0.6)",
                  }}
                >
                  {s.heroTitle}
                </h3>
                <p
                  className="text-[15px] leading-relaxed max-w-2xl"
                  style={{
                    color: "rgba(255,255,255,0.82)",
                    textShadow: "0 2px 12px rgba(0,0,0,0.5)",
                  }}
                >
                  {s.heroSub}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pause/play for accessibility */}
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
