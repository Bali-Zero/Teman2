import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Two rendered /kbli-explorer components carried 10px text: the RiskGauge
 * level label under the gauge ("Medium-High", "Not Classified", …) and both
 * header cells of the ComparisonModal table. Measured at afd8fc5.
 * Floor is 11px, the same floor kita labels use.
 *
 * Declared limits: reads the two files as text and checks arbitrary
 * `text-[Npx]` classes only. It does not render. MatchScoreRing (number
 * inside a 40px ring) is deliberately out of scope.
 */
const FILES = ["RiskGauge.tsx", "ComparisonModal.tsx"].map((f) => ({
  f,
  src: readFileSync(join(__dirname, f), "utf8"),
}));
const SIZE = /(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g;

describe("RiskGauge and ComparisonModal have no text below 11px", () => {
  it("positive control: both files are read and carry size classes", () => {
    for (const { f, src } of FILES) {
      expect([...src.matchAll(SIZE)].length, f).toBeGreaterThan(0);
    }
    expect(FILES[0].src).toContain("{label}");
    expect(FILES[1].src).toContain("Field");
  });

  it("no arbitrary text size below 11px", () => {
    const hits = FILES.flatMap(({ f, src }) =>
      [...src.matchAll(SIZE)]
        .filter((m) => Number(m[1]) < 11)
        .map((m) => `${f}: ${m[0]}`),
    );
    expect(hits).toEqual([]);
  });
});
