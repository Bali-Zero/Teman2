import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getSections } from "@/lib/kbli-data";
import { KBLISearch } from "@/components/kbli/KBLISearch";
import { KBLISectorGrid } from "@/components/kbli/KBLISectorGrid";
import { ZantaraChat } from "@/components/kbli/ZantaraChat";
import { FunnelFrame } from "@balizero/core";

export const metadata: Metadata = {
  title: "KBLI 2025 Navigator — Indonesia Business Classification Guide",
  description:
    "Navigate Indonesia's 1,563 KBLI 2025 business codes. PMA investment rules, licensing requirements, and 2020→2025 transition mapping. Powered by Zantara AI.",
  openGraph: {
    title: "KBLI 2025 Navigator — Zantara by Bali Zero",
    description:
      "The definitive guide to Indonesia's KBLI 2025 business classification. 1,563 codes, PMA rules, and AI-powered analysis.",
    type: "website",
  },
};

export default function KBLIHomePage() {
  const sections = getSections().filter((s) => s.codeCount > 0);

  return (
    <FunnelFrame
      funnel="kbli"
      sessionId="SSR"
      trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
    >
      <div className="space-y-16">
        {/* ── HERO ── */}
        <div className="relative -mx-4 overflow-hidden rounded-3xl sm:-mx-6 lg:-mx-8 bg-[#141416]">
          {/* Balinese ornamental pattern */}
          <div
            className="absolute inset-0 opacity-100"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='none'/%3E%3Crect x='0' y='0' width='200' height='200' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='50' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='30' fill='none' stroke='rgba(255,255,255,0.025)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='8' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='2' fill='rgba(255,255,255,0.05)'/%3E%3Cpath d='M100,50 Q120,70 100,90 Q80,70 100,50Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Cpath d='M100,150 Q120,130 100,110 Q80,130 100,150Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Cpath d='M50,100 Q70,120 90,100 Q70,80 50,100Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3Cpath d='M150,100 Q130,120 110,100 Q130,80 150,100Z' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='0.5'/%3E%3C/svg%3E")`,
              backgroundSize: "200px 200px",
            }}
          />
          {/* Vignette */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 80% 70% at 50% 50%, transparent 30%, rgba(20,20,22,0.9) 100%)",
            }}
          />
          {/* Ambient orbs — subtle red and white for Indonesian flag feel */}
          <div
            className="absolute top-[-15%] left-[10%] w-[500px] h-[500px] rounded-full opacity-[0.06] blur-[120px]"
            style={{
              background: "radial-gradient(circle, #dc2626, transparent)",
            }}
          />
          <div
            className="absolute top-[-10%] right-[15%] w-[400px] h-[400px] rounded-full opacity-[0.04] blur-[100px]"
            style={{
              background: "radial-gradient(circle, #ffffff, transparent)",
            }}
          />
          <div
            className="absolute bottom-[-15%] right-[-5%] w-[350px] h-[350px] rounded-full opacity-[0.05] blur-[100px]"
            style={{
              background: "radial-gradient(circle, #dc2626, transparent)",
            }}
          />

          <div className="relative z-10 flex flex-col lg:flex-row items-center lg:items-start justify-between gap-12 px-8 py-16 sm:px-12 sm:py-20 lg:px-16 lg:py-24">
            {/* Left column */}
            <div className="flex flex-col items-center lg:items-start text-center lg:text-left max-w-xl">
              {/* Bali Zero branding */}
              <div className="flex items-center gap-3 mb-8">
                <Image
                  src="/assets/logo/balizero-logo-clean.png"
                  alt="Bali Zero"
                  width={48}
                  height={48}
                  className="rounded-full"
                />
                <div className="text-[13px] font-semibold text-white/80 leading-tight tracking-wide">
                  <span className="block">We don&apos;t sell services.</span>
                  <span className="block text-white/50">
                    We offer intelligence.
                  </span>
                </div>
              </div>

              {/* Main title — KBLI 2025 on one line, Montserrat, Indonesian flag effect */}
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-none kbli-flag-title">
                KBLI 2025
              </h1>

              {/* Subtitle */}
              <p className="mt-5 text-xl sm:text-2xl text-zinc-400 font-light tracking-tight">
                Your{" "}
                <em className="text-white font-medium not-italic">
                  Indonesian
                </em>{" "}
                Business Codes
              </p>

              {/* Inline stats */}
              <p className="mt-3 text-sm text-zinc-500 tracking-wide">
                1,563 codes&ensp;&middot;&ensp;22 sectors&ensp;&middot;&ensp;PMA
                rules
              </p>

              {/* CTA — glassmorphism button */}
              <Link
                href="#search"
                className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white/[0.06] backdrop-blur-md border border-white/[0.1] px-7 py-3.5 text-sm font-bold text-white shadow-[0_4px_20px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.06)] transition-all duration-300 hover:bg-[#dc2626]/90 hover:border-[#dc2626]/60 hover:shadow-[0_0_40px_rgba(220,38,38,0.3)] active:scale-[0.98]"
              >
                Explore All KBLI Sectors &rarr;
              </Link>
            </div>

            {/* Right column — 3D tilted tablet with video (lg+ only) */}
            <div className="hidden lg:flex flex-shrink-0 items-center justify-center flex-1 max-w-[580px] relative">
              {/* Glow behind tablet */}
              <div
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[320px] h-[320px] blur-[80px] pointer-events-none"
                style={{
                  background:
                    "radial-gradient(circle, rgba(220,38,38,0.06), transparent 70%)",
                }}
              />
              <div
                className="relative z-10 transition-transform duration-[400ms]"
                style={{
                  transform:
                    "perspective(1000px) rotateY(-12deg) rotateX(4deg) rotate(-3deg)",
                  transformStyle: "preserve-3d",
                  filter:
                    "drop-shadow(0 40px 60px rgba(0,0,0,0.6)) drop-shadow(0 0 30px rgba(220,38,38,0.08))",
                }}
              >
                {/* Tablet frame — glassmorphism */}
                <div
                  className="rounded-[36px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl p-[18px] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                  style={{ width: 442 }}
                >
                  {/* Camera */}
                  <div className="flex justify-center py-1.5 pb-2.5">
                    <div className="w-2 h-2 rounded-full bg-white/[0.08]" />
                  </div>
                  {/* Screen with video */}
                  <div
                    className="rounded-[18px] bg-black/60 overflow-hidden"
                    style={{ height: 286 }}
                  >
                    <video
                      src="/videos/kbli-demo.mp4"
                      autoPlay
                      loop
                      playsInline
                      controls
                      className="w-full h-full object-cover block rounded-[18px]"
                    />
                  </div>
                  {/* Home bar */}
                  <div className="flex justify-center pt-2.5 pb-1.5">
                    <div className="w-[60px] h-1 rounded-sm bg-white/[0.08]" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── TRUST BAR ── */}
        <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 -mt-4">
          {[
            { num: "1,563", label: "KBLI Codes" },
            { num: "22", label: "Industry Sectors" },
            { num: "100%", label: "PMA Coverage" },
            { num: "AI", label: "Powered by Zantara" },
          ].map((t) => (
            <div
              key={t.label}
              className="text-center px-6 py-4 rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] shadow-[0_4px_24px_rgba(0,0,0,0.25),inset_0_1px_0_rgba(255,255,255,0.04)] transition-all duration-300 hover:bg-white/[0.05] hover:border-white/[0.1] hover:shadow-[0_8px_32px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)]"
            >
              <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {t.num}
              </div>
              <div className="mt-1 text-[10px] font-bold uppercase tracking-[0.12em] text-zinc-500">
                {t.label}
              </div>
            </div>
          ))}
        </div>

        {/* ── SEARCH ── */}
        <div
          id="search"
          className="sticky top-20 z-40 -mx-4 px-4 py-4 backdrop-blur-2xl bg-[#141416]/80 border border-white/[0.05] sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 shadow-[0_10px_40px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.03)] rounded-3xl mb-8"
        >
          <KBLISearch autoFocus />
          <div className="mt-4 flex flex-wrap items-center gap-2 justify-center lg:justify-start">
            <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mr-2">
              Quick:
            </span>
            {[
              "Restaurant",
              "Tech",
              "Real Estate",
              "Retail",
              "Manufacturing",
            ].map((filter) => (
              <button
                key={filter}
                className="px-3.5 py-1.5 rounded-full text-xs font-medium text-zinc-400 bg-white/[0.04] backdrop-blur-md border border-white/[0.06] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] hover:bg-white/[0.07] hover:text-white transition-all duration-300 hover:border-red-500/30 hover:shadow-[0_0_20px_rgba(220,38,38,0.08),inset_0_1px_0_rgba(255,255,255,0.06)]"
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        {/* ── SECTORS ── */}
        <section>
          <h2 className="mb-4 text-xl font-semibold text-white/90">
            Browse by Sector
          </h2>
          <KBLISectorGrid sections={sections} />
        </section>

        {/* ── ZANTARA AI ── */}
        <section>
          <ZantaraChat
            opener="I'm Zantara, your KBLI expert. Ask me anything about Indonesian business codes — which ones you need, PMA rules, what changed in 2025, or how to set up in Bali."
            suggestions={[
              "What KBLI do I need for a restaurant in Bali?",
              "Can foreigners own a villa rental business?",
              "What changed from KBLI 2020 to 2025?",
              "What's the difference between 55101 and 55203?",
            ]}
          />
        </section>
      </div>
    </FunnelFrame>
  );
}
