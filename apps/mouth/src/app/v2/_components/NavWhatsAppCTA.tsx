"use client";

import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

/**
 * Nav "Get Started via WhatsApp" CTA — #1216 tracking island
 * (home_whatsapp_cta, trigger: nav).
 *
 * MYTHOS B2 (P2): `variant="whatsapp"` renders the channel-green style
 * (--accent-whatsapp + dark text, 7.5:1 on #25D366 — AA) for the navy
 * masthead, where red is reserved for the page's single primary.
 * Default "accent" keeps existing consumers (e.g. /v2) byte-identical.
 */
export function NavWhatsAppCTA({
  variant = "accent",
}: {
  variant?: "accent" | "whatsapp";
}) {
  const isWhatsApp = variant === "whatsapp";
  return (
    <a
      href={buildWhatsAppLink("home")}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() =>
        void trackFunnelEvent("home_whatsapp_cta", {
          sessionId: getOrCreateSessionId(),
          payload: { trigger: "nav" },
        })
      }
      className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
      style={{
        background: isWhatsApp
          ? "var(--accent-whatsapp, #25d366)"
          : "var(--accent-funnel)",
        color: isWhatsApp ? "#06301a" : "var(--text-on-accent)",
        textDecoration: "none",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: isWhatsApp ? "#06301a" : "#25D366",
          boxShadow: isWhatsApp ? "none" : "0 0 6px #25D366",
          flexShrink: 0,
        }}
      />
      <span
        style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}
      >
        <span>Get Started</span>
        <span
          style={{
            fontSize: 8,
            fontWeight: 500,
            opacity: 0.85,
            textTransform: "lowercase",
            letterSpacing: "0.04em",
          }}
        >
          via WhatsApp
        </span>
      </span>
    </a>
  );
}
