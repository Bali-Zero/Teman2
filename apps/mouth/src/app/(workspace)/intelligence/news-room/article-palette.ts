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
 * All palettes are taken from the original set — no new colors introduced.
 */
export interface ArticlePalette {
  bg: string;
  border: string;
  glow: string;
  accent: string;
  gradient: string;
}

export const NEUTRAL_PALETTE: ArticlePalette = {
  bg: "rgba(212,132,90,0.12)",
  border: "rgba(212,132,90,0.25)",
  glow: "rgba(212,132,90,0.15)",
  accent: "#d4845a",
  gradient:
    "linear-gradient(145deg, rgba(212,132,90,0.18) 0%, rgba(180,100,60,0.06) 100%)",
};

export const CRITICAL_PALETTE: ArticlePalette = {
  bg: "rgba(244,63,94,0.12)",
  border: "rgba(244,63,94,0.25)",
  glow: "rgba(244,63,94,0.15)",
  accent: "#fb7185",
  gradient:
    "linear-gradient(145deg, rgba(244,63,94,0.18) 0%, rgba(190,18,60,0.06) 100%)",
};

export const NEW_PALETTE: ArticlePalette = {
  bg: "rgba(99,102,241,0.12)",
  border: "rgba(99,102,241,0.25)",
  glow: "rgba(99,102,241,0.15)",
  accent: "#818cf8",
  gradient:
    "linear-gradient(145deg, rgba(99,102,241,0.18) 0%, rgba(67,56,202,0.06) 100%)",
};

export const UPDATED_PALETTE: ArticlePalette = {
  bg: "rgba(14,165,233,0.12)",
  border: "rgba(14,165,233,0.25)",
  glow: "rgba(14,165,233,0.15)",
  accent: "#38bdf8",
  gradient:
    "linear-gradient(145deg, rgba(14,165,233,0.18) 0%, rgba(2,132,199,0.06) 100%)",
};

export function getArticlePalette(
  item: Pick<StagingItem, "is_critical" | "detection_type">,
): ArticlePalette {
  if (item.is_critical) return CRITICAL_PALETTE;
  if (item.detection_type === "NEW") return NEW_PALETTE;
  if (item.detection_type === "UPDATED") return UPDATED_PALETTE;
  return NEUTRAL_PALETTE;
}
