"use client";

import { Building2, Landmark, User } from "lucide-react";
import { getCopy } from "@/lib/secondhome-studio/copy";
import { buildTimeline } from "@/lib/secondhome-studio/timeline";
import type {
  Location,
  RouteIntent,
  TimelineHorizon,
  Verdict,
} from "@/lib/secondhome-studio/types";

const OWNER_ICONS = {
  you: User,
  balizero: Building2,
  imigrasi: Landmark,
} as const;

export interface TimelineViewProps {
  horizon: TimelineHorizon;
  location: Location;
  /** P1-C9 (optional, defaults preserve the original always-bank-deposit
   *  second step): route/product make the second step honest about what
   *  the applicant actually needs to do — property never had a bank
   *  deposit, E33F is explicitly "without the deposit". */
  route?: RouteIntent | null;
  product?: Verdict["product"];
}

/** Renders buildTimeline()'s 7 public steps — each with a heading, body
 *  (range label), and an owner chip (You / Bali Zero / Imigrasi). Every
 *  range is "typical, not a promise" per copy.ts — no promised dates. */
export function TimelineView({
  horizon,
  location,
  route = null,
  product = null,
}: TimelineViewProps) {
  const steps = buildTimeline(horizon, location, route, product);

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
        Your typical timeline
      </h2>
      <ol
        style={{
          margin: 0,
          padding: 0,
          listStyle: "none",
          display: "grid",
          gap: "var(--space-3, 1rem)",
        }}
      >
        {steps.map((step) => (
          <li
            key={step.id}
            style={{
              display: "grid",
              gap: "var(--space-1, 0.3rem)",
              paddingBottom: "var(--space-2, 0.5rem)",
              borderBottom: "1px dashed var(--color-border-subtle)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "var(--space-2, 0.5rem)",
              }}
            >
              <strong style={{ color: "var(--text-primary)" }}>
                {getCopy(step.titleKey)}
              </strong>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "var(--space-1, 0.3rem)",
                  fontSize: "0.68rem",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  padding: "2px 8px",
                  borderRadius: 999,
                  border: "1px solid var(--color-border-subtle)",
                  color: "var(--color-text-muted)",
                  whiteSpace: "nowrap",
                }}
              >
                {(() => {
                  const OwnerIcon = OWNER_ICONS[step.ownerKey];
                  return OwnerIcon ? (
                    <OwnerIcon
                      size={12}
                      strokeWidth={1.5}
                      aria-hidden
                      style={{ flexShrink: 0 }}
                    />
                  ) : null;
                })()}
                {getCopy(`timeline.ownerLabels.${step.ownerKey}`)}
              </span>
            </div>
            <p
              style={{
                margin: 0,
                color: "var(--color-text-muted)",
                fontSize: "var(--text-sm, 0.88rem)",
              }}
            >
              {getCopy(step.rangeKey)}
            </p>
            {step.paceNoteKey ? (
              <p
                style={{
                  margin: 0,
                  fontSize: "var(--text-sm, 0.85rem)",
                  fontStyle: "italic",
                  color: "var(--text-primary)",
                }}
              >
                {getCopy(step.paceNoteKey)}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
