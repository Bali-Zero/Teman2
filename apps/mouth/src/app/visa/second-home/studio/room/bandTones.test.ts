import { describe, expect, it } from "vitest";

import { R19_DIRECTION_A_VARS } from "@/lib/theme/r19Vars";
import { BAND_TONES, GLASS_TINT, ROOM_STATE_VARS } from "./bandTones";

const vars = R19_DIRECTION_A_VARS as Record<string, string>;
const PAPER = vars["--surface-base"];
const RAISED = vars["--surface-raised"];
const COPPER = vars["--r19-copper"];

function channels(hex: string): number[] {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
/** The window glass: the tone at GLASS_TINT composited over paper. */
function glass(tone: string): string {
  const t = channels(tone);
  const p = channels(PAPER);
  return (
    "#" +
    t
      .map((c, i) => Math.round(c * GLASS_TINT + p[i] * (1 - GLASS_TINT)))
      .map((c) => c.toString(16).padStart(2, "0"))
      .join("")
  );
}

describe("verdict window tones (R19, computed — BRIEF-v2 §3.2: ≥4.5 on paper)", () => {
  it.each(Object.entries(BAND_TONES))(
    "%s %s is text-legal on paper, raised and its own glass",
    (_band, tone) => {
      expect(contrast(tone, PAPER)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tone, RAISED)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tone, glass(tone))).toBeGreaterThanOrEqual(4.5);
      // Body text inside the window stays ink.
      expect(
        contrast(vars["--text-primary"], glass(tone)),
      ).toBeGreaterThanOrEqual(7);
    },
  );

  it("four bands, four distinct tones — and none of them is the action copper", () => {
    const tones = Object.values(BAND_TONES).map((t) => t.toLowerCase());
    expect(new Set(tones).size).toBe(4);
    expect(tones).not.toContain(COPPER.toLowerCase());
  });

  it.each(Object.entries(ROOM_STATE_VARS))(
    "room state token %s %s clears 4.5 on paper",
    (_name, value) => {
      expect(contrast(value, PAPER)).toBeGreaterThanOrEqual(4.5);
    },
  );
});
