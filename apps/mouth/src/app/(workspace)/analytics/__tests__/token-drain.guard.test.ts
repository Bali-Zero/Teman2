import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 6 (final sweep) — analytics suite drain guard.
 *
 * Pins the token drain of the WORKSPACE analytics surfaces (hub + funnel):
 * no raw hex colors, no raw status-rgba tuples, no Tailwind status/neutral
 * palette utilities (incl. zinc/gray/slate and border-t/l/r variants).
 * Categorical stat accents read the --bz-chart-* series (cyan -> neon twin),
 * statuses read --state-*, panels read the dashboard recipe, amounts read
 * the Money component.
 */

const PAGES = {
  hub: join(__dirname, "..", "page.tsx"),
  funnel: join(__dirname, "..", "funnel", "page.tsx"),
};

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples the drain replaced with --state-* /
// --bz-accent color-mix tints.
const STATUS_RGBA_TUPLES = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(77,184,122", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(251,191,36", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(245,158,11", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
];

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

describe("analytics suite drain guard (WS2 slice 6)", () => {
  for (const [name, path] of Object.entries(PAGES)) {
    it(`${name}: no unmarked raw hex colors`, () => {
      for (const line of codeLines(path)) {
        expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
      }
    });

    it(`${name}: no raw status/accent rgba tuples`, () => {
      const src = codeLines(path).join("\n");
      for (const tuple of STATUS_RGBA_TUPLES) {
        expect(src.includes(tuple), `found ${tuple}`).toBe(false);
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

  it("hub: categorical stat accents read the --bz-chart-* series", () => {
    const src = readFileSync(PAGES.hub, "utf8");
    expect(src).toContain("var(--bz-chart-1)");
    expect(src).toContain("var(--bz-chart-6)");
    expect(src).toContain("var(--bz-neon-cyan)");
  });

  it("hub: statuses read --state-* and legacy aliases are gone", () => {
    const src = readFileSync(PAGES.hub, "utf8");
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-warning)");
    expect(src).toContain("var(--state-danger)");
    expect(src).not.toContain("var(--success)");
    expect(src).not.toContain("var(--warning)");
    expect(src).not.toContain("var(--error)");
  });

  it("hub: panels read the dashboard recipe + --bz-border", () => {
    const src = readFileSync(PAGES.hub, "utf8");
    expect(src).toContain("var(--bz-card)");
    expect(src).toContain("var(--bz-border)");
    expect(src).not.toContain("rgba(255, 255, 255, 0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(32,32,36"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("hub: IDR amounts read the Money component", () => {
    const src = readFileSync(PAGES.hub, "utf8");
    expect(src).toContain('import { Money } from "@balizero/core"');
    expect(src).toContain("<Money value={data.crm.revenue_paid} />");
    expect(src).not.toContain("formatIDR(");
  });

  it("funnel: statuses/text read tokens, panels read the recipe", () => {
    const src = readFileSync(PAGES.funnel, "utf8");
    expect(src).toContain("var(--state-danger)");
    expect(src).toContain("var(--bz-text-2)");
    expect(src).toContain("var(--bz-card)");
    expect(src).not.toContain("var(--color-text-secondary"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(26,26,30"); // token-lint-ok: drain-guard assertion string, not a color use
  });
});
