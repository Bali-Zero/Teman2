/**
 * WS2 kita slice 2 — compliance & money drain guard.
 *
 * Source-scanning guard for the 5 pages drained in this slice
 * (lkpm list, review, lkpm/[id], accounting, lkpm/submit). Mirrors the
 * slice-1 practice-core guard contract: 0 raw hexes, 0 status rgba tuples,
 * 0 Tailwind palette utilities in the touched files — statuses read
 * --state-*, accents read --bz-*, panels mirror the dashboard recipe
 * (rgba(35,35,40,0.65) + var(--bz-border)), amounts render via Money.
 *
 * Comments may document what was drained; judge only code lines (same
 * filter as the portal lkpm/[quarter] guard).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const PAGES: Record<string, string> = {
  "lkpm list": join(__dirname, "..", "lkpm", "page.tsx"),
  "lkpm detail": join(__dirname, "..", "lkpm", "[id]", "page.tsx"),
  "lkpm submit": join(__dirname, "..", "lkpm", "submit", "page.tsx"),
  review: join(__dirname, "..", "review", "page.tsx"),
  accounting: join(__dirname, "..", "accounting", "page.tsx"),
};

function codeLines(path: string): string {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter(
      (l) => !l.trimStart().startsWith("*") && !l.trimStart().startsWith("//"),
    )
    .join("\n");
}

/** Raw hex literals drained by this slice (red/amber/emerald/blue/purple/gray scale + copper/gold). */
const FORBIDDEN_HEXES = [
  "#f87171", // token-lint-ok: drain-guard assertion string, not a color use
  "#fbbf24", // token-lint-ok: drain-guard assertion string, not a color use
  "#34d399", // token-lint-ok: drain-guard assertion string, not a color use
  "#60a5fa", // token-lint-ok: drain-guard assertion string, not a color use
  "#a78bfa", // token-lint-ok: drain-guard assertion string, not a color use
  "#9ca3af", // token-lint-ok: drain-guard assertion string, not a color use
  "#d4845a", // token-lint-ok: drain-guard assertion string, not a color use
  "#d95f5a", // token-lint-ok: drain-guard assertion string, not a color use
  "#d4923a", // token-lint-ok: drain-guard assertion string, not a color use
  "#2e9e6b", // token-lint-ok: drain-guard assertion string, not a color use
  "#4db87a", // token-lint-ok: drain-guard assertion string, not a color use
];

/** Status/accent rgba tuples drained to state tokens + color-mix tints. */
const FORBIDDEN_RGBA = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(245,158,11", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(59,130,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(168,85,247", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(107,114,128", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212, 132, 90", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(201,169,110", // token-lint-ok: drain-guard assertion string, not a color use
];

/** Tailwind palette utilities drained (status colors as utilities). */
const FORBIDDEN_PALETTE = [
  "bg-red-500/15",
  "text-red-400",
  "bg-amber-500/15",
  "text-amber-400",
  "bg-emerald-500/10",
  "text-emerald-400",
  "text-red-500",
  "text-emerald-600",
  "text-rose-600",
  "text-amber-600",
  "text-amber-700",
  "bg-amber-100",
  "bg-amber-50",
];

describe("WS2 kita slice 2 — compliance & money token drain guard", () => {
  for (const [name, path] of Object.entries(PAGES)) {
    it(`${name}: no raw hex colors`, () => {
      const src = codeLines(path);
      expect(src, `${name} leaked a hex`).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      for (const hex of FORBIDDEN_HEXES) {
        expect(src, `${name} still uses ${hex}`).not.toContain(hex);
      }
    });

    it(`${name}: no status rgba tuples`, () => {
      const src = codeLines(path);
      for (const tuple of FORBIDDEN_RGBA) {
        expect(src, `${name} still uses ${tuple}`).not.toContain(tuple);
      }
    });

    it(`${name}: no Tailwind palette status utilities`, () => {
      const src = codeLines(path);
      for (const util of FORBIDDEN_PALETTE) {
        expect(src, `${name} still uses ${util}`).not.toContain(util);
      }
    });

    it(`${name}: white-alpha borders drained to --bz-border`, () => {
      const src = codeLines(path);
      expect(src).not.toContain('borderColor: "rgba(255,255,255,0.05)"');
      expect(src).not.toContain('borderColor: "rgba(255, 255, 255, 0.05)"');
    });
  }

  it("lkpm list: statuses read --state-* tokens", () => {
    const src = codeLines(PAGES["lkpm list"]);
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-warning)");
    expect(src).toContain("var(--state-danger)");
    expect(src).toContain("var(--state-info)");
    // client_review purple channel — documented one-off via neon token.
    expect(src).toContain("var(--bz-neon-purple)");
  });

  it("lkpm list + detail: amounts render via Money, formatIDR gone", () => {
    for (const name of ["lkpm list", "lkpm detail"] as const) {
      const src = codeLines(PAGES[name]);
      expect(src, `${name} must use Money`).toContain("<Money value=");
      expect(src, `${name} must not import formatIDR`).not.toContain(
        'from "@balizero/core/utils"',
      );
    }
  });

  it("accounting: amounts render via Money (compact + full)", () => {
    const src = codeLines(PAGES.accounting);
    expect(src).toContain("<Money compact value=");
    expect(src).toContain("<Money value=");
  });

  it("review: statuses read --state-*, accents read --bz-accent", () => {
    const src = codeLines(PAGES.review);
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-danger)");
    expect(src).toContain("var(--state-warning)");
    // No legacy var() hex fallbacks survive.
    expect(src).not.toMatch(/var\(--bz-[a-z-]+,\s*#/);
  });

  it("lkpm submit: selected-company accent reads --bz-accent-warm", () => {
    const src = codeLines(PAGES["lkpm submit"]);
    expect(src).toContain("var(--bz-accent-warm)");
    expect(src).toContain("var(--state-danger)");
  });
});
