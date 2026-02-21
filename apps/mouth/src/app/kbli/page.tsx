import type { Metadata } from "next";
import { getSections, getAllCodes } from "@/lib/kbli-data.server";
import { GOLD_CODES } from "@/lib/kbli-gold-codes";
import { KBLISectorGrid } from "@/components/kbli/KBLISectorGrid";
import { KBLICard } from "@/components/kbli/KBLICard";
import { KBLISearch } from "@/components/kbli/KBLISearch";
import Link from "next/link";

export const metadata: Metadata = {
  title: "KBLI 2025 Navigator — Indonesian Business Code Guide | Bali Zero",
  description:
    "Find and understand any Indonesian business classification code (KBLI 2025). " +
    "Foreign investment rules, licensing requirements, and expert AI guidance.",
};

export default function KBLIHomePage() {
  const sections = getSections();
  const allCodes = getAllCodes();

  // Featured codes for Bali investors
  const featuredCodes = [
    "56101", // Restaurant
    "55194", // Villa Rental
    "62011", // Software
    "68110", // Real Estate
    "47911", // E-commerce
    "96102", // Spa
  ]
    .map((code) => allCodes.find((c) => c.code === code))
    .filter(Boolean);

  const stats = {
    total: allCodes.length,
    open: allCodes.filter((c) => c.pma.status === "open").length,
    gold: GOLD_CODES.size,
  };

  return (
    <div className="bg-slate-50 min-h-screen">
      {/* Hero Section */}
      <section className="bg-slate-900 text-white py-20 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-bold mb-6 tracking-tight">
            KBLI 2025 <span className="text-amber-500">Navigator</span>
          </h1>
          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto">
            Instant access to all 1,563 Indonesian business codes with
            intelligent search, investment tracking, and AI-powered guidance.
          </p>

          <div className="max-w-2xl mx-auto">
            <KBLISearch navigateOnSubmit autoFocus />
          </div>

          <div className="grid grid-cols-3 gap-8 mt-16 max-w-3xl mx-auto">
            <div className="text-center">
              <div className="text-3xl font-bold text-white">{stats.total}</div>
              <div className="text-xs uppercase tracking-widest text-slate-500 mt-1">
                Total Codes
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-400">
                {stats.open}
              </div>
              <div className="text-xs uppercase tracking-widest text-slate-500 mt-1">
                PMA Open
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-amber-400">
                {stats.gold}
              </div>
              <div className="text-xs uppercase tracking-widest text-slate-500 mt-1">
                Expert Guides
              </div>
            </div>
          </div>
        </div>
      </section>

      <main className="max-w-6xl mx-auto px-4 py-16 space-y-20">
        {/* Featured Section */}
        <section>
          <div className="flex justify-between items-end mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">
                Featured Business Activities
              </h2>
              <p className="text-slate-500 mt-1">
                Most searched codes by foreign investors in Bali.
              </p>
            </div>
            <Link
              href="/kbli/search"
              className="text-amber-600 font-semibold hover:underline text-sm"
            >
              View all codes →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {featuredCodes.map((code: any) => (
              <KBLICard key={code.code} code={code} />
            ))}
          </div>
        </section>

        {/* Sector Grid */}
        <section>
          <div className="mb-8 text-center max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900">
              Browse by Industry Sector
            </h2>
            <p className="text-slate-500 mt-2">
              Explore the full BPS 2025 classification system by category.
            </p>
          </div>

          <KBLISectorGrid sections={sections} />
        </section>

        {/* Zantara AI Banner */}
        <section className="bg-amber-500 rounded-3xl p-8 md:p-12 text-slate-900 flex flex-col md:flex-row items-center gap-8 shadow-2xl shadow-amber-500/20">
          <div className="flex-1 text-center md:text-left">
            <h2 className="text-3xl font-black mb-4 leading-tight uppercase italic">
              Still not sure which KBLI you need?
            </h2>
            <p className="text-lg font-medium opacity-80 mb-0">
              Our Zantara AI assistant can analyze your business idea and
              recommend the exact codes, licenses, and investment structure
              required for success.
            </p>
          </div>
          <div className="shrink-0">
            <Link
              href="/kbli-explorer"
              className="inline-block bg-slate-900 text-white font-bold px-8 py-4 rounded-full hover:scale-105 transition-transform shadow-xl"
            >
              Consult Zantara AI Now
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-12 px-4 bg-white">
        <div className="max-w-5xl mx-auto text-center">
          <p className="text-slate-400 text-sm">
            Powered by Bali Zero • Verified BPS 2025 Data • Legal AI Assistance
          </p>
        </div>
      </footer>
    </div>
  );
}
