import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 3 — voice-concierge drain guard.
 *
 * Pins the token drain of the voice-concierge surface: no raw hex colors,
 * no raw status-rgba tuples, no bespoke near-black card surfaces, no
 * Tailwind status palette utilities. Neutral white-alpha tints that
 * remain (pill/row backgrounds, assistant bubble) are deliberate fine
 * one-offs; every border and every status/accent value reads a token.
 */

const CLIENT = join(__dirname, "VoiceConciergeClient.tsx");
const PAGE = join(__dirname, "page.tsx");

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples + the bespoke near-black card surface the
// drain replaced with --state-* / --bz-accent tints and the panel recipe.
const STATUS_RGBA_TUPLES = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(34,197,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(77,184,122", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(10,12,16", // token-lint-ok: drain-guard assertion string, not a color use
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

describe("voice-concierge drain guard (WS2 slice 3)", () => {
  it("VoiceConciergeClient.tsx carries no unmarked raw hex colors", () => {
    for (const line of codeLines(CLIENT)) {
      expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
    }
  });

  it("VoiceConciergeClient.tsx carries no raw status/bespoke rgba tuples", () => {
    const src = codeLines(CLIENT).join("\n");
    for (const tuple of STATUS_RGBA_TUPLES) {
      expect(src.includes(tuple), `found ${tuple}`).toBe(false);
    }
  });

  it("concierge files carry no Tailwind status palette utilities", () => {
    for (const line of [...codeLines(CLIENT), ...codeLines(PAGE)]) {
      expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
        false,
      );
    }
  });

  it("cards read the dashboard panel recipe + --bz-border", () => {
    const src = readFileSync(CLIENT, "utf8");
    expect(src).toContain("rgba(35,35,40,0.65)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).toContain("var(--bz-border)");
    expect(src).not.toContain("rgba(255,255,255,0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(255,255,255,0.08)"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("ready/gated states read --state-success / --state-danger", () => {
    const src = readFileSync(CLIENT, "utf8");
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-danger)");
    // Pastel steps are built from the state tokens, not raw green/red hex.
    expect(src).not.toContain("#86efac"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("#fca5a5"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("user bubble + mode dot read --bz-accent; no --bz-green alias", () => {
    const src = readFileSync(CLIENT, "utf8");
    expect(src).toContain("var(--bz-accent)");
    expect(src).not.toContain("var(--bz-green");
  });
});
