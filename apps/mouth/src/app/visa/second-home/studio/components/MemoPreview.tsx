"use client";

import { getCopy } from "@/lib/secondhome-studio/copy";
import type { PlanState } from "@/lib/secondhome-studio/types";

export interface MemoPreviewProps {
  plan: PlanState;
}

/** Resolves a wizard option's label from copy.ts. "not_applicable" is a
 *  valid PlanState value (types.ts) with no wizard button / no copy entry
 *  (copy.ts's own comment: not user-selectable) — guarded here so a
 *  hand-edited fragment never surfaces a raw dot-path string. */
function optionLabel(base: string, value: string | null): string {
  if (value === null) return "—";
  if (value === "not_applicable") return "Not applicable";
  return getCopy(`${base}.options.${value}`);
}

function familySummary(plan: PlanState): string {
  const parts: string[] = [];
  if (plan.family.spouse) parts.push("Spouse");
  if (plan.family.children > 0) parts.push("Children");
  if (plan.family.parents > 0) parts.push("Parents");
  return parts.length > 0 ? parts.join(", ") : "—";
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "var(--space-2, 0.5rem)",
        fontSize: "var(--text-sm, 0.85rem)",
      }}
    >
      <dt style={{ color: "var(--color-text-muted)" }}>{label}</dt>
      <dd
        style={{ margin: 0, color: "var(--text-primary)", textAlign: "right" }}
      >
        {value}
      </dd>
    </div>
  );
}

/** Live-filling summary of the plan-in-progress. Desktop: static right
 *  rail. Mobile: a native collapsible (spec §4 "collapsible on mobile") —
 *  implemented as one <details> whose disclosure toggle is neutralised via
 *  CSS at desktop widths rather than duplicating markup per breakpoint. */
export function MemoPreview({ plan }: MemoPreviewProps) {
  return (
    <details
      className="bz-shs-memo"
      open
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-3, 1rem)",
      }}
    >
      <summary
        style={{
          cursor: "pointer",
          fontWeight: 600,
          fontSize: "var(--text-sm, 0.88rem)",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        Your plan so far
      </summary>
      <dl
        style={{
          display: "grid",
          gap: "var(--space-2, 0.5rem)",
          margin: "var(--space-2, 0.5rem) 0 0",
        }}
      >
        <Row label="Age" value={optionLabel("wizard.age", plan.age)} />
        <Row label="Route" value={optionLabel("wizard.route", plan.route)} />
        {plan.route === "property" ? (
          <Row
            label="Property"
            value={optionLabel("wizard.property", plan.property)}
          />
        ) : (
          <Row
            label="Capital"
            value={optionLabel("wizard.capital", plan.capital)}
          />
        )}
        {plan.age !== null && plan.age !== "under_55" ? (
          <Row
            label="Senior funding"
            value={optionLabel("wizard.seniorFunding", plan.seniorFunding)}
          />
        ) : null}
        <Row label="Family" value={familySummary(plan)} />
        <Row
          label="Timeline"
          value={optionLabel("wizard.horizon", plan.horizon)}
        />
        <Row
          label="Location"
          value={optionLabel("wizard.location", plan.location)}
        />
      </dl>
      <style>{`
        @media (min-width: 900px) {
          .bz-shs-memo > summary {
            pointer-events: none;
            list-style: none;
          }
          .bz-shs-memo > summary::-webkit-details-marker {
            display: none;
          }
        }
      `}</style>
    </details>
  );
}
