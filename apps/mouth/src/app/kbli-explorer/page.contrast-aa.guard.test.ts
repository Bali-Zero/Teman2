import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * page.tsx rendered secondary text in #333, #444, #555 and #666 on the
 * route's dark grounds (#050507, #0A0C10, #0f1115, #151921, #1a1d24):
 * 1.33-3.55:1, below WCAG AA 4.5:1. Measured at 59d24e63c, 25 occurrences.
 * They now use #888 (4.76-5.74:1 on the same five grounds), the muted grey
 * page.tsx already used 13 times and ComparisonModal/ThinkingIndicator
 * adopted in #8014. The two buttons whose hover was #888 now hover to #CCC
 * so the hover state stays visible.
 *
 * Declared limits: reads page.tsx as text and checks un-prefixed arbitrary
 * `text-[#3xx-#6xx]` greys only. It does not render, does not compute
 * contrast at runtime, and does not cover KBLIInspector.tsx (only its helper
 * functions are imported by page.tsx; its JSX is not rendered here).
 */
const SRC = readFileSync(join(__dirname, "page.tsx"), "utf8");
const DARK_GREY = /(?<![\w:-])text-\[#[3-6][0-9a-fA-F]{2}\]/g;

describe("kbli-explorer page text meets AA on dark", () => {
  it("positive control: page.tsx is read and carries arbitrary text colours", () => {
    expect(
      SRC.match(/text-\[#[0-9a-fA-F]{3,6}\]/g)?.length ?? 0,
    ).toBeGreaterThan(0);
    expect(SRC).toContain("KBLI_CONCORDANCE_2025");
  });

  it("no #3xx-#6xx grey text", () => {
    expect([...SRC.matchAll(DARK_GREY)].map((m) => m[0])).toEqual([]);
  });

  it("the probe fires on the colours it forbids", () => {
    const probe = 'className="text-[#555] hover:text-[#444]"';
    expect([...probe.matchAll(DARK_GREY)].map((m) => m[0])).toEqual([
      "text-[#555]",
    ]);
  });
});
