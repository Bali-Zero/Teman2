import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 7 — OwnerCashoutCharts drain guard.
 *
 * Pins the token drain of the owner-cashout recharts surfaces: no raw
 * hex (zinc grid/axis/tooltip hexes -> --bz-border / --bz-text-muted /
 * --bz-bg-elevated; emerald/amber series -> --bz-chart-2 / --bz-chart-3),
 * mirroring scripts/token_lint.py HEX_RE.
 */

const COMPONENT = join(__dirname, "OwnerCashoutCharts.tsx");

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Status AND neutral families (slices 4-6 extended regex).
const PALETTE_UTIL_RE =
  /\b(?:bg|text|border|ring|divide|fill|stroke|from|to|via)-(?:red|green|emerald|amber|rose|blue|sky|cyan|purple|violet|indigo|yellow|orange|teal|fuchsia|pink|lime|zinc|gray|slate|neutral|stone)-\d/;

/** Code lines only: drops full-line comments and token-lint-ok one-offs. */
function codeLines(path: string): string[] {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((l) => {
      const t = l.trimStart();
      if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) {
        return false;
      }
      return !l.includes("token-lint-ok:");
    });
}

describe("OwnerCashoutCharts drain guard (WS2 slice 7)", () => {
  it("carries no unmarked raw hex colors", () => {
    for (const line of codeLines(COMPONENT)) {
      expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
    }
  });

  it("carries no Tailwind palette utilities (status + neutral)", () => {
    for (const line of codeLines(COMPONENT)) {
      expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
        false,
      );
    }
  });

  it("chart chrome reads border/text/surface tokens", () => {
    const src = readFileSync(COMPONENT, "utf8");
    expect(src).toContain('stroke="var(--bz-border)"');
    expect(src).toContain('stroke="var(--bz-text-muted)"');
    expect(src).toContain('background: "var(--bz-bg-elevated)"');
  });

  it("chart series read --bz-chart-* tokens", () => {
    const src = readFileSync(COMPONENT, "utf8");
    expect(src).toContain('stroke="var(--bz-chart-2)"');
    expect(src).toContain('stroke="var(--bz-chart-3)"');
    expect(src).toContain('fill="var(--bz-chart-2)"');
  });
});
