"use client";

import {
  CHECKLIST_ITEMS,
  classifyChecklistItem,
  readiness,
  type ChecklistItem,
} from "@/lib/secondhome-studio/checklist";
import { getCopy } from "@/lib/secondhome-studio/copy";
import type { PlanState, Verdict } from "@/lib/secondhome-studio/types";

export interface ReadinessChecklistProps {
  plan: PlanState;
  verdict: Verdict;
  onToggle: (id: string) => void;
}

const groupHeadingStyle = {
  margin: "0 0 var(--space-2, 0.5rem)",
  fontSize: "var(--text-sm, 0.9rem)",
  fontWeight: 600,
  color: "var(--text-primary)",
} as const;

const mutedSmallStyle = {
  margin: 0,
  fontSize: "var(--text-sm, 0.82rem)",
  color: "var(--color-text-muted)",
} as const;

const listStyle = {
  margin: 0,
  padding: 0,
  listStyle: "none",
  display: "grid",
  gap: "var(--space-2, 0.5rem)",
} as const;

/** One route-classification group ("Applies to your answers" / "May also
 *  apply") — renders nothing when empty (the applicable group is never
 *  empty in practice; the may_apply group can be, e.g. an unresolved
 *  route). Every item stays a real, tickable checkbox in whichever group
 *  it lands in — nothing here is disabled or read-only. */
function ChecklistGroup({
  headingKey,
  noteKey,
  items,
  plan,
  onToggle,
}: {
  headingKey: string;
  noteKey?: string;
  items: ChecklistItem[];
  plan: PlanState;
  onToggle: (id: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 style={groupHeadingStyle}>{getCopy(headingKey)}</h3>
      {noteKey ? <p style={mutedSmallStyle}>{getCopy(noteKey)}</p> : null}
      <ul style={listStyle}>
        {items.map((item) => (
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
    </div>
  );
}

/** 10-item readiness checklist bound to plan.checklist. Checkboxes only —
 *  no uploads. Every item stays visible regardless of route (this is a
 *  readiness list, not a final application checklist — copy.ts's
 *  `checklist.body` says so), but items are grouped by whether THIS plan's
 *  answers apply to them (`classifyChecklistItem`, fail-safe toward
 *  "applies" whenever the route is unconfirmed). The meter counts only the
 *  applicable group, so "X of Y prepared" is always honestly reachable —
 *  never "approval likelihood" (spec §5 hard rule; copy.ts's own
 *  readiness.caption reinforces it). */
export function ReadinessChecklist({
  plan,
  verdict,
  onToggle,
}: ReadinessChecklistProps) {
  const { done, total } = readiness(plan, verdict);

  const applicableItems: ChecklistItem[] = [];
  const mayApplyItems: ChecklistItem[] = [];
  for (const item of CHECKLIST_ITEMS) {
    const group =
      classifyChecklistItem(item.id, plan, verdict) === "applies"
        ? applicableItems
        : mayApplyItems;
    group.push(item);
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
          // R4 §3: Cormorant is display-only and never below 24px.
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.5rem, 3vw, 1.75rem)",
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
        <p style={mutedSmallStyle}>{getCopy("checklist.readiness.caption")}</p>
      </div>

      <ChecklistGroup
        headingKey="checklist.groups.applicableHeading"
        items={applicableItems}
        plan={plan}
        onToggle={onToggle}
      />
      <ChecklistGroup
        headingKey="checklist.groups.mayApplyHeading"
        noteKey="checklist.groups.mayApplyNote"
        items={mayApplyItems}
        plan={plan}
        onToggle={onToggle}
      />

      <p style={mutedSmallStyle}>{getCopy("checklist.note")}</p>
    </section>
  );
}
