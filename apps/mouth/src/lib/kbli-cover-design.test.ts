import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";
import {
  SECTION_VISUALS,
  DEFAULT_SECTION_VISUAL,
  getSectionVisual,
  codeFingerprint,
  fingerprintsEqual,
  sectionGradient,
} from "./kbli-cover-design";

// All 22 KBLI sections (A-U real sectors + V catch-all "not yet classified"),
// per SECTION_PREFIX_MAP / SECTION_META in kbli-data.ts.
const ALL_SECTIONS = "ABCDEFGHIJKLMNOPQRSTUV".split("");

describe("SECTION_VISUALS", () => {
  it("has an entry for every KBLI section A-U plus V", () => {
    for (const section of ALL_SECTIONS) {
      expect(SECTION_VISUALS[section], `missing section ${section}`).toBeDefined();
    }
  });

  it("every section visual has non-empty hueA/hueB/accent and a valid motif", () => {
    const validMotifs = new Set([
      "organic",
      "grid",
      "waves",
      "circuit",
      "arc",
      "strata",
      "scatter",
    ]);
    for (const [section, visual] of Object.entries(SECTION_VISUALS)) {
      expect(visual.hueA, section).toMatch(/^#[0-9a-f]{6}$/i);
      expect(visual.hueB, section).toMatch(/^#[0-9a-f]{6}$/i);
      expect(visual.accent, section).toMatch(/^#[0-9a-f]{6}$/i);
      expect(validMotifs.has(visual.motif), `${section}: ${visual.motif}`).toBe(
        true,
      );
      expect(visual.label.length).toBeGreaterThan(0);
    }
  });

  it("hueA/hueB are dark (never neon) — every RGB channel stays below 0x40", () => {
    const channelMax = (hex: string) => {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return Math.max(r, g, b);
    };
    for (const [section, visual] of Object.entries(SECTION_VISUALS)) {
      expect(channelMax(visual.hueA), `${section} hueA`).toBeLessThanOrEqual(0x40);
      expect(channelMax(visual.hueB), `${section} hueB`).toBeLessThanOrEqual(0x40);
    }
  });

  it("getSectionVisual falls back to DEFAULT_SECTION_VISUAL for unknown/null section", () => {
    expect(getSectionVisual(null)).toEqual(DEFAULT_SECTION_VISUAL);
    expect(getSectionVisual(undefined)).toEqual(DEFAULT_SECTION_VISUAL);
    expect(getSectionVisual("ZZ")).toEqual(DEFAULT_SECTION_VISUAL);
  });

  it("getSectionVisual is case-insensitive", () => {
    expect(getSectionVisual("a")).toEqual(SECTION_VISUALS.A);
  });
});

describe("sectionGradient", () => {
  it("produces a linear-gradient CSS value from a section visual", () => {
    const css = sectionGradient(SECTION_VISUALS.I);
    expect(css).toBe(
      `linear-gradient(135deg, ${SECTION_VISUALS.I.hueA} 0%, ${SECTION_VISUALS.I.hueB} 100%)`,
    );
  });
});

describe("codeFingerprint", () => {
  it("is deterministic — same code always yields identical geometry", () => {
    const a = codeFingerprint("55203");
    const b = codeFingerprint("55203");
    expect(fingerprintsEqual(a, b)).toBe(true);
    expect(a.seed).toBe(b.seed);
    expect(a.motifRotation).toBe(b.motifRotation);
  });

  it("produces one bar per digit", () => {
    const fp = codeFingerprint("64194");
    expect(fp.bars).toHaveLength(5);
    expect(fp.bars.map((b) => b.digit)).toEqual([6, 4, 1, 9, 4]);
  });

  it("bar heightFrac stays within the legible 0.12-1.0 range", () => {
    for (const code of ["00000", "99999", "55203", "01111"]) {
      const fp = codeFingerprint(code);
      for (const bar of fp.bars) {
        expect(bar.heightFrac).toBeGreaterThanOrEqual(0.12);
        expect(bar.heightFrac).toBeLessThanOrEqual(1.0);
      }
    }
  });

  it("is distinct across a large sample of real-looking KBLI codes", () => {
    // Sample spans multiple sections/prefixes so the distinctness check is
    // not gamed by only ever hashing the same 2-digit prefix.
    const codes: string[] = [];
    const prefixes = [
      "01",
      "05",
      "10",
      "35",
      "41",
      "45",
      "49",
      "55",
      "58",
      "64",
      "68",
      "69",
      "77",
      "84",
      "85",
      "86",
      "90",
      "94",
      "97",
      "99",
    ];
    for (const prefix of prefixes) {
      for (let i = 0; i < 6; i++) {
        codes.push(`${prefix}${String(100 + i).slice(0, 3)}`);
      }
    }
    expect(codes.length).toBeGreaterThanOrEqual(100);

    const fingerprints = codes.map((c) => codeFingerprint(c));
    const signatures = new Set(
      fingerprints.map((fp) =>
        fp.bars
          .map((b) => `${b.heightFrac.toFixed(4)}:${b.xFrac.toFixed(4)}:${b.rotationDeg.toFixed(2)}`)
          .join("|"),
      ),
    );
    // Every code in the sample is unique, so every signature should be too.
    expect(signatures.size).toBe(codes.length);
  });

  it("motifRotation is a small non-negative integer in [0, 360)", () => {
    for (const code of ["12345", "00000", "99999"]) {
      const fp = codeFingerprint(code);
      expect(fp.motifRotation).toBeGreaterThanOrEqual(0);
      expect(fp.motifRotation).toBeLessThan(360);
      expect(Number.isInteger(fp.motifRotation)).toBe(true);
    }
  });
});

describe("no Unsplash / external image references in the new cover system", () => {
  it("kbli-cover-design.ts contains no unsplash.com or http(s) image URLs", () => {
    const source = readFileSync(
      join(__dirname, "kbli-cover-design.ts"),
      "utf-8",
    );
    expect(source).not.toContain("unsplash.com");
    expect(source).not.toMatch(/https?:\/\/images\./);
  });
});
