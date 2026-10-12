import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * page.tsx still carried eleven 10px labels after the left panel moved to
 * 11px (#7960): the hero sub-label, "Ask about your codes", the sector
 * heading, filter and card chips, and — inside InspectorChoreographed, the
 * inspector visitors actually see — the section eyebrow, step numbers, the
 * license SLA chip and "What you need to do:". Measured at 0e6d48a.
 * Floor is 11px, the same floor as #7960 and #7972.
 *
 * Declared limits: reads page.tsx as text and checks arbitrary `text-[Npx]`
 * classes only. It does not render and does not check colour contrast.
 */
const SRC = readFileSync(join(__dirname, "page.tsx"), "utf8");
const SIZE = /(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g;

describe("/kbli-explorer page.tsx has no text below 11px", () => {
  it("positive control: the scan reaches the rendered inspector", () => {
    expect(SRC).toContain("const InspectorChoreographed");
    expect(SRC).toContain("What you need to do:");
    expect([...SRC.matchAll(SIZE)].length).toBeGreaterThanOrEqual(11);
  });

  it("no arbitrary text size below 11px", () => {
    const hits = [...SRC.matchAll(SIZE)]
      .filter((m) => Number(m[1]) < 11)
      .map((m) => m[0]);
    expect(hits).toEqual([]);
  });
});
