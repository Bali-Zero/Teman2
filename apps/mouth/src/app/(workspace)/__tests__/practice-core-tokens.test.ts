/**
 * WS2 slice 1 (GARUDA OS) — practice-core token drain guard.
 *
 * The kita. workspace pages (operative-dark persona) went through the
 * redesign-tail token pass: hardcoded hexes, status rgba tuples and Tailwind
 * palette utilities that bypassed the token system were replaced by semantic
 * tokens (--state-*, --bz-*, --surface-*, --accent-whatsapp). This test pins
 * the drain: any NEW hardcoded color in the five practice-core pages (or
 * their single-use co-located components) fails here, before token-lint ever
 * sees the diff.
 *
 * Documented exception (kept deliberately, counted exactly): the three
 * channel-accent buttons on clients/[id] — Telegram (sky), Email (indigo),
 * Google Drive (amber). Only WhatsApp has a channel token
 * (--accent-whatsapp); the other channels have none, so their Tailwind
 * accents stay as fine one-off styles. Adding a FOURTH palette-colored
 * channel breaks this test — tokenize it instead.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

const WORKSPACE_DIR = path.resolve(__dirname, "..");

const PAGE_FILES = [
  "process/page.tsx",
  "process/[id]/page.tsx",
  "process/[id]/RequiredDocumentsCard.tsx",
  "clients/page.tsx",
  "clients/UnnamedLeadsBanner.tsx",
  "clients/new/page.tsx",
  "clients/new/components/PassportScanSection.tsx",
  "clients/[id]/page.tsx",
] as const;

// Hardcoded hex colors (#rgb/#rgba/#rrggbb/#rrggbbaa).
const HEX_RE = /(?<![0-9A-Za-z#&])#[0-9a-fA-F]{3,8}\b/g;

// Status/semantic rgba tuples that must now come from tokens via
// color-mix(in srgb, var(--state-*) X%, transparent) or --bz-accent.
const STATUS_RGBA_RE =
  /rgba\((?:239,68,68|245,158,11|34,197,94|249,115,22|59,130,246|139,92,246|99,102,241|16,185,129|74,222,128|156,163,175|113,113,122|217,95,90|212,\s*132,\s*90),/g;

// Tailwind palette utilities for status/semantic colors (red/green/blue/
// yellow/orange/amber/purple/sky/indigo/gray/zinc/slate + step).
const PALETTE_CLASS_RE =
  /(?:bg|text|border|ring|divide)-(?:red|green|blue|yellow|orange|amber|purple|sky|indigo|gray|zinc|slate)-[0-9]{2,3}/g;

// The documented channel-accent exception lives ONLY here.
const CHANNEL_EXCEPTION_FILE = "clients/[id]/page.tsx";
const ALLOWED_CHANNEL_ACCENTS = ["sky-500", "indigo-400", "amber-400"];

function readPage(file: string): string {
  return readFileSync(path.join(WORKSPACE_DIR, file), "utf8");
}

describe("WS2 practice-core token drain guard", () => {
  for (const file of PAGE_FILES) {
    it(`${file}: no hardcoded hex colors`, () => {
      const source = readPage(file);
      expect(source.match(HEX_RE) ?? []).toEqual([]);
    });

    it(`${file}: no hardcoded status rgba tuples`, () => {
      const source = readPage(file);
      expect(source.match(STATUS_RGBA_RE) ?? []).toEqual([]);
    });
  }

  for (const file of PAGE_FILES.filter((f) => f !== CHANNEL_EXCEPTION_FILE)) {
    it(`${file}: no Tailwind palette status utilities`, () => {
      const source = readPage(file);
      expect(source.match(PALETTE_CLASS_RE) ?? []).toEqual([]);
    });
  }

  it(`${CHANNEL_EXCEPTION_FILE}: only the 3 documented channel accents remain`, () => {
    const source = readPage(CHANNEL_EXCEPTION_FILE);
    const matches = source.match(PALETTE_CLASS_RE) ?? [];
    expect(matches.length).toBeGreaterThan(0); // guard the guard
    const uniqueSteps = [
      ...new Set(matches.map((m) => m.replace(/^[a-z]+-/, ""))),
    ];
    expect(uniqueSteps.sort()).toEqual([...ALLOWED_CHANNEL_ACCENTS].sort());
  });

  it("state semantics read --state-* tokens (spot check the drain landed)", () => {
    // If someone reverts the drain wholesale, these must fail.
    expect(readPage("process/page.tsx")).toContain("var(--state-danger)");
    expect(readPage("process/[id]/page.tsx")).toContain("var(--state-success)");
    expect(readPage("clients/page.tsx")).toContain("--bz-neon-purple");
    expect(readPage("clients/[id]/page.tsx")).toContain(
      "var(--accent-whatsapp)",
    );
  });
});
