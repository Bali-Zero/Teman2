"use client";

import { Phone } from "lucide-react";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import { getCopy } from "@/lib/secondhome-studio/copy";
import { readiness } from "@/lib/secondhome-studio/checklist";
import { encodePlanFragment } from "@/lib/secondhome-studio/plan-codec";
import type { PlanState, Verdict } from "@/lib/secondhome-studio/types";

const STUDIO_PATH = "/visa/second-home/studio";

function optionLabel(base: string, value: string | null): string {
  if (value === null) return "—";
  if (value === "not_applicable") return "Not applicable";
  return getCopy(`${base}.options.${value}`);
}

function familySummary(plan: PlanState): string {
  const parts: string[] = [];
  if (plan.family.spouse) parts.push("spouse");
  if (plan.family.children > 0) parts.push("children");
  if (plan.family.parents > 0) parts.push("parents");
  return parts.length > 0 ? parts.join(", ") : "none";
}

export interface WhatsAppHandoffProps {
  plan: PlanState;
  verdict: Verdict;
}

/**
 * Reuses the landing's WhatsAppLeadButton pattern verbatim (spec §5): the
 * tracked-capture-then-wa.me-deeplink handoff, with the same
 * never-block-the-user fallback. `WhatsAppLeadButton` takes a structured
 * `whatsappContext` (label/value bullets) — not a free-text message prop
 * — so the copy deck's `whatsapp.prefillTemplate` field structure
 * (ageBand/route/funding/property/family/timeline/location/verdict) is
 * mirrored here as bullets, in the same order, plus readiness + the saved
 * plan link (spec §5 asks for both explicitly; the template itself has no
 * placeholder for either).
 */
export function WhatsAppHandoff({ plan, verdict }: WhatsAppHandoffProps) {
  const bandLabel = getCopy(`verdict.bands.${verdict.band}.heading`);
  const { done, total } = readiness(plan);

  const planUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}${STUDIO_PATH}#p=${encodePlanFragment(plan)}`
      : `${STUDIO_PATH}#p=${encodePlanFragment(plan)}`;

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
        whatsappContext={[
          { label: "Age band", value: optionLabel("wizard.age", plan.age) },
          {
            label: "Route considered",
            value: optionLabel("wizard.route", plan.route),
          },
          {
            label: "Funding position",
            value: optionLabel("wizard.seniorFunding", plan.seniorFunding),
          },
          {
            label: "Property position",
            value: optionLabel("wizard.property", plan.property),
          },
          { label: "Family members", value: familySummary(plan) },
          {
            label: "Preferred timing",
            value: optionLabel("wizard.horizon", plan.horizon),
          },
          {
            label: "Current location",
            value: optionLabel("wizard.location", plan.location),
          },
          { label: "Fit-check result", value: bandLabel },
          { label: "Readiness", value: `${done} of ${total} prepared` },
          { label: "Saved plan", value: planUrl },
        ]}
        utm={{ page: STUDIO_PATH }}
        resultHash={verdict.band}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "var(--space-3, 0.85rem) var(--space-5, 1.5rem)",
          borderRadius: 8,
          background: "#25D366",
          color: "#fff",
          fontWeight: 600,
          textDecoration: "none",
          minHeight: 44,
        }}
      >
        <Phone size={18} aria-hidden />
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
