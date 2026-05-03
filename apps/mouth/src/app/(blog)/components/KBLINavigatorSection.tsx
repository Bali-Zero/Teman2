"use client";

import Link from "next/link";
import {
  ArrowRight,
  Search,
  Activity,
  Building2,
  Sparkles,
} from "lucide-react";
import { KBLISearch } from "@/components/kbli/KBLISearch";

export default function KBLINavigatorSection() {
  return (
    <section className="border-b border-white/10">
      <div className="max-w-[1400px] mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
          {/* Left: Hero Video */}
          <div className="relative aspect-video lg:aspect-auto lg:min-h-[500px] overflow-hidden">
            <video
              src="/videos/kbli-logo-puzzle.mp4"
              autoPlay
              loop
              muted
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
            />
          </div>

          {/* Right: Content */}
          <div className="bg-gradient-to-br from-[#0a2540] to-[#051C2C] p-10 lg:p-16 flex flex-col justify-center">
            <span className="text-accent-blue-editorial text-xs font-semibold uppercase tracking-wider mb-4">
              Featured Tool
            </span>
            <h2 className="font-serif text-3xl lg:text-4xl text-white mb-4 leading-tight">
              KBLI 2025 Navigator
            </h2>
            <p className="text-white/70 text-lg mb-8 leading-relaxed">
              Instant access to all 1,563 KBLI 2025 codes with intelligent
              search, 4-level risk assessment, PMA status tracking, and
              AI-powered guidance.
            </p>

            <div className="mb-8">
              <KBLISearch
                className="max-w-md"
                placeholder="Search KBLI (e.g. villa, restaurant)..."
              />
            </div>

            <div className="flex flex-wrap gap-3 mb-8 text-sm text-white/60">
              <span className="flex items-center gap-1.5">
                <Search className="w-4 h-4" />
                Smart bilingual search
              </span>
              <span className="flex items-center gap-1.5">
                <Activity className="w-4 h-4" />
                4-level risk system
              </span>
              <span className="flex items-center gap-1.5">
                <Building2 className="w-4 h-4" />
                PMA status tracking
              </span>
              <span className="flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" />
                AI assistant
              </span>
            </div>

            <Link
              href="/kbli"
              className="inline-flex items-center gap-3 text-white group w-fit"
            >
              <span className="text-lg font-medium">Explore Navigator</span>
              <span className="w-10 h-10 rounded-full border-2 border-white/40 flex items-center justify-center group-hover:bg-accent-blue-editorial group-hover:border-accent-blue-editorial transition-all duration-300">
                <ArrowRight className="w-4 h-4" />
              </span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
