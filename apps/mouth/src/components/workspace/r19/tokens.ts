/**
 * R19 "TEPAT FORTE" shared constants for the kita workspace (SAETTA-R19K /
 * K1c-bis, v2 of the K1b "SIAP" module).
 *
 * v1's values were copied from the frozen concept-K renders. v2's new/changed
 * values below are copied from the frozen fusion render
 * `R19-KITA-20260914/fusion/02-dashboard.html` and `03-clients-list.html`
 * (search the `<style>` block for "TEPAT FORTE fusion layer") — geometry from
 * their `html{}` block, class strings from their stylesheet. Nothing is
 * invented; a deviation needs a reason in the window's pack.
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
/** v2 name for `SIDEBAR_W` — the invariant rail width. Same value, own doc line. */
export const RAIL_W = SIDEBAR_W;
export const GUTTER = 24;
/** Below this width the two lowest-priority columns leave the grid. */
export const COLLAPSE_PX = 1360;

/** Masthead h1: Fraunces opsz144 450 — 40/42 desktop, 32/34 under 768. */
export const MASTHEAD_H1 =
  "text-[32px] leading-[1.05] tracking-[-0.035em] text-[var(--tx-pure)] md:text-[40px]";

/** The masthead sentence: Manrope 15/1.55 on a 62ch measure. */
export const MASTHEAD_SUB =
  "mt-[3px] max-w-[62ch] text-[15px] leading-[1.55] text-[var(--tx-secondary)]";

/** KPI numeral — 44/44, 38 under 768. The viewport peak. */
export const NUMERAL_KPI =
  "text-[38px] leading-none tracking-[-0.03em] md:text-[44px]";
/** Desk count — 22/22. */
export const NUMERAL_COUNT = "text-[22px] leading-none tracking-[-0.02em]";
/** Ledger ordinal — 18/18. */
export const NUMERAL_ORDINAL = "text-[18px] leading-none tracking-[-0.02em]";

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

/**
 * The selected FILTER: v2 fills it INK with paper text (v1 filled it slate,
 * `bg-[var(--state-info)] border-[var(--state-info)] text-[var(--bz-on-warm)]`
 * — the fusion render's selected pill is the same ink fill as `PILL_TONE.ink`,
 * so a filter reads as "chosen" the same way a filled status reads as
 * "resolved").
 */
export const PILL_SELECTED =
  "bg-[var(--tx-pure)] border-[var(--tx-pure)] text-[var(--bz-base)]";

/** The square pill: 2px radius. A kita pill is never a circle. */
export const PILL_SQUARE = "rounded-[2px]";

/** The ink 1px table-head rule. */
export const INK_HEAD_RULE = "border-b border-[var(--tx-pure)]";

/**
 * The 96x4 masthead rule (72 under 768) — the ONE place copper is allowed to
 * fill anything, because it fills a decorative graphic that carries no
 * label. It is a named constant so `r19.test.tsx` can allow exactly this use
 * and flag every other copper background as the law-breaking fill it would
 * be. `bg-[var(--bz-copper)]` MUST stay on this physical line for that
 * exemption to apply — see `findCopperFill` in the test file, which skips a
 * LINE carrying the identifier. The render draws a square rule, so v1's
 * `rounded-sm` is gone; dropping it is also what keeps the declaration inside
 * prettier's 80 columns, and therefore on one line, without a pragma.
 */
export const COPPER_RULE = "h-[4px] w-[72px] bg-[var(--bz-copper)] md:w-24";

/** Two-digit index for the copper numerals of the R19 list idiom. */
export const pad2 = (n: number) => String(n).padStart(2, "0");
