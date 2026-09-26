import type { VerdictBand } from "@/lib/secondhome-studio/types";

/**
 * The verdict window's light — one tone per FROZEN band (types.ts), mapped
 * into R19 Direction A. The bands' meaning and order are unchanged; only the
 * hue moves from the shared `--state-*` tokens (which R19_DIRECTION_A_VARS
 * does not restate, so on this paper they kept the editorial theme's values)
 * to four values drawn from the R19 family:
 *
 *   strong_fit   #2F5E45  forest, the R19 base canopy's green family
 *   likely_fit   #233D52  R19 structure slate (entry.css:320)
 *   edge_case    #8A5410  ochre — a caution that is not copper, because
 *                         copper is the page's single ACTION colour (R-1/Q4)
 *   not_eligible #58626B  R19 muted ink (entry.css:322)
 *
 * Every tone is TEXT-legal (≥4.5:1) on paper #F7F4EE, on raised #FFFCF7 and
 * on its own window glass (the tone at GLASS_TINT over paper) — recomputed
 * by `bandTones.test.ts`, never trusted from this comment.
 */
export const BAND_TONES: Record<VerdictBand, string> = {
  strong_fit: "#2F5E45",
  likely_fit: "#233D52",
  edge_case: "#8A5410",
  not_eligible: "#58626B",
};

/** Share of the tone in the window glass (mixed toward transparent over paper). */
export const GLASS_TINT = 0.08;

export function glassBackground(band: VerdictBand): string {
  return `color-mix(in srgb, ${BAND_TONES[band]} ${Math.round(GLASS_TINT * 100)}%, transparent)`;
}

/**
 * State tokens the Studio's older components read (ScenarioToggle,
 * RouteComparator, SavePlanBar) and that R19_DIRECTION_A_VARS does not
 * restate — found by the alias guard in
 * scripts/tests/test_merah_putih_day_contrast.py. Without a restatement on
 * the room wrapper they fall back to the shared theme's :root value. The
 * three state hues reuse the band tones (one caution, one info, one success
 * in the whole room); the error red keeps its day-set value, #A83A44, the
 * one tone the R19 family has no member for.
 */
export const ROOM_STATE_VARS = {
  "--state-success": BAND_TONES.strong_fit,
  "--state-info": BAND_TONES.likely_fit,
  "--state-warning": BAND_TONES.edge_case,
  "--state-danger": "#A83A44",
  "--color-error": "#A83A44",
} as const;
