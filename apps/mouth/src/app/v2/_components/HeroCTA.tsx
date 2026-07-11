"use client";

import { ArrowRight } from "lucide-react";
import { trackHeroCTA } from "@/lib/analytics";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";

/**
 * HeroCTA — Client Component wrapper for hero section CTA links.
 *
 * Extracted from HeroBlueprint (Server Component) to keep the parent
 * zero-JS while enabling onClick analytics.
 *
 * MYTHOS B2 (P2 single-primary): the WhatsApp chat CTA is THE one red
 * primary action of the homepage (`--cta-primary-bg`, class `cta-primary`
 * pinned by e2e). Wording and visual treatment are Subhi's #1205/#1216
 * surface — do not change behavior. The secondary is a ghost button
 * (white-on-photo here; navy-ghost on light surfaces).
 *
 * 2026-07-06: primary CTA migrated to WhatsAppLeadButton — the 6th
 * consumer of the shared lead-capture pattern (article, kbli_navigator,
 * zantara_widget_handoff, cta_handoff, pricing_modal + hero). POSTs
 * /api/lead/capture (writes lead_intents row) before handing off to
 * WhatsApp, so homepage traffic is captured in the same funnel as the
 * other 5 surfaces instead of a bare untracked wa.me link.
 *
 * source="homepage_hero" is NOT YET in the backend LeadSource enum
 * (apps/backend-rag/backend/services/lead_capture/source.py) — needs
 * Antonello to add it. Until then /api/lead/capture will reject the
 * source and WhatsAppLeadButton's built-in catch falls back to the bare
 * wa.me link automatically (captured=false tracked), so this ships safe
 * today with zero user-facing risk — lead capture just activates the
 * moment the enum value lands on the backend.
 *
 * Behavior change vs. previous version: navigates in the SAME tab (no
 * target="_blank") — WhatsAppLeadButton doesn't support a target prop,
 * matching the other 5 consumers. Flagging explicitly since it's a
 * visible UX change on the homepage's single primary CTA.
 *
 * hero_cta_book_call is retired in favor of the unified lead_whatsapp_cta
 * event (fired inside WhatsAppLeadButton). hero_cta_read_dispatch stays
 * for the secondary (non-WhatsApp) CTA.
 * Events registered in packages/core/analytics/funnel-view.ts:
 *   - lead_whatsapp_cta (existing, shared across all 6 consumers)
 *   - hero_cta_read_dispatch
 */
export function HeroCTA() {
  return (
    <div className="flex items-center gap-4 md:gap-6 mb-6 md:mb-10 flex-wrap">
      <WhatsAppLeadButton
        source="homepage_hero"
        context={{ section: "hero", page: "home" }}
        whatsappContext={[{ label: "Source", value: "Homepage Hero" }]}
        utm={{ page: "/" }}
        fallbackHref={buildWhatsAppLink("home")}
        className="cta-primary inline-flex items-center gap-2 px-6 py-3 rounded-md text-[15px] font-semibold transition-transform hover:-translate-y-0.5"
        style={{
          background: "var(--cta-primary-bg)",
          color: "var(--cta-primary-fg)",
          boxShadow: "0 6px 18px rgba(255,45,76,0.3)",
        }}
      >
        Chat with us — avg reply: 2 min
        <ArrowRight size={15} strokeWidth={2.2} />
      </WhatsAppLeadButton>
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
