"use client";

/**
 * R19 presentation primitives for the GARUDA VOA staff console.
 *
 * SAETTA-VOA W-VOA-V3 (2026-09-13): G0.4 ruled R19 for this console
 * (docs/plans/2026-09-03-relaunch-lanes/ZERO-DECISIONS.md:19). These are the
 * same primitives, class strings and token reads the concept-F pass shipped on
 * the client portal (apps/mouth/src/app/portal/(authenticated)/page.tsx and
 * components/portal/StatusBadge.tsx) — copied idiom, not a second visual
 * system, and page-local so nothing shared is restyled.
 *
 * FOUR COLOUR MEANINGS, one vocabulary, read from the theme layer:
 *   done / healthy  -> --state-success
 *   ours / moving   -> --state-info
 *   needs you       -> --bz-copper / --bz-copper-text
 *   waiting         -> --tx-secondary
 *
 * NO RED ON THIS SURFACE. --state-danger resolves to #b91c1c on the kita
 * daylight theme, so concept-F's re-alias is applied here instead: every state
 * that used to read danger now reads copper AND carries the word ("Blocked",
 * "Rejected"). r19.test.tsx fails if a danger read comes back.
 *
 * Value caveat, recorded rather than fixed. The R19 hues (forest #253E33,
 * slate #233D52, copper #A44B36) are declared in globals.css under
 * [data-product="my"] only. On kita the same TOKENS resolve to the daylight
 * AA steps. Giving kita the R19 values is a theme-layer change and belongs to
 * a window whose perimeter includes the whole workspace, not to this one.
 */

import React from "react";
import { cn } from "@/lib/utils";
import type { PracticeState } from "./types";

/** Fraunces, scoped to this console by layout.tsx (nothing global is swapped). */
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
export const FIELD =
  "w-full rounded border border-[var(--bz-border-hover)] bg-[var(--bz-base)] px-3 py-2.5 text-sm text-[var(--tx-pure)] placeholder:text-[var(--tx-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

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

/**
 * The seven practice states of the frozen contract, as four meanings and seven
 * WORDS. Blocked and Rejected are the two that used to read danger: they keep
 * their word and take the copper "needs you" step.
 */
export const PRACTICE_TONE: Record<PracticeState, PillTone> = {
  Received: "wait",
  "In review": "ours",
  Blocked: "you",
  Submitted: "ours",
  Approved: "ok",
  Rejected: "you",
  Delivered: "ok",
};

export function PracticeStatePill({
  state,
  className,
}: {
  state: PracticeState;
  className?: string;
}) {
  return (
    <StatePill
      tone={PRACTICE_TONE[state] ?? "wait"}
      label={state}
      className={className}
    />
  );
}

/** Copper rule + Fraunces headline + the existing subtitle copy. */
export function Masthead({
  eyebrow,
  title,
  subtitle,
  headingClassName,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  headingClassName?: string;
}) {
  return (
    <section>
      <div
        aria-hidden="true"
        className="mb-4 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
      />
      {eyebrow && <p className={cn(EYEBROW, "mb-2")}>{eyebrow}</p>}
      <h1
        className={cn(
          "text-[clamp(28px,3.4vw,40px)] leading-[1.06] tracking-[-0.03em] text-[var(--tx-pure)]",
          headingClassName,
        )}
        style={SERIF}
      >
        {title}
      </h1>
      {subtitle && (
        <p className="mt-2 text-[var(--tx-secondary)]">{subtitle}</p>
      )}
    </section>
  );
}

/**
 * A quiet notice. `tone="you"` is the ONLY alarming variant this console has —
 * copper text on a copper hairline plus the words the caller passes, never a
 * filled red row.
 */
export function Notice({
  children,
  role,
}: {
  children: React.ReactNode;
  role?: "alert" | "status";
}) {
  return (
    <div
      role={role}
      className="rounded-lg border border-[var(--bz-copper)] bg-[var(--bz-surface)] px-4 py-3 text-sm text-[var(--bz-copper-text)]"
    >
      {children}
    </div>
  );
}

/** Two-digit index for the copper numerals of the R19 list idiom. */
export const pad2 = (n: number) => String(n).padStart(2, "0");
