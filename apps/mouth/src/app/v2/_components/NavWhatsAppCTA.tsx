"use client";

import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

export function NavWhatsAppCTA() {
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
      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-[13px] font-semibold uppercase tracking-wide"
      style={{
        background: "var(--accent-funnel)",
        color: "var(--text-on-accent)",
        textDecoration: "none",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: "#25D366",
          boxShadow: "0 0 6px #25D366",
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
