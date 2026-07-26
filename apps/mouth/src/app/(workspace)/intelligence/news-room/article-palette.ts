import type { StagingItem } from "@/lib/api/intelligence.api";

/**
 * State-driven card accent palette (P1.5).
 *
 * The card accent used to be assigned by list index (modulo rainbow), so the
 * color carried no meaning and shifted as items were filtered/sorted. It is
 * now driven by article state:
 *
 *   critical  -> red    (urgent, mirrors the CRITICAL ribbon)
 *   NEW       -> blue   (fresh detection)
 *   UPDATED   -> cyan   (revision of known content)
 *   otherwise -> neutral terracotta (brand accent)
 *
 * WS2 kita slice 3 (2026-07-25): raw hex/rgba tuples drained to operative
 * tokens — critical reads --state-danger, NEW reads --state-info, neutral
 * reads --bz-accent (copper). UPDATED stays the documented sky one-off: no
 * token covers sky-400/500 (state-info is royal blue, neon-cyan is a
 * different hue family), and the 4-hue state encoding is deliberate
 * editorial identity. Tints are color-mix percentages of the token, so the
 * liquid-glass aesthetic survives the drain.
 */
export interface ArticlePalette {
  bg: string;
  border: string;
  glow: string;
  accent: string;
  /** 30% tint of accent — strong stop for the publish-button gradient. */
  accentSoft: string;
  gradient: string;
}

export const NEUTRAL_PALETTE: ArticlePalette = {
  bg: "color-mix(in srgb, var(--bz-accent) 12%, transparent)",
  border: "color-mix(in srgb, var(--bz-accent) 25%, transparent)",
  glow: "color-mix(in srgb, var(--bz-accent) 15%, transparent)",
  accent: "var(--bz-accent)",
  accentSoft: "color-mix(in srgb, var(--bz-accent) 30%, transparent)",
  gradient:
    "linear-gradient(145deg, color-mix(in srgb, var(--bz-accent) 18%, transparent) 0%, color-mix(in srgb, var(--bz-copper-deep) 6%, transparent) 100%)",
};

export const CRITICAL_PALETTE: ArticlePalette = {
  bg: "color-mix(in srgb, var(--state-danger) 12%, transparent)",
  border: "color-mix(in srgb, var(--state-danger) 25%, transparent)",
  glow: "color-mix(in srgb, var(--state-danger) 15%, transparent)",
  accent: "var(--state-danger)",
  accentSoft: "color-mix(in srgb, var(--state-danger) 30%, transparent)",
  gradient:
    "linear-gradient(145deg, color-mix(in srgb, var(--state-danger) 18%, transparent) 0%, color-mix(in srgb, var(--state-danger) 6%, transparent) 100%)",
};

export const NEW_PALETTE: ArticlePalette = {
  bg: "color-mix(in srgb, var(--state-info) 12%, transparent)",
  border: "color-mix(in srgb, var(--state-info) 25%, transparent)",
  glow: "color-mix(in srgb, var(--state-info) 15%, transparent)",
  accent: "var(--state-info)",
  accentSoft: "color-mix(in srgb, var(--state-info) 30%, transparent)",
  gradient:
    "linear-gradient(145deg, color-mix(in srgb, var(--state-info) 18%, transparent) 0%, color-mix(in srgb, var(--state-info) 6%, transparent) 100%)",
};

// Documented one-off (WS2 slice 3): sky identity for UPDATED — no operative
// token covers the sky hue; pinned by the intelligence drain-guard test.
export const UPDATED_PALETTE: ArticlePalette = {
  bg: "rgba(14,165,233,0.12)", // token-lint-ok: sky one-off, no token covers the hue
  border: "rgba(14,165,233,0.25)", // token-lint-ok: sky one-off, no token covers the hue
  glow: "rgba(14,165,233,0.15)", // token-lint-ok: sky one-off, no token covers the hue
  accent: "#38bdf8", // token-lint-ok: sky-400 one-off accent, no token covers the hue
  accentSoft: "rgba(14,165,233,0.3)", // token-lint-ok: sky one-off, no token covers the hue
  gradient:
    "linear-gradient(145deg, rgba(14,165,233,0.18) 0%, rgba(2,132,199,0.06) 100%)", // token-lint-ok: sky one-off gradient, no token covers the hue
};

export function getArticlePalette(
  item: Pick<StagingItem, "is_critical" | "detection_type">,
): ArticlePalette {
  if (item.is_critical) return CRITICAL_PALETTE;
  if (item.detection_type === "NEW") return NEW_PALETTE;
  if (item.detection_type === "UPDATED") return UPDATED_PALETTE;
  return NEUTRAL_PALETTE;
}
