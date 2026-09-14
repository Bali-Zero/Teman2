"use client";

/**
 * R19 presentation primitives for the kita dashboard's Portal Champion widget.
 *
 * Copied idiom, not a second visual system — same primitives, class strings
 * and token reads as apps/mouth/src/app/portal/(authenticated)/page.tsx
 * (concept-F) and apps/mouth/src/app/(workspace)/garuda-voa/r19.tsx (PR
 * #6411), page-local so nothing shared is restyled. See garuda-voa/r19.tsx
 * for the fuller doc block this one intentionally does not repeat. Only the
 * primitives this widget actually uses are kept here (no Masthead/
 * ProgressBar/SECTION_H2 — the hero band and the position scale need
 * custom markup PortalChallengeWidget.tsx owns directly).
 *
 * COLOUR MEANINGS actually used on THIS widget, read from the theme layer:
 *   needs you / mine -> --bz-copper / --bz-copper-text
 *   waiting          -> --tx-secondary
 *   solid ink chip   -> --tx-pure (fill) / --bz-surface (text) — for the
 *                       "Tax" badge, which the shared idiom would otherwise
 *                       give --state-info, which resolves to a BLUE on
 *                       kita's daylight theme — forbidden by brand. `ok`/
 *                       `ours` stay declared for idiom parity with
 *                       garuda-voa/r19.tsx but are never applied here:
 *                       --state-success resolves to a GREEN and --state-info
 *                       to a BLUE on kita (verified against globals.css's
 *                       kita daylight theme block; run token_lint.py or grep
 *                       the two token names there for the exact values —
 *                       never restate them as a literal here).
 *
 * NO RED ON THIS WIDGET. --state-danger is never read here. r19.test.tsx
 * fails if a danger read or a hardcoded hex comes back in this widget's own
 * files.
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
export const HAIRLINE = "border border-[var(--bz-border)]";
export const CARD = `rounded-lg bg-[var(--bz-surface)] ${HAIRLINE}`;
export const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

export type PillTone = "ok" | "ours" | "you" | "wait" | "ink";

export const PILL_TONE: Record<PillTone, string> = {
  ok: "text-[var(--state-success)] border-[var(--state-success)]",
  ours: "text-[var(--state-info)] border-[var(--state-info)]",
  you: "text-[var(--bz-copper-text)] border-[var(--bz-copper)]",
  wait: "text-[var(--tx-secondary)] border-[var(--bz-border-hover)]",
  // Solid ink chip (dark fill, paper text) — the brand-safe stand-in for a
  // second pill colour on kita, see the doc block above.
  ink: "text-[var(--bz-surface)] bg-[var(--tx-pure)] border-[var(--tx-pure)]",
};

/** Outlined status pill — one vocabulary, never a filled state except `ink`. */
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
