import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 5 — partners & team-management drain guard.
 *
 * Pins the token drain of the five surfaces (team-management, partners list,
 * partner detail, partner new, partner edit): no raw hex colors, no raw
 * status-rgba tuples, no Tailwind status/neutral palette utilities in the
 * touched files. Any future documented one-off survives ONLY on a line
 * carrying a `// token-lint-ok: <reason>` marker, mirroring
 * scripts/token_lint.py.
 */

const PARTNERS_DIR = join(__dirname, "..");
const WORKSPACE_DIR = join(PARTNERS_DIR, "..");

const TOUCHED: Record<string, string> = {
  teamManagement: join(WORKSPACE_DIR, "team-management", "page.tsx"),
  partnersList: join(PARTNERS_DIR, "page.tsx"),
  partnerDetail: join(PARTNERS_DIR, "[id]", "page.tsx"),
  partnerNew: join(PARTNERS_DIR, "new", "page.tsx"),
  partnerEdit: join(PARTNERS_DIR, "[id]", "edit", "page.tsx"),
};

// token_lint.py HEX_RE — 3/4/6/8 digits, word-boundary aware.
const HEX_RE =
  /(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])/;

// Raw status/accent rgba tuples the drain replaced with --state-* /
// --bz-accent color-mix tints.
const STATUS_RGBA_TUPLES = [
  "rgba(239,68,68", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(244,63,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(185,28,28", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(16,185,129", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(5,150,105", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(52,211,153", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(34,197,94", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(22,163,74", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(251,191,36", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(245,158,11", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(217,119,6", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(249,115,22", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(154,52,18", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(250,204,21", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(133,77,14", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(59,130,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(96,165,250", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(99,102,241", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(139,92,246", // token-lint-ok: drain-guard assertion string, not a color use
  "rgba(212,132,90", // token-lint-ok: drain-guard assertion string, not a color use
];

// Status palettes drained to --state-*; neutrals (zinc/gray) drained to
// --bz-text-*/--bz-border; orange (legacy bronze tier) drained to --bz-accent.
const PALETTE_UTIL_RE =
  /\b(?:bg|text|border)-(?:red|green|emerald|amber|rose|blue|sky|cyan|purple|violet|indigo|yellow|orange|zinc|gray|slate|neutral|stone)-\d/;

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

describe("partners & team-management drain guard (WS2 slice 5)", () => {
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

    it(`${name} carries no Tailwind status/neutral palette utilities`, () => {
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
      expect(src).not.toContain("rgba(255,255,255,0.1)"); // token-lint-ok: drain-guard assertion string, not a color use
    });
  }

  it("partner statuses map honestly to --state-* (pending/active/inactive)", () => {
    for (const key of ["partnersList", "partnerDetail"]) {
      const src = readFileSync(TOUCHED[key], "utf8");
      expect(src, `${key} pending_approval -> warning`).toContain(
        "var(--state-warning)",
      );
      expect(src, `${key} active -> success`).toContain("var(--state-success)");
      expect(src, `${key} chips tint via color-mix`).toContain(
        "color-mix(in srgb,",
      );
    }
  });

  it("commission pipeline statuses keep paid->success + clawed_back->danger", () => {
    const src = readFileSync(TOUCHED.partnerDetail, "utf8");
    expect(src).toContain('paid: stateChip("var(--state-success)")');
    expect(src).toContain('clawed_back: stateChip("var(--state-danger)")');
    expect(src).toContain('ready_to_pay: stateChip("var(--bz-neon-purple)")');
  });

  it("partners list + detail render IDR amounts via Money", () => {
    for (const key of ["partnersList", "partnerDetail"]) {
      const src = readFileSync(TOUCHED[key], "utf8");
      expect(src, `${key} imports Money`).toContain(
        'import { Money } from "@balizero/core"',
      );
      expect(src, `${key} renders Money`).toContain("<Money");
    }
  });

  it("team-management reads state + accent tokens, not legacy aliases", () => {
    const src = readFileSync(TOUCHED.teamManagement, "utf8");
    for (const token of [
      "var(--state-success)",
      "var(--state-info)",
      "var(--state-warning)",
      "var(--bz-neon-purple)",
      "var(--bz-accent)",
      "var(--bz-border)",
    ]) {
      expect(src).toContain(token);
    }
    // legacy kita aliases drained
    expect(src).not.toContain("var(--success)");
    expect(src).not.toContain("var(--foreground)");
  });
});
