"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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

function familySummary(plan: PlanState): { text: string; isKnown: boolean } {
  const parts: string[] = [];
  if (plan.family.spouse) parts.push("Spouse");
  if (plan.family.children > 0) parts.push("Children");
  if (plan.family.parents > 0) parts.push("Parents");
  return parts.length > 0
    ? { text: parts.join(", "), isKnown: true }
    : { text: "—", isKnown: false };
}

interface RowItem {
  id: string;
  label: string;
  value: string;
  isKnown: boolean;
}

function buildRows(plan: PlanState): RowItem[] {
  const family = familySummary(plan);
  const rows: RowItem[] = [
    {
      id: "age",
      label: "Age",
      value: optionLabel("wizard.age", plan.age),
      isKnown: plan.age !== null,
    },
    {
      id: "route",
      label: "Route",
      value: optionLabel("wizard.route", plan.route),
      isKnown: plan.route !== null,
    },
  ];

  if (plan.route === "property") {
    rows.push({
      id: "property",
      label: "Property",
      value: optionLabel("wizard.property", plan.property),
      isKnown: plan.property !== null,
    });
  } else {
    rows.push({
      id: "capital",
      label: "Capital",
      value: optionLabel("wizard.capital", plan.capital),
      isKnown: plan.capital !== null,
    });
  }

  if (plan.age !== null && plan.age !== "under_55") {
    rows.push({
      id: "seniorFunding",
      label: "Senior funding",
      value: optionLabel("wizard.seniorFunding", plan.seniorFunding),
      isKnown: plan.seniorFunding !== null,
    });
  }

  rows.push(
    {
      id: "family",
      label: "Family",
      value: family.text,
      isKnown: family.isKnown,
    },
    {
      id: "horizon",
      label: "Timeline",
      value: optionLabel("wizard.horizon", plan.horizon),
      isKnown: plan.horizon !== null,
    },
    {
      id: "location",
      label: "Location",
      value: optionLabel("wizard.location", plan.location),
      isKnown: plan.location !== null,
    },
  );

  return rows;
}

function Row({
  label,
  value,
  isKnown,
  isNew,
  testId,
}: {
  label: string;
  value: string;
  isKnown: boolean;
  isNew: boolean;
  testId: string;
}) {
  return (
    <div
      data-testid={testId}
      data-known={isKnown}
      className={isNew ? "bz-shs-memo-row-enter" : undefined}
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "var(--space-2, 0.5rem)",
        fontSize: "var(--text-sm, 0.85rem)",
      }}
    >
      <dt style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>
        {label}
      </dt>
      <dd
        style={{
          margin: 0,
          textAlign: "right",
          color: isKnown ? "var(--text-primary)" : "var(--color-text-muted)",
          fontWeight: isKnown ? 500 : 300,
          opacity: isKnown ? 1 : 0.55,
          fontStyle: isKnown ? "normal" : "italic",
        }}
      >
        {value}
      </dd>
    </div>
  );
}

/** P2-5: on desktop the rail is a STATIC summary (the `.bz-shs-memo`
 *  CSS below neutralises pointer-events on the toggle), but a native
 *  `<summary>` remains keyboard-focusable and Enter/Space still fires the
 *  browser's default toggle — so a keyboard/AT user could focus an
 *  element with no visible affordance and have it silently collapse the
 *  panel. Detects the same `(min-width: 900px)` breakpoint the CSS below
 *  keys off, and when true removes the summary from the tab order
 *  (`tabIndex={-1}`) and hides it from the accessibility tree
 *  (`aria-hidden`) — mobile keeps the full native collapsible behavior
 *  unchanged. Guarded against `window.matchMedia` being absent (jsdom by
 *  default has no `matchMedia`) so this can never throw or change
 *  behavior for any test that doesn't explicitly stub it — it silently
 *  stays in the "mobile/interactive" default. */
function useIsDesktopStatic(): boolean {
  const [isDesktopStatic, setIsDesktopStatic] = useState(false);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      typeof window.matchMedia !== "function"
    ) {
      return;
    }
    const mq = window.matchMedia("(min-width: 900px)");
    const update = () => setIsDesktopStatic(mq.matches);
    update();
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", update);
      return () => mq.removeEventListener("change", update);
    }
    return undefined;
  }, []);

  return isDesktopStatic;
}

