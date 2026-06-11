"use client";

import { ArrowRight } from "lucide-react";
import { trackHeroCTA } from "@/lib/analytics";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";

/**
 * HeroCTA — Client Component wrapper for hero section CTA links.
 *
 * Extracted from HeroBlueprint (Server Component) to keep the parent
 * zero-JS while enabling onClick analytics. Renders the two hero CTAs
 * with identical className / style to the original markup.
 *
 * Triple-dispatch on click: GA4 + internal CRM bus + funnel store.
 * Events registered in packages/core/analytics/funnel-view.ts:
 *   - hero_cta_book_call
 *   - hero_cta_read_dispatch
 */
export function HeroCTA() {
  return (
    <div className="flex items-center gap-4 md:gap-8 mb-6 md:mb-10 flex-wrap">
      <a
        href={buildWhatsAppLink(
          "home",
          "Hi Bali Zero, I'd like to book a 30-minute call.",
        )}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold transition-transform hover:-translate-y-0.5"
        style={{
          background: "#ffffff",
          color: "#121016",
          boxShadow: "0 10px 32px rgba(0,0,0,0.35)",
        }}
        onClick={() => trackHeroCTA("hero_cta_book_call")}
      >
        Book a 30-minute call
        <ArrowRight size={15} strokeWidth={2.2} />
      </a>
      <a
        href="#news"
        className="text-[13px] font-semibold underline-offset-4 hover:underline"
        style={{ color: "rgba(255,255,255,0.85)" }}
        onClick={() => trackHeroCTA("hero_cta_read_dispatch")}
      >
        Read the dispatch →
      </a>
    </div>
  );
}
