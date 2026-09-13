"use client";

import { Phone } from "lucide-react";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import { getCopy } from "@/lib/secondhome-studio/copy";
import { buildWhatsAppBullets } from "@/lib/secondhome-studio/whatsapp-bullets";
import type { PlanState, Verdict } from "@/lib/secondhome-studio/types";

const STUDIO_PATH = "/visa/second-home/studio";

export interface WhatsAppHandoffProps {
  plan: PlanState;
  verdict: Verdict;
}

/**
 * Reuses the landing's WhatsAppLeadButton pattern verbatim (spec §5): the
 * tracked-capture-then-wa.me-deeplink handoff, with the same
 * never-block-the-user fallback.
 *
 * P0-C3 + P0-C4 (backend contract verified in-worktree against
 * `apps/backend-rag/backend/app/routers/lead_capture.py:38-47`):
 * `whatsappContext` carries EXACTLY the <=6 branch-aware bullets built by
 * `buildWhatsAppBullets` (lib/secondhome-studio/whatsapp-bullets.ts) — no
 * plan URL, no readiness row, and no `resultHash` is passed at all (the
 * `cta_handoff` LeadSource's `result_url_path` is "/", so a `resultHash`
 * would build a garbage "Reference: https://balizero.com//<band>" line —
 * `whatsapp_deeplink.py:88-89`). The plan link's ONLY carrier is
 * SavePlanBar's "Copy plan link" (P0-C3(e)).
 */
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
          // R4 identity spec (research/design/2026-08-27-r4-identity-
          // merah-putih-token-spec.md §3/§4): WhatsApp is the ICON of the
          // human exit, never a text surface — not even at a passing
          // ratio. The 2026-08-24 fix below answered a different question
          // ("what ink passes AA on a green button?") and its
          // #0d3a1f-on-#25D366 ~6.45:1 does pass, but the spec names
          // ink-on-green explicitly and rejects it anyway: it breaks the
          // platform's mental model (a solid-green pill reads as the
          // WhatsApp app icon). The cure that survives is the SHAPE —
          // elevated card, border-input boundary, green confined to the
          // icon, ink label — which is the card-with-icon component the
          // spec's token table names (this call site's card already had
          // the outer <section>; this is the button ITSELF adopting the
          // same pattern). Green-on-surface-raised now measures ~1.98:1,
          // which is EXPECTED and spec-sanctioned ("icon-only"): the
          // adjacent text label carries the meaning independently, so
          // WCAG 1.4.11's "graphical object required to understand
          // content" does not apply to this icon.
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
