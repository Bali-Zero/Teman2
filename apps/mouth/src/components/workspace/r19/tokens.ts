/**
 * R19 "SIAP" shared constants for the kita workspace (SAETTA-R19K / K1b).
 *
 * Every value here is copied from the frozen concept-K renders in
 * R19-KITA-20260914/concept/ — geometry from their `html{}` block, class
 * strings from their stylesheet. Nothing is invented; a deviation needs a
 * reason in the window's pack.
 *
 * These are STRINGS and numbers only, so this file stays importable from a
 * server component. The components live beside it.
 *
 * The tokens they read are listed in README.md. All of them are declared by
 * the kita theme blocks in app/globals.css; a surface that is not
 * `data-product="kita"` may leave some of them undefined.
 */

import type { CSSProperties } from "react";

/** Fraunces, 450, the only face that touches a masthead or a numeral. */
export const SERIF: CSSProperties = {
  fontFamily: "var(--font-serif)",
  fontWeight: 450,
  fontVariationSettings: '"opsz" 144',
};

/** Fraunces for a section heading — one optical size down. */
export const SERIF_SECTION: CSSProperties = {
  fontFamily: "var(--font-serif)",
  fontWeight: 450,
  fontVariationSettings: '"opsz" 96',
};

/** Tabular figures on every date, count, amount and reference. */
export const TABULAR: CSSProperties = { fontVariantNumeric: "tabular-nums" };

/** 10px/650/.14em uppercase. The concept's one label voice. */
export const EYEBROW =
  "text-[10px] font-[650] uppercase tracking-[0.14em] text-[var(--tx-secondary)]";

/** 9px/650/.16em — the sidebar section and the stamp. */
export const MICRO_LABEL =
  "text-[9px] font-[650] uppercase tracking-[0.16em] text-[var(--tx-secondary)]";

export const SECTION_H2 = "text-[20px] leading-[1.2] tracking-[-0.02em]";

/** A hairline, never a nested card. */
export const HAIRLINE = "border border-[var(--bz-border)]";

/** The one box shape kita still allows. The unit is the row, not this. */
export const CARD = "rounded-lg bg-[var(--bz-card)] " + HAIRLINE;

/** Copper focus ring, everywhere, so focus reads as one thing. */
export const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

/**
 * 52px field on a single control boundary, copper on focus — the login and
 * form idiom. `--line-control` exists because the hairline fails SC 1.4.11
 * under a control.
 */
export const FIELD =
  "w-full h-[52px] bg-transparent border-0 border-b border-[var(--line-control)] " +
  "px-0.5 text-sm text-[var(--tx-pure)] placeholder:text-[var(--tx-secondary)] " +
  "focus:outline-none focus:border-[var(--bz-copper)] focus:shadow-[0_1px_0_0_var(--bz-copper)] " +
  "disabled:opacity-50";

/** Geometry, from the renders' own `html{}` block. */
export const ROW_H = 44;
export const HEADER_H = 48;
export const SIDEBAR_W = 216;
export const GUTTER = 24;
/** Below this width the two lowest-priority columns leave the grid. */
export const COLLAPSE_PX = 1360;

/**
 * Five tones. The first four are the four meanings; `ink` is the filled tone
 * PR #6483's dashboard widget added, kept here so a later window adopts it
 * without a second file. Only `ink` and the `selected` filter variant are
 * ever filled — copper is never a fill.
 */
export type PillTone = "ok" | "ours" | "you" | "wait" | "ink";

export const PILL_TONE: Record<PillTone, string> = {
  ok: "text-[var(--state-success)] border-[var(--state-success)]",
  ours: "text-[var(--state-info)] border-[var(--state-info)]",
  you: "text-[var(--bz-copper-text)] border-[var(--bz-copper-text)]",
  wait: "text-[var(--tx-secondary)] border-[var(--line-control)]",
  ink: "text-[var(--bz-card)] bg-[var(--tx-pure)] border-[var(--tx-pure)]",
};

/** The selected FILTER: filled slate, because it is a choice, not a state. */
export const PILL_SELECTED =
  "bg-[var(--state-info)] border-[var(--state-info)] text-[var(--bz-on-warm)]";

/**
 * The 56x3 masthead rule — the ONE place copper is allowed to fill anything,
 * because it fills a decorative graphic that carries no label. It is a named
 * constant so `r19.test.tsx` can allow exactly this use and flag every other
 * copper background as the law-breaking fill it would be.
 */
export const COPPER_RULE = "h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]";

/** Two-digit index for the copper numerals of the R19 list idiom. */
export const pad2 = (n: number) => String(n).padStart(2, "0");
