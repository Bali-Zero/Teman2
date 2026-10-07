import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * ComparisonModal (dialog on #0A0C10) and ThinkingIndicator (chat panel on
 * the page's dark surfaces) rendered secondary text in #444, #555 and #666:
 * 1.81-3.41:1 against #0A0C10 / #0f1115 / #151921, below WCAG AA 4.5:1.
 * Measured at 0e6d48a. They now use #888 (4.97-5.52:1 on the same three
 * backgrounds), the muted grey page.tsx already uses 22 times.
 *
 * Declared limits: reads the two files as text and checks arbitrary
 * `text-[#3xx-#6xx]` greys only. It does not render, does not compute
 * contrast at runtime, and does not cover page.tsx.
 */
const FILES = ["ComparisonModal.tsx", "ThinkingIndicator.tsx"].map((f) => ({
  f,
  src: readFileSync(join(__dirname, f), "utf8"),
}));
const DARK_GREY = /(?<![\w-])text-\[#[3-6][0-9a-fA-F]{2}\]/g;

describe("ComparisonModal and ThinkingIndicator text meets AA on dark", () => {
  it("positive control: both files are read and carry arbitrary text colours", () => {
    for (const { f, src } of FILES) {
      expect(
        src.match(/text-\[#[0-9a-fA-F]{3,6}\]/g)?.length ?? 0,
        f,
      ).toBeGreaterThan(0);
    }
    expect(FILES[0].src).toContain("Field");
    expect(FILES[1].src).toContain("activeStage");
  });

  it("no #3xx-#6xx grey text", () => {
    const hits = FILES.flatMap(({ f, src }) =>
      [...src.matchAll(DARK_GREY)].map((m) => `${f}: ${m[0]}`),
    );
    expect(hits).toEqual([]);
  });
});
