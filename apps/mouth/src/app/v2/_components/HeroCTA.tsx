"use client";

import { ArrowRight } from "lucide-react";
import { trackHeroCTA } from "@/lib/analytics";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";

/**
 * HeroCTA — Client Component wrapper for hero section CTA links.
 *
 * Extracted from HeroBlueprint (Server Component) to keep the parent
 * zero-JS while enabling onClick analytics.
 *
 * MYTHOS B2 (P2 single-primary): the WhatsApp chat CTA is THE one red
 * primary action of the homepage (`--cta-primary-bg`, class `cta-primary`
 * pinned by e2e). Wording, link and tracking are Subhi's #1205/#1216
 * surface — do not change behavior. The secondary is a ghost button
 * (white-on-photo here; navy-ghost on light surfaces).
 *
 * Triple-dispatch on click: GA4 + internal CRM bus + funnel store.
 * Events registered in packages/core/analytics/funnel-view.ts:
 *   - hero_cta_book_call
 *   - hero_cta_read_dispatch
 */
export function HeroCTA() {
  return (
    <div className="flex items-center gap-4 md:gap-6 mb-6 md:mb-10 flex-wrap">
      <a
        href={buildWhatsAppLink("home")}
        target="_blank"
        rel="noopener noreferrer"
        className="cta-primary inline-flex items-center gap-2 px-6 py-3 rounded-md text-[15px] font-semibold transition-transform hover:-translate-y-0.5"
        style={{
          background: "var(--cta-primary-bg)",
          color: "var(--cta-primary-fg)",
          boxShadow: "0 6px 18px rgba(255,45,76,0.3)",
        }}
        onClick={() => trackHeroCTA("hero_cta_book_call")}
      >
        Chat with us — avg reply: 2 min
        <ArrowRight size={15} strokeWidth={2.2} />
      </a>
      <a
        href="#news"
        className="inline-flex items-center px-4 py-3 rounded-md text-[13px] font-semibold transition-colors"
        style={{
          color: "rgba(255,255,255,0.88)",
          border: "1px solid rgba(255,255,255,0.4)",
          background: "transparent",
        }}
        onClick={() => trackHeroCTA("hero_cta_read_dispatch")}
      >
        Explore Bali insights →
      </a>
    </div>
  );
}
