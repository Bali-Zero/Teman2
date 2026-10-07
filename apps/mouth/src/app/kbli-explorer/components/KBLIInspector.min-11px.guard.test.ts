import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli-explorer inspector panel carried seven 10px labels: the three
 * "2026 Business Intelligence" card headings, the "2025 Transition" note,
 * the license SLA chip, the "What you need to do:" label and the grouped
 * requirement headings. Measured at 0e6d48a. Floor is 11px, the same floor
 * the left panel (#7960), RiskGauge and ComparisonModal (#7972) moved to.
 *
 * Declared limits: reads the file as text and checks arbitrary `text-[Npx]`
 * classes only. It does not render, and it does not check colour contrast.
 */
const SRC = readFileSync(join(__dirname, "KBLIInspector.tsx"), "utf8");
const SIZE = /(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g;

describe("KBLIInspector has no text below 11px", () => {
  it("positive control: the file is read and carries size classes", () => {
    expect([...SRC.matchAll(SIZE)].length).toBeGreaterThan(0);
    expect(SRC).toContain("What you need to do:");
  });

  it("no arbitrary text size below 11px", () => {
    const hits = [...SRC.matchAll(SIZE)]
      .filter((m) => Number(m[1]) < 11)
      .map((m) => m[0]);
    expect(hits).toEqual([]);
  });
});
