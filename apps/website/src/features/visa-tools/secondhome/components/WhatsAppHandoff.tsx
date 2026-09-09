"use client";

import { Phone } from "lucide-react";
import { WhatsAppLeadButton } from "../support";
import { getCopy } from "../engine/copy";
import { buildWhatsAppBullets } from "../engine/whatsapp-bullets";
import type { PlanState, Verdict } from "../engine/types";

const STUDIO_PATH = "/visa/second-home/studio";

export interface WhatsAppHandoffProps {
  plan: PlanState;
  verdict: Verdict;
}

export function WhatsAppHandoff({ plan, verdict }: WhatsAppHandoffProps) {
  const bullets = buildWhatsAppBullets(plan, verdict);

  return (
    <section
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
        textAlign: "center",
        justifyItems: "center",
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.85rem)",
          color: "var(--color-text-muted)",
          maxWidth: "34rem",
        }}
      >
        {getCopy("whatsapp.privacy")}
      </p>
      <WhatsAppLeadButton
        source="cta_handoff"
        context={{
          page: STUDIO_PATH,
          product: "e33_second_home_studio",
          service_interest: "second_home",
        }}
        whatsappContext={bullets}
        utm={{ page: STUDIO_PATH }}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "var(--space-3, 0.85rem) var(--space-5, 1.5rem)",
          borderRadius: 12,
          background: "var(--surface-raised)",
          border: "1px solid var(--border-strong)",
          color: "var(--text-primary)",
          fontWeight: 600,
          textDecoration: "none",
          minHeight: 44,
        }}
      >
        <Phone size={18} aria-hidden color="var(--accent-whatsapp, #25d366)" />
        {getCopy("whatsapp.button")}
      </WhatsAppLeadButton>
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.8rem)",
          color: "var(--color-text-muted)",
        }}
      >
        {getCopy("whatsapp.note")}
      </p>
    </section>
  );
}
