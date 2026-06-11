"use client";

import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const gtag: ((...args: any[]) => void) | undefined;

export function InlineNewsCTA() {
  const href = buildWhatsAppLink("home");

  const handleClick = () => {
    if (typeof gtag !== "undefined") {
      gtag("event", "home_whatsapp_cta", {
        funnel: "home",
        placement: "news_grid_inline",
      });
    }
    void trackFunnelEvent("home_whatsapp_cta", {
      sessionId: getOrCreateSessionId(),
      payload: { trigger: "news_inline" },
    });
  };

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={handleClick}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1rem",
        padding: "1.25rem 1.5rem",
        borderRadius: "1rem",
        background:
          "linear-gradient(135deg, color-mix(in srgb, #25D366 10%, transparent) 0%, rgba(255,255,255,0.02) 100%)",
        border: "1px solid color-mix(in srgb, #25D366 28%, transparent)",
        textDecoration: "none",
      }}
    >
      <div>
        <p
          style={{
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            color: "#25D366",
            marginBottom: 4,
          }}
        >
          Free Consultation
        </p>
        <p
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "var(--text-primary)",
            lineHeight: 1.3,
            marginBottom: 4,
          }}
        >
          Not sure where to start? Talk to our team directly.
        </p>
        <p style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
          Visa · Company · Tax · Property — one conversation.
        </p>
      </div>
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "0.55rem 1.1rem",
          borderRadius: "0.7rem",
          background: "#25D366",
          color: "#fff",
          fontSize: 13,
          fontWeight: 600,
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        WhatsApp Us →
      </span>
    </a>
  );
}
