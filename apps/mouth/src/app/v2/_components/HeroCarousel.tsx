"use client";

import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import type { Funnel } from "@balizero/core/components/ThemeProvider";
import { BZLogo } from "@balizero/core/components/BZLogo";

interface Slide {
  funnel: Exclude<Funnel, null>;
  badge: string;
  titleTop: string;
  titleAccent: string; // rendered with the red underline + italic-ish emphasis
  titleBottom: string;
  body: string;
  ctaPrimary: string;
  ctaSecondary: string;
  imageUrl: string;
}

const SLIDES: Slide[] = [
  {
    funnel: "visa",
    badge: "5,000+ CLIENTS SERVED SINCE 2019",
    titleTop: "Your",
    titleAccent: "business",
    titleBottom: "in Bali. Done right.",
    body: "Visa, company formation, tax compliance, property due diligence. Four critical operations for any serious expat or investor in Indonesia — executed with precision by a private team.",
    ctaPrimary: "Book a Consultation →",
    ctaSecondary: "View Services",
    imageUrl: "/assets/art/hero-visa.jpg",
  },
  {
    funnel: "kbli",
    badge: "1,563 BUSINESS CATEGORIES · KBLI 2025",
    titleTop: "Your",
    titleAccent: "business",
    titleBottom: "code. In 60 seconds.",
    body: "Complete KBLI 2025 database with PMA eligibility, risk classification and required licenses. Every sector of the Indonesian economy, mapped and searchable.",
    ctaPrimary: "Open Navigator →",
    ctaSecondary: "View Categories",
    imageUrl: "/assets/art/hero-kbli.jpg",
  },
  {
    funnel: "tax",
    badge: "CORETAX INTEGRATED · COMPLIANT FILING",
    titleTop: "Your",
    titleAccent: "taxes",
    titleBottom: "filed. Correctly.",
    body: "Monthly PPh, annual SPT, PPN, BPJS, LKPM. Indonesian tax compliance handled end-to-end by a dedicated team, not automated guesswork.",
    ctaPrimary: "Book a Review →",
    ctaSecondary: "View Services",
    imageUrl: "/assets/art/hero-tax.jpeg",
  },
  {
    funnel: "property",
    badge: "BALI-WIDE COVERAGE · RTRW 2025",
    titleTop: "Your",
    titleAccent: "land",
    titleBottom: "checked. Before you buy.",
    body: "Zoning intelligence, due diligence, land certificate verification. Know exactly what you can build — and where — before the money changes hands.",
    ctaPrimary: "Check Zoning →",
    ctaSecondary: "View Services",
    imageUrl: "/assets/art/hero-zoning.jpeg",
  },
];

const STATS = [
  { n: "5,000+", l: "CLIENTS SERVED" },
  { n: "1,563", l: "KBLI CATEGORIES" },
  { n: "24/7", l: "AI SUPPORT" },
];

