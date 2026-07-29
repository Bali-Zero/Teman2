import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 3 — news-room drain guard.
 *
 * Pins the token drain of the news-room surface: no raw hex colors, no
 * raw status-rgba tuples, no Tailwind status palette utilities in the
 * touched files. Documented one-offs (the sky UPDATED identity — no
 * operative token covers the sky hue) are kept ONLY on lines carrying a
 * `// token-lint-ok: <reason>` marker, mirroring scripts/token_lint.py.
 */

const PAGE = join(__dirname, "page.tsx");
const PALETTE = join(__dirname, "article-palette.ts");
const UPLOADER = join(__dirname, "components", "CoverImageUploader.tsx");

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples the drain replaced with --state-* /
// --bz-accent color-mix tints (sky included: in page.tsx it is forbidden,
// in article-palette.ts it survives only on marked one-off lines).
const STATUS_RGBA_TUPLES = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(244,63,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(5,150,105", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(52,211,153", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(34,197,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(77,184,122", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(251,191,36", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(245,158,11", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(99,102,241", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(139,92,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(14,165,233", // token-lint-ok: drain-guard assertion string, not a color use
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

describe("news-room drain guard (WS2 slice 3)", () => {
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

  it("page.tsx panels read the dashboard recipe + --bz-border", () => {
    const src = readFileSync(PAGE, "utf8");
    expect(src).toContain("var(--bz-card)");
    expect(src).toContain("var(--surface-raised)");
    expect(src).toContain("var(--bz-border)");
    expect(src).not.toContain("rgba(35,35,40,0.6)"); // token-lint-ok: regression guard string, not a color use
    expect(src).not.toContain("rgba(255,255,255,0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(255,255,255,0.07)"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("article-palette.ts state palettes read tokens, not raw values", () => {
    const src = readFileSync(PALETTE, "utf8");
    for (const token of [
      "var(--state-danger)",
      "var(--state-info)",
      "var(--bz-accent)",
      "color-mix(in srgb,",
    ]) {
      expect(src).toContain(token);
    }
    for (const line of codeLines(PALETTE)) {
      expect(HEX_RE.test(line), `unmarked hex: ${line.trim()}`).toBe(false);
    }
  });

  it("article-palette.ts keeps sky as the only documented one-off", () => {
    const lines = readFileSync(PALETTE, "utf8").split("\n");
    const skyHex = "#38bdf8"; // token-lint-ok: drain-guard assertion string, not a color use
    const hexLines = lines.filter((l) => HEX_RE.test(l));
    expect(hexLines.length).toBeGreaterThan(0);
    for (const line of hexLines) {
      expect(line).toContain(skyHex);
      expect(line).toContain("token-lint-ok:");
    }
  });

  it("CoverImageUploader.tsx carries no palette utilities or raw hex", () => {
    for (const line of codeLines(UPLOADER)) {
      expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
        false,
      );
      expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
    }
    expect(readFileSync(UPLOADER, "utf8")).toContain("var(--state-danger)");
  });
});
