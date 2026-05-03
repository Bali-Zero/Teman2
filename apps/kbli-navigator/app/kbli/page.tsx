import type { Metadata } from 'next';
import Link from 'next/link';
import { getSections } from '@/lib/kbli-data';
import { KBLISearch } from '@/components/kbli/KBLISearch';
import { KBLISectorGrid } from '@/components/kbli/KBLISectorGrid';
import { ZantaraChat } from '@/components/kbli/ZantaraChat';

export const metadata: Metadata = {
  title: 'KBLI 2025 Navigator — Indonesia Business Classification Guide',
  description:
    "Navigate Indonesia's 1,563 KBLI 2025 business codes. PMA investment rules, licensing requirements, and 2020→2025 transition mapping. Powered by Zantara AI.",
  openGraph: {
    title: 'KBLI 2025 Navigator — Zantara by Bali Zero',
    description:
      "The definitive guide to Indonesia's KBLI 2025 business classification. 1,563 codes, PMA rules, and AI-powered analysis.",
    type: 'website',
  },
};

export default function KBLIHomePage() {
  const sections = getSections().filter((s) => s.codeCount > 0);

  return (
    <div className="space-y-12 animate-fade-in-up">
      {/* Hero — gradient impact zone with Parallax Background */}
      <div className="relative -mx-4 overflow-hidden rounded-3xl sm:-mx-6 lg:-mx-8 shadow-2xl bg-[#1c1c1e]">
        {/* Parallax Background Image */}
        <div
          className="absolute inset-0 bg-cover bg-fixed bg-center bg-no-repeat opacity-40 mix-blend-luminosity"
          style={{ backgroundImage: "url('/kbli-hero.jpg')" }}
        />

        {/* Dark Vignette Overlay to ensure text readability */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#1c1c1e]/40 via-[#1c1c1e]/60 to-[#1c1c1e] z-0" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#1c1c1e]/80 via-transparent to-[#1c1c1e]/80 z-0" />

        {/* Multi-color gradient (Warm pink/orange to deep teal) */}
        <div
          className="absolute inset-0 animate-aurora mix-blend-color z-0"
          style={{
            background:
              'linear-gradient(90deg, rgba(212,132,90,0.5) 0%, rgba(168,85,247,0.5) 25%, rgba(59,130,246,0.5) 55%, rgba(20,184,166,0.5) 100%)',
            opacity: 0.8,
          }}
        />
        {/* Decorative radials to soften the fade */}
        <div
          className="absolute inset-0 z-0"
          style={{
            background:
              'radial-gradient(ellipse at top center, rgba(255,255,255,0.05) 0%, transparent 70%), radial-gradient(ellipse at bottom center, rgba(0,0,0,0.6) 0%, transparent 100%)',
          }}
        />
        {/* Noise overlay for texture */}
        <div
          className="absolute inset-0 opacity-[0.05] z-0"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          }}
        />

        <div className="relative z-10 px-6 py-16 text-center sm:px-8 sm:py-24 lg:px-10 flex flex-col items-center justify-center min-h-[420px] animate-float">
          <h1 className="text-5xl font-black tracking-tight sm:text-6xl lg:text-7xl drop-shadow-lg text-transparent bg-clip-text bg-gradient-to-r from-white via-white to-white/70">
            KBLI 2025 Navigator
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base text-[#e2e8f0] sm:text-lg font-medium tracking-wide drop-shadow-sm">
            Indonesia&apos;s complete business classification system — 1,563 codes with PMA
            investment rules, licensing requirements, and
            <span className="text-white/90"> 2020→2025 transition mapping.</span>
          </p>

          {/* Stats strip - Glassmorphic Elevated */}
          <div className="mx-auto mt-12 mb-2 flex flex-wrap items-center justify-center gap-6 sm:gap-8">
            <div className="px-6 py-4 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.2)]">
              <div className="text-4xl font-black text-white tracking-tight drop-shadow-sm">
                1,563
              </div>
              <div className="mt-1 text-[11px] font-bold uppercase tracking-widest text-[#d4845a] drop-shadow-sm">
                Codes
              </div>
            </div>
            <div className="px-6 py-4 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.2)]">
              <div className="text-4xl font-black text-white tracking-tight drop-shadow-sm">21</div>
              <div className="mt-1 text-[11px] font-bold uppercase tracking-widest text-[#a855f7] drop-shadow-sm">
                Sectors
              </div>
            </div>
            <div className="px-6 py-4 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.2)] relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
              <div className="text-4xl font-black text-white tracking-tight drop-shadow-sm relative z-10">
                300+
              </div>
              <div className="mt-1 text-[11px] font-bold uppercase tracking-widest text-[#3b82f6] drop-shadow-sm relative z-10">
                Gold Intel
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Search Command Center (Sticky) */}
      <div className="sticky top-20 z-40 -mx-4 px-4 py-4 backdrop-blur-xl bg-[#1c1c1e]/60 border-b border-white/5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 shadow-[0_10px_30px_rgba(0,0,0,0.3)] rounded-b-3xl mb-8">
        <KBLISearch autoFocus />

        {/* Quick Filters */}
        <div className="mt-4 flex flex-wrap items-center gap-2 justify-center lg:justify-start">
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mr-2">
            Quick:
          </span>
          {['Restaurant', 'Tech', 'Real Estate', 'Retail', 'Manufacturing'].map((filter) => (
            <Link
              key={filter}
              href={`/kbli/search?q=${encodeURIComponent(filter)}`}
              className="px-3 py-1.5 rounded-full text-xs font-medium text-zinc-300 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-all hover:border-[#d4845a]/50 hover:shadow-[0_0_15px_rgba(212,132,90,0.2)]"
              aria-label={`Quick search: ${filter}`}
            >
              {filter}
            </Link>
          ))}
        </div>
      </div>

      {/* Sectors Grid */}
      <section>
        <h2 className="mb-4 text-xl font-semibold text-[var(--foreground)]">Browse by Sector</h2>
        <KBLISectorGrid sections={sections} />
      </section>

      {/* Zantara AI */}
      <section>
        <ZantaraChat
          opener="I'm Zantara, your KBLI expert. Ask me anything about Indonesian business codes — which ones you need, PMA rules, what changed in 2025, or how to set up in Bali."
          suggestions={[
            'What KBLI do I need for a restaurant in Bali?',
            'Can foreigners own a villa rental business?',
            'What changed from KBLI 2020 to 2025?',
            "What's the difference between 55101 and 55203?",
          ]}
        />
      </section>
    </div>
  );
}
