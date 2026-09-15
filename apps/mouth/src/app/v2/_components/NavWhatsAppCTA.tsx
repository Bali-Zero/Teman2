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
 * the filled treatment is reserved for the page's single primary.
 * Default "accent" keeps existing consumers (e.g. /v2) byte-identical.
 *
 * R19 uses a copper outline on the navy masthead. Its light hover switches
 * to dark ink so the label keeps AA contrast; the href/UTM payload is
 * untouched.
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
            ? "#EAE3D8"
            : "transparent"
          : "var(--accent-funnel)",
        color: isWhatsApp
          ? hovered
            ? "#1D2C3B"
            : "#F7F4EE"
          : "var(--text-on-accent)",
        border: isWhatsApp ? "1px solid #A44B36" : undefined,
        textDecoration: "none",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: isWhatsApp ? "#A44B36" : "#25D366",
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
