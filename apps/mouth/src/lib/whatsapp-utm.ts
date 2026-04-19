/**
 * WhatsApp deep-link builder with UTM tracking for SEO attribution.
 *
 * All WA CTAs across balizero.com MUST go through this helper so the
 * landing_page on the WhatsApp side carries proper attribution that
 * the CRM lead_intake can parse into lead_source=whatsapp_inbound.
 *
 * Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
 * Plan: docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md Task 5
 */

const WA_NUMBER = "628213107363";

export type Funnel = "home" | "visa" | "kbli" | "tax" | "property";

const FUNNEL_GREETINGS: Record<Funnel, string> = {
  home: "Hi Bali Zero, I would like to get started.",
  visa: "Hi Bali Zero, I have a question about visa or KITAS.",
  kbli: "Hi Bali Zero, I want to set up a PT PMA / business in Indonesia.",
  tax: "Hi Bali Zero, I have a question about Indonesian tax.",
  property: "Hi Bali Zero, I want help with property due diligence in Bali.",
};

export function buildWhatsAppLink(
  funnel: string,
  customGreeting?: string,
): string {
  const safe: Funnel = (funnel in FUNNEL_GREETINGS ? funnel : "home") as Funnel;
  const greeting = customGreeting || FUNNEL_GREETINGS[safe];

  const params = new URLSearchParams({
    text: greeting,
    utm_source: "balizero_web",
    utm_medium: "whatsapp_cta",
    utm_campaign: safe,
  });

  return `https://wa.me/${WA_NUMBER}?${params.toString()}`;
}
