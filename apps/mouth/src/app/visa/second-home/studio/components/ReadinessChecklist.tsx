"use client";

import { CHECKLIST_ITEMS, readiness } from "@/lib/secondhome-studio/checklist";
import { getCopy } from "@/lib/secondhome-studio/copy";
import type { PlanState } from "@/lib/secondhome-studio/types";

export interface ReadinessChecklistProps {
  plan: PlanState;
  onToggle: (id: string) => void;
}

/** 10-item readiness checklist bound to plan.checklist. Checkboxes only —
 *  no uploads. The meter says "prepared", never "approval likelihood"
 *  (spec §5 hard rule; copy.ts's own readiness.caption reinforces it). */
export function ReadinessChecklist({
  plan,
  onToggle,
}: ReadinessChecklistProps) {
  const { done, total } = readiness(plan);

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
          fontSize: "clamp(1.2rem, 3vw, 1.5rem)",
          color: "var(--text-primary)",
        }}
      >
        {getCopy("checklist.heading")}
      </h2>
      <p style={{ margin: 0, color: "var(--text-primary)", lineHeight: 1.6 }}>
        {getCopy("checklist.body")}
      </p>
      <div>
        <p style={{ margin: 0, fontWeight: 600, color: "var(--text-primary)" }}>
          {done} of {total} {getCopy("checklist.readiness.preparedLabel")}
        </p>
        <p
          style={{
            margin: 0,
            fontSize: "var(--text-sm, 0.82rem)",
            color: "var(--color-text-muted)",
          }}
        >
          {getCopy("checklist.readiness.caption")}
        </p>
      </div>
      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: "none",
          display: "grid",
          gap: "var(--space-2, 0.5rem)",
        }}
      >
        {CHECKLIST_ITEMS.map((item) => (
          <li key={item.id}>
            <label
              style={{
                display: "flex",
                gap: "var(--space-2, 0.5rem)",
                alignItems: "flex-start",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={Boolean(plan.checklist[item.id])}
                onChange={() => onToggle(item.id)}
                style={{ marginTop: 4, minWidth: 18, minHeight: 18 }}
              />
              <span>
                <span
                  style={{ display: "block", color: "var(--text-primary)" }}
                >
                  {getCopy(item.titleKey)}
                </span>
                <span
                  style={{
                    display: "block",
                    fontSize: "var(--text-sm, 0.85rem)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {getCopy(item.whyKey)}
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.82rem)",
          color: "var(--color-text-muted)",
        }}
      >
        {getCopy("checklist.note")}
      </p>
    </section>
  );
}
