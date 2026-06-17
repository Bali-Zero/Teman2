"use client";

import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";

export function InlineNewsCTA() {
  return (
    <WhatsAppLeadButton
      source="article"
      context={{ section: "inline_news_cta", page: "home" }}
      whatsappContext={[
        { label: "Source", value: "Homepage Inline CTA" },
        { label: "Section", value: "Latest News" },
      ]}
      utm={{ page: "/" }}
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
    </WhatsAppLeadButton>
  );
}
