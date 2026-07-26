import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 4 — HR suite drain guard.
 *
 * Pins the token drain of the five HR surfaces (leave, payroll slip detail,
 * bonuses, owner-cashout week detail, employees): no raw hex colors, no raw
 * status-rgba tuples, no Tailwind status palette utilities in the touched
 * files. Any future documented one-off survives ONLY on a line carrying a
 * `// token-lint-ok: <reason>` marker, mirroring scripts/token_lint.py.
 */

const HR_DIR = join(__dirname, "..");

const TOUCHED: Record<string, string> = {
  leave: join(HR_DIR, "leave", "page.tsx"),
  payslip: join(HR_DIR, "payroll", "[slipId]", "page.tsx"),
  bonuses: join(HR_DIR, "bonuses", "page.tsx"),
  ownerCashout: join(HR_DIR, "owner-cashout", "[weekId]", "page.tsx"),
  employees: join(HR_DIR, "employees", "page.tsx"),
};

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples the drain replaced with --state-* /
// --bz-accent color-mix tints.
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
  "rgba(59,130,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(96,165,250", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(99,102,241", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(139,92,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
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

describe("HR suite drain guard (WS2 slice 4)", () => {
  for (const [name, path] of Object.entries(TOUCHED)) {
    it(`${name} carries no unmarked raw hex colors`, () => {
      for (const line of codeLines(path)) {
        expect(HEX_RE.test(line), `hex in line: ${line.trim()}`).toBe(false);
      }
    });

    it(`${name} carries no raw status/accent rgba tuples`, () => {
      const src = codeLines(path).join("\n");
      for (const tuple of STATUS_RGBA_TUPLES) {
        expect(src.includes(tuple), `found ${tuple}`).toBe(false);
      }
    });

    it(`${name} carries no Tailwind status palette utilities`, () => {
      for (const line of codeLines(path)) {
        expect(PALETTE_UTIL_RE.test(line), `palette util: ${line.trim()}`).toBe(
          false,
        );
      }
    });

    it(`${name} panels read the dashboard recipe + --bz-border`, () => {
      const src = readFileSync(path, "utf8");
      expect(src).toContain("rgba(35,35,40,0.65)"); // token-lint-ok: drain-guard assertion string, not a color use
      expect(src).toContain("var(--bz-border)");
      expect(src).not.toContain("rgba(255,255,255,0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
      expect(src).not.toContain("rgba(255,255,255,0.07)"); // token-lint-ok: drain-guard assertion string, not a color use
    });
  }

  it("leave statuses map to --state-* (pending/approved/rejected)", () => {
    const src = readFileSync(TOUCHED.leave, "utf8");
    for (const token of [
      "var(--state-warning)",
      "var(--state-success)",
      "var(--state-danger)",
      "color-mix(in srgb,",
    ]) {
      expect(src).toContain(token);
    }
  });

  it("payslip + owner-cashout + bonuses + employees render IDR via Money", () => {
    for (const key of ["payslip", "ownerCashout", "bonuses", "employees"]) {
      const src = readFileSync(TOUCHED[key], "utf8");
      expect(src, `${key} imports Money`).toContain(
        'import { Money } from "@balizero/core"',
      );
      expect(src, `${key} renders Money`).toContain("<Money");
    }
  });
});
