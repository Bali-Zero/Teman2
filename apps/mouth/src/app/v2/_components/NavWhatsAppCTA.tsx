"use client";

import { useState } from "react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

/**
 * Nav "Get Started via WhatsApp" CTA — #1216 tracking island
 * (home_whatsapp_cta, trigger: nav).
 *
 * MYTHOS B2 (P2): `variant="whatsapp"` is the navy-masthead style, where
 * red is reserved for the page's single primary.
 * Default "accent" keeps existing consumers (e.g. /v2) byte-identical.
 *
 * 2026-08-28 brand-accent pass: the fill was WhatsApp's own brand green
 * (#25D366). That is the CHANNEL's colour, not Bali Zero's — on a navy
 * masthead it read like a bolted-on chat widget and out-competed the hero
 * for attention. Repainted to brand gold #D4A017 with navy ink (4.91:1 —
 * AA). Hover LIGHTENS to #E0AE28 (5.69:1) rather than the darker #B8890F
 * that was first proposed: #B8890F drops navy ink to 3.68:1, i.e. the label
 * would fail AA exactly while the pointer is on it. The href/UTM payload is
 * untouched — only paint changed.
 */
export function NavWhatsAppCTA({
  variant = "accent",
}: {
  variant?: "accent" | "whatsapp";
}) {
  const isWhatsApp = variant === "whatsapp";
  const [hovered, setHovered] = useState(false);
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
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-[13px] font-semibold uppercase tracking-wide transition-colors"
      style={{
        background: isWhatsApp
          ? hovered
            ? "#E0AE28"
            : "#D4A017"
          : "var(--accent-funnel)",
        color: isWhatsApp ? "#1E3863" : "var(--text-on-accent)",
        textDecoration: "none",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: isWhatsApp ? "#1E3863" : "#25D366",
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
            // Navy ink on gold is 4.91:1; dimming it to 0.85 lands near
            // 3.13:1, below AA. That figure is estimated from a flattened
            // blend, not alpha compositing. Hierarchy comes from size and
            // weight instead.
            opacity: isWhatsApp ? 1 : 0.85,
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
