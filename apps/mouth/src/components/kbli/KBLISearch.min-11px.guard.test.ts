import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli search dropdown carried three 10px labels: the PMA status chip
 * and the risk chip under every result, and the footer ("N KBLI codes
 * found" / keyboard hint). Floor is 11px, the same floor as the
 * /kbli-explorer series (#7960, #7972, #8011).
 *
 * Declared limits: reads KBLISearch.tsx as text and checks arbitrary
 * `text-[Npx]` classes only. It does not render and does not check colour
 * contrast.
 */
const SRC = readFileSync(join(__dirname, "KBLISearch.tsx"), "utf8");
const SIZE = /(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g;

describe("/kbli search dropdown has no text below 11px", () => {
  it("positive control: the scan reaches the result chips and the footer", () => {
    expect(SRC).toContain("apiPmaStatusLabel(result)");
    expect(SRC).toContain("KBLI codes found");
    expect([...SRC.matchAll(SIZE)].length).toBeGreaterThanOrEqual(3);
  });

  it("no arbitrary text size below 11px", () => {
    const hits = [...SRC.matchAll(SIZE)]
      .filter((m) => Number(m[1]) < 11)
      .map((m) => m[0]);
    expect(hits).toEqual([]);
  });
});
