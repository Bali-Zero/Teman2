"use client";

import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

type HeaderFunnel = "visa" | "kbli" | "tax" | "property";

const EVENT_NAME = {
  visa: "visa_whatsapp_cta",
  kbli: "kbli_whatsapp_cta",
  tax: "tax_whatsapp_cta",
  property: "property_whatsapp_cta",
} as const;

/**
 * HeaderWhatsAppCTA — single source of truth for the WA button in the
 * NavShell actions slot across the 4 L1 funnels. Uses the semantic
 * --accent-funnel token so the editorial theme's funnel-specific accent
 * flows through (replaces the ad-hoc --bz-accent / --kbli-accent picks
 * in individual layouts).
 *
 * Fires trackFunnelEvent("<funnel>_whatsapp_cta") on click. Event name is
 * whitelisted in both frontend FUNNEL_EVENTS and backend ALLOWED_EVENTS.
 */
export function HeaderWhatsAppCTA({ funnel }: { funnel: HeaderFunnel }) {
  return (
    <a
      href="https://wa.me/628213107363"
      onClick={() =>
        void trackFunnelEvent(EVENT_NAME[funnel], {
          sessionId: getOrCreateSessionId(),
          payload: { trigger: "header" },
        })
      }
      className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold"
      style={{ background: "var(--accent-funnel)", color: "#fff" }}
    >
      WhatsApp
    </a>
  );
}
