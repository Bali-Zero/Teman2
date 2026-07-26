import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 3 — article-composer drain guard.
 *
 * Pins the token drain of the article-composer surface: no raw hex colors,
 * no raw status-rgba tuples, no Tailwind status palette utilities.
 * Neutral white-alpha tints that remain (chip backgrounds, disabled fills)
 * are deliberate fine one-offs; every status/accent value reads a token.
 */

const PAGE = join(__dirname, "page.tsx");

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples the drain replaced with --state-* /
// --bz-accent color-mix tints.
const STATUS_RGBA_TUPLES = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(77,184,122", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(34,197,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(251,191,36", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(192,106,58", // token-lint-ok: drain-guard assertion string, not a color use
];

const PALETTE_UTIL_RE =
  /\b(?:bg|text|border)-(?:red|green|emerald|amber|rose|blue|sky|cyan|purple|violet|indigo|yellow)-\d/;

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

describe("article-composer drain guard (WS2 slice 3)", () => {
  it("page.tsx carries no unmarked raw hex colors", () => {
    for (const line of codeLines(PAGE)) {
      expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
    }
  });

  it("page.tsx carries no raw status/accent rgba tuples", () => {
    const src = codeLines(PAGE).join("\n");
    for (const tuple of STATUS_RGBA_TUPLES) {
      expect(src.includes(tuple), `found ${tuple}`).toBe(false);
    }
  });

  it("page.tsx carries no Tailwind status palette utilities", () => {
    for (const line of codeLines(PAGE)) {
      expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
        false,
      );
    }
  });

  it("panels and inputs read the dashboard recipe + --bz-border", () => {
    const src = readFileSync(PAGE, "utf8");
    expect(src).toContain("rgba(35,35,40,0.65)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).toContain("rgba(35,35,40,0.6)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).toContain("var(--bz-border)");
    expect(src).not.toContain("rgba(255,255,255,0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(255,255,255,0.07)"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("statuses read --state-* tokens (success/danger/warning)", () => {
    const src = readFileSync(PAGE, "utf8");
    for (const token of [
      "var(--state-success)",
      "var(--state-danger)",
      "var(--state-warning)",
    ]) {
      expect(src).toContain(token);
    }
    // The legacy green alias + hex fallback pair is gone.
    expect(src).not.toContain("var(--bz-green");
  });

  it("copper accents are tokenized (no raw copper rgba/hex)", () => {
    const src = codeLines(PAGE).join("\n");
    expect(src).toContain("var(--bz-accent)");
    expect(src).not.toContain("rgba(212,132,90"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("#c06a3a"); // token-lint-ok: drain-guard assertion string, not a color use
  });
});
