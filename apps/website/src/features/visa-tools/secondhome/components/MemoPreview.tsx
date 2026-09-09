"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getCopy } from "../engine/copy";
import type { PlanState } from "../engine/types";

export interface MemoPreviewProps {
  plan: PlanState;
}

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

export function MemoPreview({ plan }: MemoPreviewProps) {
  const isDesktopStatic = useIsDesktopStatic();
  const rows = useMemo(() => buildRows(plan), [plan]);
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
