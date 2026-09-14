import type React from "react";

/**
 * The desk strip idiom, on concept-K "SIAP" / the frozen fusion.
 *
 * One vocabulary, shared by the four list primitives so a page cannot drift
 * from the alphabet a control at a time. Every value here is a TOKEN read, not
 * a colour: `packages/core` is imported by kita, my, prime and editorial, and
 * a hex written here would follow all four.
 *
 * The idiom, from the frozen renders: square corners (radius 0, the ledger is
 * printed not rounded), a 1px control boundary rather than a fill, 44px
 * controls so a thumb can hit them, Fraunces for counts because a number is a
 * fact and facts are set in the serif, and a SELECTED pill that is filled —
 * the one filled shape in the strip — carrying a ✓ so the state survives
 * greyscale and a screen reader.
 *
 * SELECTION COLOUR, and why it is written as a pair of fallbacks. The fusion
 * fills the pressed pill with slate. `--state-info` is that slate on paper and
 * a LIFTED slate in the dark, because in the dark it has to work as text — so
 * a filled pill reading `--state-info` needs its label to be the canvas, which
 * is ink on the light fill and paper on the dark one. That pair is correct
 * today under both themes. `--bz-selected-fill` / `--bz-on-selected` are the
 * seam hooks: when the K1c-bis seat declares them, the pill takes the fusion's
 * exact values without this file changing.
 */

/** Square by law: the ledger is printed, not rounded. */
export const DESK_RADIUS = "rounded-none";

/** A control a thumb can hit, and the height the renders measure. */
export const DESK_CONTROL_H = "h-11";

/** Counts and numerals are facts, and facts are set in the serif. */
export const DESK_SERIF: React.CSSProperties = {
  fontFamily: "var(--font-serif)",
  fontWeight: 450,
  fontVariantNumeric: "tabular-nums",
};

/** The strip's own rules: hairline above and below, nothing in between. */
export const DESK_STRIP =
  "border-y border-[var(--bz-border)] py-2 flex flex-col gap-2 sm:flex-row sm:items-center";

/** Every desk control sits on the control boundary, never on a fill. */
export const DESK_FIELD =
  "w-full h-11 rounded-none border border-[var(--line-control)] " +
  "bg-[var(--bz-card)] px-3 text-[13px] text-[var(--tx-pure)] " +
  "placeholder:text-[var(--tx-secondary)] focus:outline-none " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

/** An unpressed filter: outline, muted label, no ground of its own. */
export const DESK_PILL =
  "inline-flex h-11 items-center gap-1.5 rounded-none border " +
  "border-[var(--line-control)] bg-[var(--bz-card)] px-2.5 " +
  "text-[10px] font-[750] uppercase tracking-[0.08em] " +
  "text-[var(--tx-secondary)] transition-colors " +
  "hover:text-[var(--tx-pure)] focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

/**
 * A pressed filter: the one filled shape in the strip. The ✓ is not
 * decoration — `aria-pressed` tells a screen reader, the fill tells an eye,
 * and the tick tells an eye that cannot separate the two colours.
 */
export const DESK_PILL_ON =
  "inline-flex h-11 items-center gap-1.5 rounded-none border px-2.5 " +
  "text-[10px] font-[750] uppercase tracking-[0.08em] " +
  "border-[var(--bz-selected-fill,var(--state-info))] " +
  "bg-[var(--bz-selected-fill,var(--state-info))] " +
  "text-[var(--bz-on-selected,var(--bz-base))] " +
  "focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-[var(--bz-copper)]";

/** The copper mark that opens a masthead. 52x3 in the frozen renders. */
export const DESK_RULE =
  "mb-3 h-[3px] w-[52px] rounded-none bg-[var(--bz-copper)]";