/** Live-filling summary of the plan-in-progress. Desktop: static right
 *  rail (P2-5: non-interactive — no focusable/keyboard-togglable toggle).
 *  Mobile: a native collapsible (spec §4 "collapsible on mobile") —
 *  implemented as one <details> whose disclosure toggle is neutralised via
 *  CSS at desktop widths rather than duplicating markup per breakpoint.
 *
 *  P2-5b: rows enter with a short fade-and-rise when they first become
 *  known; a thin left spine grows with the answered rows to read as a
 *  receipt filling in. `prefers-reduced-motion: reduce` disables all
 *  movement. */
export function MemoPreview({ plan }: MemoPreviewProps) {
  const isDesktopStatic = useIsDesktopStatic();
  const rows = useMemo(() => buildRows(plan), [plan]);

  // Track which rows have already been seen with a known value so only
  // freshly-known rows animate. We deliberately do NOT remove ids when a
  // row becomes unknown again (user goes back and clears an answer); if it
  // later becomes known again we treat it as an update, not a birth, which
  // matches the product brief: "in that case the row updates, it is not
  // born". The initial mount is excluded from animation so mounting with
  // a partially-filled plan does not flash every row at once.
  const seenRowsRef = useRef<Set<string>>(new Set());
  const isInitialMountRef = useRef(true);

  const newRowIds = useMemo(() => {
    if (isInitialMountRef.current) return new Set<string>();
    const ids = new Set<string>();
    for (const row of rows) {
      if (row.isKnown && !seenRowsRef.current.has(row.id)) {
        ids.add(row.id);
      }
    }
    return ids;
  }, [rows]);

  useEffect(() => {
    for (const row of rows) {
      if (row.isKnown) seenRowsRef.current.add(row.id);
    }
    isInitialMountRef.current = false;
  }, [rows]);

  const knownCount = rows.filter((r) => r.isKnown).length;
  const spineProgress = rows.length > 0 ? (knownCount / rows.length) * 100 : 0;

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
        tabIndex={isDesktopStatic ? -1 : undefined}
        aria-hidden={isDesktopStatic ? true : undefined}
        style={{
          cursor: "pointer",
          // R4 §3 24px floor: --text-sm resolves to 0.875rem (14px,
          // packages/core/tokens/primitives.css) — well below the
          // display-only floor either way (0.9rem fallback is 14.4px) — so
          // this disclosure summary uses the UI/body face at Inter 600
          // instead, per R4 §3's own remedy ("smaller headings are Inter
          // 600"). Size/hierarchy unchanged — only the face and weight move.
          fontFamily: "var(--font-sans, ui-sans-serif, system-ui, sans-serif)",
          fontSize: "var(--text-sm, 0.9rem)",
          fontWeight: 600,
          color: "var(--text-primary)",
        }}
      >
        Your plan so far
      </summary>
      <div
        style={{
          position: "relative",
          marginTop: "var(--space-2, 0.5rem)",
          paddingLeft: "var(--space-3, 1rem)",
        }}
      >
        <div
          aria-hidden="true"
          className="bz-shs-memo-spine"
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: 2,
            height: `${spineProgress}%`,
            background: "var(--color-border-subtle)",
            borderRadius: 1,
          }}
        />
        <dl
          style={{
            display: "grid",
            gap: "var(--space-2, 0.5rem)",
            margin: 0,
          }}
        >
          {rows.map((row) => (
            <Row
              key={row.id}
              testId={`memo-row-${row.id}`}
              label={row.label}
              value={row.value}
              isKnown={row.isKnown}
              isNew={newRowIds.has(row.id)}
            />
          ))}
        </dl>
      </div>
      <style>{`
        @keyframes bz-shs-memo-row-enter {
          from {
            opacity: 0;
            transform: translateY(-4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .bz-shs-memo-row-enter {
          animation: bz-shs-memo-row-enter 180ms ease-out forwards;
        }
        .bz-shs-memo-spine {
          transition: height 180ms ease-out;
        }
        @media (min-width: 900px) {
          .bz-shs-memo > summary {
            pointer-events: none;
            list-style: none;
          }
          .bz-shs-memo > summary::-webkit-details-marker {
            display: none;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .bz-shs-memo-row-enter {
            animation: none !important;
          }
          .bz-shs-memo-spine {
            transition: none !important;
          }
        }
      `}</style>
    </details>
  );
}
