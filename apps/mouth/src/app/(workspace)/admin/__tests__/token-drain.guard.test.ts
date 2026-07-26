import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 6 (final sweep) — admin/system drain guard.
 *
 * Pins the token drain of the WORKSPACE admin system ("control room")
 * surface: the bespoke green-on-black telemetry palette is mapped onto the
 * token SSOT — healthy telemetry -> --state-success, database -> --state-info,
 * vectors -> --bz-neon-purple, alerts -> --state-danger, panels -> the
 * dashboard recipe. No raw hex, no status rgba, no palette utilities.
 */

const PAGE = join(__dirname, "..", "system", "page.tsx");

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

describe("admin/system drain guard (WS2 slice 6)", () => {
  it("page.tsx carries no unmarked raw hex colors", () => {
    for (const line of codeLines(PAGE)) {
      expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
    }
  });

  it("page.tsx carries no Tailwind status/neutral palette utilities", () => {
    for (const line of codeLines(PAGE)) {
      expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
        false,
      );
    }
  });

  it("telemetry green reads --state-success", () => {
    const src = readFileSync(PAGE, "utf8");
    expect(src).toContain("var(--state-success)");
    // The bespoke matrix look is gone: no raw black surfaces remain.
    expect(src).not.toContain("bg-black");
  });

  it("database/vectors tabs read --state-info / --bz-neon-purple", () => {
    const src = readFileSync(PAGE, "utf8");
    expect(src).toContain("var(--state-info)");
    expect(src).toContain("var(--bz-neon-purple)");
  });

  it("alerts read --state-danger, panels read the dashboard recipe", () => {
    const src = readFileSync(PAGE, "utf8");
    expect(src).toContain("var(--state-danger)");
    expect(src).toContain("rgba(35,35,40,0.65)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).toContain("var(--bz-border)");
  });
});
