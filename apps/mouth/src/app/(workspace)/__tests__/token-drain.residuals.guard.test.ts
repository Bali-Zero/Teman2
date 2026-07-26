import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 7 — workspace pages residual drain guard.
 *
 * Pins the token drain of the eight residual workspace pages flagged by
 * the slice-6 sweep: no raw hex colors, no raw status-rgba tuples, no
 * Tailwind palette utilities (status AND neutral families — the slices
 * 4-6 extended regex). Statuses read --state-* color-mix tints,
 * categorical stat/chart accents read --bz-chart-*, purple reads
 * --bz-neon-purple, mirroring scripts/token_lint.py.
 */

const PAGES: Array<{ name: string; path: string; pins: string[] }> = [
  {
    name: "clients/analytics",
    path: join(__dirname, "..", "clients", "analytics", "page.tsx"),
    pins: ["var(--bz-chart-1)", "var(--state-success)", "var(--state-danger)"],
  },
  {
    name: "notifications",
    path: join(__dirname, "..", "notifications", "page.tsx"),
    pins: [
      "var(--state-success)",
      "var(--state-warning)",
      "var(--state-danger)",
    ],
  },
  {
    name: "admin/team-activity",
    path: join(__dirname, "..", "admin", "team-activity", "page.tsx"),
    pins: ["var(--bz-chart-1)", "var(--state-info)", "var(--bz-neon-purple)"],
  },
  {
    name: "admin",
    path: join(__dirname, "..", "admin", "page.tsx"),
    pins: ["var(--state-success)", "var(--bz-chart-1)"],
  },
  {
    name: "intelligence/analytics",
    path: join(__dirname, "..", "intelligence", "analytics", "page.tsx"),
    pins: [
      "var(--bz-neon-purple)",
      "var(--state-success)",
      "var(--state-danger)",
    ],
  },
  {
    name: "process/new",
    path: join(__dirname, "..", "process", "new", "page.tsx"),
    pins: ["var(--state-danger)", "var(--state-warning)"],
  },
  {
    name: "revenue/analytics",
    path: join(__dirname, "..", "revenue", "analytics", "page.tsx"),
    pins: ["var(--state-success)", "var(--state-warning)", "var(--bz-chart-2)"],
  },
  {
    name: "team/analytics",
    path: join(__dirname, "..", "team", "analytics", "page.tsx"),
    pins: ["var(--bz-chart-1)", "var(--bz-chart-4)"],
  },
];

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples the drain replaced with --state-* /
// --bz-chart-* color-mix tints.
const STATUS_RGBA_TUPLES = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(244,63,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(5,150,105", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(52,211,153", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(34,197,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(251,191,36", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(245,158,11", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(59,130,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(96,165,250", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(139,92,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(168,85,247", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(249,115,22", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(6,182,212", // token-lint-ok: drain-guard assertion string, not a color use
];

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

describe("workspace residual pages drain guard (WS2 slice 7)", () => {
  for (const page of PAGES) {
    it(`${page.name} carries no unmarked raw hex colors`, () => {
      for (const line of codeLines(page.path)) {
        expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
      }
    });

    it(`${page.name} carries no raw status/accent rgba tuples`, () => {
      const src = codeLines(page.path).join("\n");
      for (const tuple of STATUS_RGBA_TUPLES) {
        expect(src.includes(tuple), `found ${tuple}`).toBe(false);
      }
    });

    it(`${page.name} carries no Tailwind palette utilities (status + neutral)`, () => {
      for (const line of codeLines(page.path)) {
        expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
          false,
        );
      }
    });

    it(`${page.name} reads the drained tokens`, () => {
      const src = readFileSync(page.path, "utf8");
      for (const pin of page.pins) {
        expect(src.includes(pin), `missing ${pin}`).toBe(true);
      }
    });
  }
});