export function HeroCarousel() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    // Manual pause button covers WCAG 2.2.2 — timer runs by default.
    if (paused) return;
    const id = setInterval(
      () => setActive((i) => (i + 1) % SLIDES.length),
      3000,
    );
    return () => clearInterval(id);
  }, [paused]);

  return (
    <section className="relative h-[100vh] overflow-hidden">
      {SLIDES.map((slide, i) => (
        <article
          key={slide.funnel}
          data-funnel={slide.funnel}
          aria-hidden={active !== i}
          className="absolute inset-0 grid grid-cols-[36%_64%] transition-opacity duration-1000"
          style={{
            opacity: active === i ? 1 : 0,
            pointerEvents: active === i ? "auto" : "none",
          }}
        >
          {/* Left text column */}
          <div className="flex flex-col justify-center px-14 py-16 relative">
            {/* Round Bali Zero logo + tagline — positioned absolutely in the
                upper-right area of the text column.
                - top: 80 = nav height (56) + breathing gap (24) so it sits
                  below the "Get Started" button, no collision.
                - right: 56 = matches the text column px-14 padding, so the
                  block aligns with the rest of the content's right edge.
                - width: 200 = enough to fit the full tagline on one line
                  without wrapping at this font-size. */}
            <div
              className="absolute z-40 flex flex-col items-center"
              style={{
                top: 80,
                right: 320,
                gap: 8,
                width: 200,
              }}
            >
              <BZLogo variant="round" size={72} />
              <h2
                className="brand-tagline"
                style={{ fontSize: 14, justifyContent: "center" }}
              >
                Your
                <img
                  className="brand-logo-3-img"
                  src="/assets/logo/balizero-3-red-fixed.png?v=1"
                  alt="B"
                  style={{ height: "1.6em", width: "auto" }}
                />
                ali, from Zer
                <span className="brand-om-circle" />
              </h2>
              <p
                className="brand-sub"
                style={{
                  color: "rgba(255,255,255,0.45)",
                  fontSize: 8,
                  margin: 0,
                  textAlign: "center",
                }}
              >
                Visa · Company · Tax · Property · Intelligence
              </p>
            </div>

            {/* Small funnel badge */}
            <div
              className="inline-flex items-center gap-2 self-start rounded-full px-3 py-1.5 text-[10px] font-semibold tracking-[0.15em] uppercase mb-10"
              style={{
                color: "var(--accent-funnel-text)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel) 30%, transparent)",
                background:
                  "color-mix(in srgb, var(--accent-funnel) 8%, transparent)",
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

            {/* Title — giant serif-feeling sans, multi-line */}
            <h1
              className="font-black leading-[0.95] tracking-tight mb-8"
              style={{
                color: "var(--text-primary)",
                fontSize: "clamp(52px, 5.8vw, 88px)",
              }}
            >
              <span className="block">{slide.titleTop}</span>
              <span className="block">{slide.titleAccent}</span>
              <span className="block" style={{ color: "var(--text-primary)" }}>
                <span
                  className="inline-block mr-3 align-middle"
                  style={{
                    width: "0.6em",
                    height: "3px",
                    background: "var(--accent-funnel)",
                    borderRadius: "2px",
                  }}
                />
                {slide.titleBottom}
              </span>
            </h1>

            {/* Body copy */}
            <p
              className="text-[14px] leading-[1.7] max-w-md mb-9"
              style={{ color: "var(--text-secondary)" }}
            >
              {slide.body}
            </p>

            {/* CTAs */}
            <div className="flex items-center gap-5 mb-14">
              <button
                className="inline-flex items-center px-6 py-3 rounded-md text-[13px] font-bold transition-transform hover:-translate-y-0.5"
                style={{
                  background: "var(--accent-funnel)",
                  color: "var(--text-on-accent)",
                  boxShadow:
                    "0 8px 28px color-mix(in srgb, var(--accent-funnel) 40%, transparent)",
                }}
              >
                {slide.ctaPrimary}
              </button>
              <button
                className="text-[13px] font-semibold"
                style={{ color: "var(--text-secondary)" }}
              >
                {slide.ctaSecondary}
              </button>
            </div>

            {/* Stats row */}
            <div className="flex gap-10">
              {STATS.map((s) => (
                <div key={s.l}>
                  <div
                    className="text-[22px] font-extrabold leading-none mb-1.5"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {s.n}
                  </div>
                  <div
                    className="text-[9.5px] tracking-[0.15em] uppercase"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {s.l}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right image column */}
          <div
            className="relative h-full overflow-hidden"
            style={{
              backgroundImage: `url('${slide.imageUrl}')`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              backgroundRepeat: "no-repeat",
            }}
            role="img"
            aria-label={`${slide.titleAccent} ${slide.titleBottom}`}
          />
        </article>
      ))}

      {/* Pause/play — WCAG 2.2.2 */}
      <button
        onClick={() => setPaused((p) => !p)}
        aria-label={paused ? "Play carousel" : "Pause carousel"}
        className="absolute bottom-8 right-24 z-30 w-8 h-8 rounded-full flex items-center justify-center transition-all hover:scale-110"
        style={{
          background: "rgba(255,255,255,0.14)",
          border: "1px solid rgba(255,255,255,0.25)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          color: "#ffffff",
        }}
      >
        {paused ? (
          <Play size={12} strokeWidth={2.2} />
        ) : (
          <Pause size={12} strokeWidth={2.2} />
        )}
      </button>

      {/* Dots — bottom right over image */}
      <div className="absolute bottom-8 right-8 z-30 flex gap-2">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => setActive(i)}
            aria-label={`Slide ${i + 1}`}
            className="h-1.5 rounded-full transition-all duration-300"
            style={{
              width: active === i ? 28 : 6,
              background: active === i ? "#ffffff" : "rgba(255,255,255,0.35)",
            }}
          />
        ))}
      </div>
    </section>
  );
}
