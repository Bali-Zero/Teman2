"use client";

import { useState } from "react";
import { getCopy } from "@/lib/secondhome-studio/copy";
import {
  encodePlanFragment,
  savePlan,
} from "@/lib/secondhome-studio/plan-codec";
import { relevantPlan } from "@/lib/secondhome-studio/sequence";
import type { PlanState } from "@/lib/secondhome-studio/types";

const STUDIO_PATH = "/visa/second-home/studio";

export interface SavePlanBarProps {
  plan: PlanState;
  /** Clears localStorage (plan-codec's clearPlan) and resets the wizard to
   *  a fresh plan — owned by StudioApp so the reset also rewinds the step
   *  index. */
  onClear: () => void;
}

const buttonStyle: React.CSSProperties = {
  padding: "var(--space-2, 0.5rem) var(--space-4, 1.1rem)",
  borderRadius: 8,
  border: "1px solid var(--color-border-subtle)",
  background: "transparent",
  color: "var(--text-primary)",
  cursor: "pointer",
  minHeight: 44,
  fontSize: "0.9rem",
  fontFamily: "inherit",
};

/** "Your plan stays on this device" bar (spec §5). Answers auto-save on
 *  every change (StudioApp calls plan-codec's savePlan after each answer)
 *  — the explicit "Save on this device" button here is a reassurance
 *  affordance, not the only save path.
 *
 *  P0-C3(e): this is the ONLY carrier of the shareable plan link — the
 *  WhatsApp handoff no longer transports one. P2-6: the copied link is
 *  built from `relevantPlan(plan)`, not the raw plan, so an
 *  abandoned-branch answer (e.g. a leftover `capital` value after
 *  switching to the property route) never leaks into a shared link. */
export function SavePlanBar({ plan, onClear }: SavePlanBarProps) {
  const [savedFeedback, setSavedFeedback] = useState(false);
  const [copiedFeedback, setCopiedFeedback] = useState(false);

  function handleSave() {
    savePlan(plan);
    setSavedFeedback(true);
    window.setTimeout(() => setSavedFeedback(false), 2500);
  }

  async function handleCopyLink() {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}${STUDIO_PATH}#p=${encodePlanFragment(relevantPlan(plan))}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedFeedback(true);
      window.setTimeout(() => setCopiedFeedback(false), 2500);
    } catch {
      // Clipboard blocked (permissions/private mode) — silent no-op; the
      // user can still select the link text manually if we ever render it.
    }
  }

  return (
    <section
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
      }}
    >
      <h2
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.1rem, 2.6vw, 1.35rem)",
          color: "var(--text-primary)",
        }}
      >
        {getCopy("savePlanBar.heading")}
      </h2>
      <p style={{ margin: 0, color: "var(--text-primary)", lineHeight: 1.6 }}>
        {getCopy("savePlanBar.body")}
      </p>
      <div
        style={{
          display: "flex",
          gap: "var(--space-2, 0.5rem)",
          flexWrap: "wrap",
        }}
      >
        <button type="button" onClick={handleSave} style={buttonStyle}>
          {getCopy("savePlanBar.saveButton")}
        </button>
        <button type="button" onClick={handleCopyLink} style={buttonStyle}>
          {getCopy("savePlanBar.copyLinkButton")}
        </button>
        <button
          type="button"
          onClick={onClear}
          style={{
            ...buttonStyle,
            borderColor: "var(--color-error, #c0392b)",
            color: "var(--color-error, #c0392b)",
          }}
        >
          {getCopy("savePlanBar.clearButton")}
        </button>
      </div>
      <div role="status" aria-live="polite" style={{ minHeight: "1.2em" }}>
        {savedFeedback ? (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--text-primary)",
            }}
          >
            {getCopy("savePlanBar.savedConfirmation")}
          </p>
        ) : null}
        {copiedFeedback ? (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--text-primary)",
            }}
          >
            {getCopy("savePlanBar.copiedConfirmation")}
          </p>
        ) : null}
      </div>
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.8rem)",
          color: "var(--color-text-muted)",
        }}
      >
        {getCopy("savePlanBar.linkWarning")}
      </p>
    </section>
  );
}
