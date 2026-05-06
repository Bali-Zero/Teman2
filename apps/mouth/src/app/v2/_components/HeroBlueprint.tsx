import Image from "next/image";
import { ArrowRight } from "lucide-react";
import { BZLogo } from "@balizero/core/components/BZLogo";

/**
 * HeroBlueprint — Essay-Opener hero.
 *
 * Concept: the team photographed in a Balinese temple courtyard clad in
 * Carrara marble — two institutional traditions in quiet dialogue.
 * Copy follows the X_BRAND_VOICE.md "bar conversation" register:
 * grounded, sharp, warm-blooded. No "AI-powered", no "premium boutique",
 * no "structured". One concrete observation, one honest commitment,
 * one call to book.
 *
 * Server Component. Zero JS. Image via next/image with priority.
 */
export function HeroBlueprint() {
  return (
    <section
      id="top"
      className="relative overflow-hidden"
      style={{ background: "var(--surface-base)" }}
    >
      {/* Full-bleed hero image — 4:5 on mobile, 21:9 on desktop */}
      <div className="relative w-full hero-aspect">
        <Image
          src="/assets/art/hero-team.jpeg"
          alt="The Bali Zero team mid-conversation in a Balinese bale pavilion — seven members on white Carrara marble benches, stone guardian statue and canang offerings beside them"
          fill
          priority
          fetchPriority="high"
          sizes="100vw"
          quality={75}
          className="object-cover"
          style={{ objectPosition: "center center" }}
        />
        {/* Darken gradient — stronger on mobile (vertical), side-to-side on desktop */}
        <div className="absolute inset-0 hero-gradient" />
        {/* Bottom fade into page */}
        <div
          className="absolute inset-x-0 bottom-0 h-32 pointer-events-none"
          style={{
            background:
              "linear-gradient(180deg, transparent 0%, var(--surface-base) 100%)",
          }}
        />

        {/* Big BALI ZERO logo — top-right on desktop, below nav on mobile */}
        <div
          className="absolute top-[68px] right-4 md:top-8 md:right-8 lg:top-12 lg:right-16 pointer-events-none z-10 hero-logo"
          style={{
            filter: "drop-shadow(0 4px 24px rgba(0,0,0,0.55))",
          }}
        >
          <BZLogo variant="full" size={120} priority />
        </div>

        {/* Copy overlay — centered on mobile, left-aligned on desktop */}
        <div className="absolute inset-0 flex items-end md:items-center pb-8 md:pb-0">
          <div className="w-full max-w-[1400px] mx-auto px-6 md:px-10 lg:px-16">
            <div className="max-w-[560px]">
              {/* Dateline */}
              <div
                className="text-[10px] font-semibold uppercase tracking-[0.28em] mb-2"
                style={{ color: "rgba(255,255,255,0.5)" }}
              >
                Bali Zero · Dispatch · April 2026 · Kerobokan
              </div>
              {/* Tagline */}
              <div
                className="font-semibold italic mb-4 md:mb-8"
                style={{
                  color: "rgba(255,255,255,0.82)",
                  fontSize: "clamp(13px, 1.1vw, 15px)",
                  letterSpacing: "0.02em",
                  textShadow: "0 1px 10px rgba(0,0,0,0.4)",
                }}
              >
                Your Bali, from Zero.
              </div>

              {/* Lede — brand-voice essay opener */}
              <h1
                className="font-bold tracking-tight mb-5 md:mb-8"
                style={{
                  color: "#ffffff",
                  fontSize: "clamp(22px, 3.2vw, 48px)",
                  lineHeight: 1.15,
                  textShadow: "0 2px 24px rgba(0,0,0,0.5)",
                }}
              >
                Most people moving to Bali pick the wrong visa in the first
                month.
                <br />
                <span style={{ color: "rgba(255,255,255,0.72)" }}>
                  Sign a lease that does not hold up under PP 18/2021. Find out
                  only at tax time.
                </span>
              </h1>

              <p
                className="mb-6 md:mb-10 hidden sm:block"
                style={{
                  color: "rgba(255,255,255,0.82)",
                  fontSize: "clamp(14px, 1.2vw, 17px)",
                  lineHeight: 1.55,
                  textShadow: "0 1px 12px rgba(0,0,0,0.5)",
                }}
              >
                We spend our days fixing that.
                <br />
                We also write about why it keeps happening.
              </p>

              {/* CTAs — text links, not buttons, per brand voice */}
              <div className="flex items-center gap-4 md:gap-8 mb-6 md:mb-10 flex-wrap">
                <a
                  href="#visa"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold transition-transform hover:-translate-y-0.5"
                  style={{
                    background: "#ffffff",
                    color: "#121016",
                    boxShadow: "0 10px 32px rgba(0,0,0,0.35)",
                  }}
                >
                  Book a 30-minute call
                  <ArrowRight size={15} strokeWidth={2.2} />
                </a>
                <a
                  href="#news"
                  className="text-[13px] font-semibold underline-offset-4 hover:underline"
                  style={{ color: "rgba(255,255,255,0.85)" }}
                >
                  Read the dispatch →
                </a>
              </div>

              {/* Trust line — concrete, not generic. Hidden on small mobile. */}
              <div
                className="text-[11px] md:text-[12px] leading-[1.6] hidden sm:block"
                style={{ color: "rgba(255,255,255,0.55)" }}
              >
                Filed this month: 47 KITAS, 9 PT PMAs · Office in Kerobokan
                <br />
                Licensed konsultan pajak · Registered PPJK · Since 2019
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
