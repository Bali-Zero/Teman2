"use client";

import type { FC } from "react";

export interface TimelineCheckpoint {
  label: string; // "D-60"
  at: string; // ISO date
  title: string;
  body: string;
  past?: boolean; // true when `at` < today
}

export interface AppResultTimelineProps {
  checkpoints: TimelineCheckpoint[];
  expiryDate: string; // ISO
}

/** 5-checkpoint timeline used by Visa Clock result page. */
export const AppResultTimeline: FC<AppResultTimelineProps> = ({
  checkpoints,
  expiryDate,
}) => {
  return (
    <ol
      aria-label={`Timeline until ${expiryDate}`}
      style={{
        listStyle: "none",
        padding: 0,
        margin: 0,
        display: "grid",
        gap: "var(--space-3)",
      }}
    >
      {checkpoints.map((c) => (
        <li
          key={c.label}
          style={{
            display: "grid",
            gridTemplateColumns: "64px minmax(0, 1fr)",
            gap: "var(--space-3)",
            padding: "var(--space-3)",
            borderLeft: `4px solid ${c.past ? "var(--color-border-subtle)" : "var(--bz-accent, #d4845a)"}`,
            background: c.past ? "transparent" : "var(--surface-raised)",
            opacity: c.past ? 0.55 : 1,
            borderRadius: 6,
          }}
        >
          <div>
            <strong
              style={{
                fontSize: "var(--text-md)",
                color: c.past
                  ? "var(--color-text-muted)"
                  : "var(--color-text-primary)",
              }}
            >
              {c.label}
            </strong>
            <div
              style={{
                fontSize: "var(--text-sm)",
                color: "var(--color-text-muted)",
              }}
            >
              {formatDate(c.at)}
            </div>
          </div>
          <div>
            <div style={{ fontWeight: 600 }}>{c.title}</div>
            <p
              style={{
                margin: 0,
                color: "var(--color-text-muted)",
                fontSize: "var(--text-sm)",
                lineHeight: 1.5,
              }}
            >
              {c.body}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
