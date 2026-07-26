import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 6 (final sweep) — system-pulse drain guard.
 *
 * Pins the token drain of the WORKSPACE intelligence/system-pulse surface:
 * health ternaries read --state-success/warning/danger, informational cards
 * read --state-info, purple reads --bz-neon-purple, card borders read
 * --bz-border, panels read the dashboard recipe. No raw hex, no status
 * rgba, no palette utilities (incl. border-t-* status rims and the
 * light-pastel badge classes the pre-drain page used).
 */

const PAGES = {
  page: join(__dirname, "page.tsx"),
  error: join(__dirname, "error.tsx"),
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

describe("system-pulse drain guard (WS2 slice 6)", () => {
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
  }

  it("health statuses read --state-*", () => {
    const src = readFileSync(PAGES.page, "utf8");
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-warning)");
    expect(src).toContain("var(--state-danger)");
    expect(src).toContain("var(--state-info)");
  });

  it("purple reads --bz-neon-purple, borders read --bz-border", () => {
    const src = readFileSync(PAGES.page, "utf8");
    expect(src).toContain("var(--bz-neon-purple)");
    expect(src).toContain("var(--bz-border)");
    expect(src).not.toContain("rgba(255, 255, 255, 0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(32,32,36"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("panels read the dashboard recipe", () => {
    const src = readFileSync(PAGES.page, "utf8");
    expect(src).toContain("rgba(35,35,40,0.6)"); // token-lint-ok: drain-guard assertion string, not a color use
  });
});
