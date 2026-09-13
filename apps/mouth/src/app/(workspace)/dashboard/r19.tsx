"use client";

/**
 * R19 presentation primitives for the kita dashboard's Portal Champion widget.
 *
 * Copied idiom, not a second visual system — same primitives, class strings
 * and token reads as apps/mouth/src/app/portal/(authenticated)/page.tsx
 * (concept-F) and apps/mouth/src/app/(workspace)/garuda-voa/r19.tsx (PR
 * #6411), page-local so nothing shared is restyled. See garuda-voa/r19.tsx
 * for the fuller doc block this one intentionally does not repeat.
 *
 * FOUR COLOUR MEANINGS, one vocabulary, read from the theme layer:
 *   done / healthy  -> --state-success
 *   ours / moving   -> --state-info
 *   needs you       -> --bz-copper / --bz-copper-text
 *   waiting         -> --tx-secondary
 *
 * NO RED ON THIS WIDGET. --state-danger is never read here — the challenge
 * has no failure state worth alarming over, only "not yet" (wait) and "you're
 * close" (you, copper). r19.test.tsx fails if a danger read or a hardcoded
 * hex comes back in this widget's own files.
 */

import React from "react";
import { cn } from "@/lib/utils";

/** Fraunces, scoped to this widget only (see r19-fonts import in the widget). */
export const SERIF: React.CSSProperties = {
  fontFamily: "var(--font-serif)",
  fontWeight: 450,
};

export const EYEBROW =
  "text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--tx-secondary)]";
export const SECTION_H2 = "text-[24px] leading-[1.14] tracking-[-0.02em]";
export const HAIRLINE = "border border-[var(--bz-border)]";
export const CARD = `rounded-lg bg-[var(--bz-surface)] ${HAIRLINE}`;
export const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

export type PillTone = "ok" | "ours" | "you" | "wait";

export const PILL_TONE: Record<PillTone, string> = {
  ok: "text-[var(--state-success)] border-[var(--state-success)]",
  ours: "text-[var(--state-info)] border-[var(--state-info)]",
  you: "text-[var(--bz-copper-text)] border-[var(--bz-copper)]",
  wait: "text-[var(--tx-secondary)] border-[var(--bz-border-hover)]",
};

/** Outlined status pill — one vocabulary, four meanings, never a filled state. */
export function StatePill({
  tone,
  label,
  className,
}: {
  tone: PillTone;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-[7px] whitespace-nowrap rounded-full border px-[10px] text-[10px] font-semibold uppercase tracking-[0.12em]",
        PILL_TONE[tone],
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full bg-current"
      />
      {label}
    </span>
  );
}

/** Copper rule + Fraunces headline, the R19 masthead idiom. */
export function Masthead({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
}) {
  return (
    <div>
      <div
        aria-hidden="true"
        className="mb-3 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
      />
      {eyebrow && <p className={cn(EYEBROW, "mb-2")}>{eyebrow}</p>}
      <h2 className={cn(SECTION_H2, "text-[var(--tx-pure)]")} style={SERIF}>
        {title}
      </h2>
      {subtitle && (
        <p className="mt-1.5 text-[13px] text-[var(--tx-secondary)]">
          {subtitle}
        </p>
      )}
    </div>
  );
}

/** Copper progress bar with threshold markers — used for "to next tier". */
export function ProgressBar({
  value,
  max,
  markers,
  toneClassName,
}: {
  value: number;
  max: number;
  markers?: number[];
  toneClassName?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--bz-border)]"
    >
      <div
        className={cn(
          "h-full rounded-full bg-[var(--bz-copper)] transition-[width] duration-700 ease-out motion-reduce:transition-none",
          toneClassName,
        )}
        style={{ width: `${pct}%` }}
      />
      {markers?.map((m) => {
        const markerPct = max > 0 ? Math.min(100, (m / max) * 100) : 0;
        return (
          <span
            key={m}
            aria-hidden="true"
            className="absolute top-0 h-full w-px bg-[var(--bz-base)]/60"
            style={{ left: `${markerPct}%` }}
          />
        );
      })}
    </div>
  );
}
