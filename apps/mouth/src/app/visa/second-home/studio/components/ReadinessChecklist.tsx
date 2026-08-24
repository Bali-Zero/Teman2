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

/** Two-column layout at width (2026-08-25): this list was 815px tall in a
 *  single column with short rows, burning 22% of the verdict-stage page on
 *  a page already leaving width unused above the mobile breakpoint.
 *
 *  A row-paired CSS Grid (`grid-template-columns: repeat(2, ...)`) was
 *  tried first and measured WORSE than it looks on paper: pairing item N
 *  with item N+1 into one row forces that row to the height of whichever
 *  of the two wraps its "why" text onto 2 lines — halving the column width
 *  makes MORE items wrap, so a naive "10 rows -> 5 rows" expectation
 *  measured only ~750px, not ~500px, because most rows still paid the
 *  2-line-item price. CSS multi-column (`columns: 2`) does not have this
 *  problem: the browser balances TOTAL content height across the two
 *  columns (short items packing next to tall ones) instead of pairing
 *  items positionally, and `break-inside: avoid` on each `<li>` stops a
 *  single item's checkbox/title from separating from its own why-text
 *  across the column break. Measured: ~707px (grid pairing) -> ~430px
 *  (balanced columns) for the same 10-item content.
 *
 *  DOM/tab order is untouched by either approach (both keep the plain
 *  source order of the `<li>` elements) — `columns` reflows them
 *  top-to-bottom in column 1 before column 2, the same sequential,
 *  newspaper-style order CSS multi-column exists for, so a keyboard user
 *  tabbing through still traverses the group in one coherent pass. Each
 *  group (`ChecklistGroup`) gets its OWN `<ul>`/column context — never one
 *  spanning both `<ul>`s — so the two route-classification groups
 *  ("Applies to your answers" / "May also apply") can never interleave:
 *  group 1's own columns finish completely before group 2 starts,
 *  whatever count each group holds. 760px matches RouteComparator's
 *  existing single-column collapse point in this same verdict stage (see
 *  RouteComparator's `@media (max-width: 760px)`), kept here as
 *  `min-width` for the inverse direction. `@media print` is forced back to
 *  one column: CustodyMap's 2026-08-24 print fix documents why —
 *  `@media (min-width)` tests the *viewport*, not the printed page, so a
 *  print engine can't be trusted to also collapse this on its own. */
const checklistListClassName = "bz-shs-checklist-list";

const checklistListResponsiveStyles = `
  .${checklistListClassName} {
    grid-template-columns: minmax(0, 1fr);
  }
  @media (min-width: 760px) {
    .${checklistListClassName} {
      display: block !important;
      columns: 2;
      column-gap: var(--space-4, 1.5rem);
    }
    .${checklistListClassName} > li {
      break-inside: avoid;
      margin: 0 0 var(--space-2, 0.5rem);
    }
  }
  @media print {
    .${checklistListClassName} {
      display: grid !important;
      grid-template-columns: minmax(0, 1fr) !important;
      columns: auto !important;
    }
    .${checklistListClassName} > li {
      margin: 0 !important;
    }
  }
`;

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
      <ul style={listStyle} className={checklistListClassName}>
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
      <style>{checklistListResponsiveStyles}</style>
    </section>
  );
}
