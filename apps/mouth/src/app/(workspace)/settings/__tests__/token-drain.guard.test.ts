import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WS2 kita slice 6 (final sweep) — settings suite drain guard.
 *
 * Pins the token drain of the WORKSPACE settings surfaces (hub, appearance,
 * roles, integrations, backup, api, notifications, security, users, locale,
 * profile): no raw hex (two documented one-off families excepted and marked:
 * role-color seeds required by <input type="color">, third-party brand
 * identity colors), no status rgba, no palette utilities. Statuses read
 * --state-*, purple reads --bz-neon-purple, decorative header icons read
 * --bz-accent, overlays read --surface-overlay.
 */

const PAGES = {
  hub: join(__dirname, "..", "page.tsx"),
  appearance: join(__dirname, "..", "appearance", "page.tsx"),
  roles: join(__dirname, "..", "roles", "page.tsx"),
  integrations: join(__dirname, "..", "integrations", "page.tsx"),
  backup: join(__dirname, "..", "backup", "page.tsx"),
  api: join(__dirname, "..", "api", "page.tsx"),
  notifications: join(__dirname, "..", "notifications", "page.tsx"),
  security: join(__dirname, "..", "security", "page.tsx"),
  users: join(__dirname, "..", "users", "page.tsx"),
  locale: join(__dirname, "..", "locale", "page.tsx"),
  profile: join(__dirname, "..", "profile", "page.tsx"),
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

describe("settings suite drain guard (WS2 slice 6)", () => {
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

  it("hub: cards read the dashboard recipe + --bz-border", () => {
    const src = readFileSync(PAGES.hub, "utf8");
    expect(src).toContain("rgba(35,35,40,0.6)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).toContain("var(--bz-border)");
    expect(src).not.toContain("rgba(255,255,255,0.05)"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(32,32,36"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(src).not.toContain("rgba(26,26,30"); // token-lint-ok: drain-guard assertion string, not a color use
  });

  it("appearance: accent swatches read the neon token family", () => {
    const src = readFileSync(PAGES.appearance, "utf8");
    expect(src).toContain("var(--bz-neon-cyan)");
    expect(src).toContain("var(--bz-neon-purple)");
    expect(src).toContain("var(--bz-neon-rose)");
  });

  it("roles: purple reads --bz-neon-purple, overlay reads --surface-overlay, seeds are marked", () => {
    const src = readFileSync(PAGES.roles, "utf8");
    expect(src).toContain("var(--bz-neon-purple)");
    expect(src).toContain("var(--surface-overlay)");
    // The <input type="color"> seed hexes stay, but every one is a marked,
    // documented one-off (picker requires #rrggbb values).
    const markers = src.match(/token-lint-ok: role color/g) ?? [];
    expect(markers.length).toBe(5);
  });

  it("integrations: brand hexes are marked one-offs, statuses read --state-*", () => {
    const src = readFileSync(PAGES.integrations, "utf8");
    const markers = src.match(/token-lint-ok: third-party brand/g) ?? [];
    expect(markers.length).toBe(5);
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-danger)");
  });

  it("warning strips read --state-warning (backup + api)", () => {
    for (const path of [PAGES.backup, PAGES.api]) {
      const src = readFileSync(path, "utf8");
      expect(src).toContain("var(--state-warning)");
    }
  });

  it("security: 2FA strips and session badge read --state-*", () => {
    const src = readFileSync(PAGES.security, "utf8");
    expect(src).toContain("var(--state-success)");
    expect(src).toContain("var(--state-warning)");
    expect(src).toContain("var(--state-danger)");
  });
});
