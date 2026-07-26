import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 6 (final sweep) — partners finance + orphaned drain guard.
 *
 * Pins the token drain of the WORKSPACE partners finance queue and orphaned
 * partners surfaces: the commission pipeline chips use the stateChip idiom
 * (warning/info/neon-purple/success/danger + neutral), amounts read the
 * Money component, panels read the dashboard recipe, form controls read
 * --bz-surface/--bz-border. No raw hex, no status rgba, no palette
 * utilities.
 */

const PAGES = {
  finance: join(__dirname, "page.tsx"),
  orphaned: join(__dirname, "..", "orphaned", "page.tsx"),
};

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

const PALETTE_UTIL_RE =
  /\b(?:bg|text|border)(?:-[tlbrxy])?-(?:red|green|emerald|amber|rose|blue|sky|cyan|purple|violet|indigo|yellow|zinc|gray|slate|neutral|stone|orange|pink|fuchsia|lime|teal)-\d/;

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

describe("partners finance/orphaned drain guard (WS2 slice 6)", () => {
  for (const [name, path] of Object.entries(PAGES)) {
    it(`${name}: no unmarked raw hex colors`, () => {
      for (const line of codeLines(path)) {
        expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
      }
    });

    it(`${name}: no Tailwind status/neutral palette utilities`, () => {
      for (const line of codeLines(path)) {
        expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
          false,
        );
      }
    });

    it(`${name}: panels read the dashboard recipe + --bz-border`, () => {
      const src = readFileSync(path, "utf8");
      expect(src).toContain("rgba(35,35,40,0.65)"); // token-lint-ok: drain-guard assertion string, not a color use
      expect(src).toContain("var(--bz-border)");
    });
  }

  it("finance: commission chips use the stateChip idiom", () => {
    const src = readFileSync(PAGES.finance, "utf8");
    expect(src).toContain("stateChip(");
    expect(src).toContain('stateChip("var(--state-warning)")');
    expect(src).toContain('stateChip("var(--state-info)")');
    expect(src).toContain('stateChip("var(--bz-neon-purple)")');
    expect(src).toContain('stateChip("var(--state-success)")');
    expect(src).toContain('stateChip("var(--state-danger)")');
  });

  it("finance: IDR amounts read the Money component", () => {
    const src = readFileSync(PAGES.finance, "utf8");
    expect(src).toContain('import { Money } from "@balizero/core"');
    expect(src).toContain("<Money value={c.gross_amount} />");
    expect(src).toContain("<Money value={c.net_amount} />");
    expect(src).not.toContain("formatIDR(");
  });

  it("orphaned: selection reads --surface-selected, actions read --state-danger", () => {
    const src = readFileSync(PAGES.orphaned, "utf8");
    expect(src).toContain("var(--surface-selected)");
    expect(src).toContain("var(--state-danger)");
    expect(src).toContain("var(--bz-accent)");
  });
});
