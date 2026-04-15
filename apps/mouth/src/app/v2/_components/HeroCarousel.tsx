"use client";

import { useEffect, useState } from "react";
import type { Funnel } from "@balizero/core/components/ThemeProvider";

interface Slide {
  funnel: Exclude<Funnel, null>;
  tool: string;
  headline: string;
  sub: string;
  badge: string;
  cta: string;
}

const SLIDES: Slide[] = [
  {
    funnel: "visa",
    tool: "Visa Oracle",
    headline: "AI-powered visa guidance for every situation",
    sub: "Ask any visa question. Get instant, accurate answers backed by real Indonesian immigration law.",
    badge: "Live · 2,400+ visa cases",
    cta: "Try Visa Oracle →",
  },
  {
    funnel: "kbli",
    tool: "KBLI Navigator",
    headline: "Find your business code in under 60 seconds",
    sub: "Complete KBLI 2025 database. PMA eligibility, risk classification, required licenses.",
    badge: "Live · 1,563 categories",
    cta: "Explore KBLI →",
  },
  {
    funnel: "tax",
    tool: "Tax Intelligence",
    headline: "Indonesian tax compliance, made human",
    sub: "Monthly filing, annual reports, CoreTax integration. Your dedicated tax advisor for Bali business.",
    badge: "Beta · CoreTax integrated",
    cta: "Explore Tax →",
  },
  {
    funnel: "property",
    tool: "Property Map",
    headline: "Know exactly what you can build — and where",
    sub: "Zoning intelligence, due diligence, land certificate verification.",
    badge: "Beta · Bali-wide coverage",
    cta: "Check Zoning →",
  },
];

export function HeroCarousel() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setActive((i) => (i + 1) % SLIDES.length), 4000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="relative h-[100vh] overflow-hidden">
      {SLIDES.map((slide, i) => (
        <article
          key={slide.funnel}
          data-funnel={slide.funnel}
          className="absolute inset-0 flex items-center px-16 transition-opacity duration-1000"
          style={{
            opacity: active === i ? 1 : 0,
            pointerEvents: active === i ? "auto" : "none",
            // Per-slide gradient using the slide's own --accent-funnel.
            // This proves leaf scoping: each slide computes its own accent
            // even though they all live under the same :root.
            background:
              "radial-gradient(ellipse at 30% 50%, color-mix(in srgb, var(--accent-funnel) 18%, transparent), transparent 60%), var(--surface-base)",
          }}
        >
          <div className="max-w-2xl">
            <h2
              className="text-[clamp(52px,5.5vw,84px)] font-black leading-none tracking-tighter mb-4 bz-shimmer"
              style={{ fontFamily: "var(--font-sans)" }}
            >
              {slide.tool}
            </h2>
            <p
              className="text-[clamp(17px,1.7vw,24px)] font-bold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              {slide.headline}
            </p>
            <p className="text-[14px] leading-relaxed mb-5" style={{ color: "var(--text-secondary)" }}>
              {slide.sub}
            </p>
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest mb-7"
              style={{
                background: "color-mix(in srgb, var(--accent-funnel) 12%, transparent)",
                border: "1px solid color-mix(in srgb, var(--accent-funnel) 30%, transparent)",
                color: "var(--accent-funnel-text)",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: "var(--accent-funnel)",
                  boxShadow: "0 0 8px var(--accent-funnel)",
                }}
              />
              {slide.badge}
            </div>
            <div>
              <button
                className="inline-flex items-center px-7 py-3 rounded-xl text-[13px] font-bold transition-transform hover:-translate-y-0.5"
                style={{
                  background: "var(--accent-funnel)",
                  color: "var(--text-on-accent)",
                  boxShadow: "0 8px 32px color-mix(in srgb, var(--accent-funnel) 35%, transparent)",
                }}
              >
                {slide.cta}
              </button>
            </div>
          </div>
        </article>
      ))}

      {/* Dots */}
      <div className="absolute bottom-9 left-16 z-30 flex gap-2">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => setActive(i)}
            aria-label={`Slide ${i + 1}`}
            className="h-1.5 rounded-full transition-all duration-300"
            style={{
              width: active === i ? 24 : 6,
              background: active === i ? "#ffffff" : "rgba(255,255,255,0.2)",
            }}
          />
        ))}
      </div>
    </section>
  );
}
