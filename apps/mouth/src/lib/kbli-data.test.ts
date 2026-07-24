import { describe, expect, it } from "vitest";
import {
  getAllCodes,
  getCode,
  getCodesBySection,
  getHeroStyle,
  getRelatedCodes,
  getSectionMeta,
  getSections,
} from "./kbli-data";

describe("kbli-data", () => {
  it("loads the canonical KBLI dataset as flat frontend records", () => {
    const codes = getAllCodes();

    expect(codes.length).toBeGreaterThan(1000);
    expect(codes[0]).toEqual(
      expect.objectContaining({
        code: expect.any(String),
        titleId: expect.any(String),
        titleEn: expect.any(String),
        description: expect.any(String),
        pma: expect.objectContaining({
          status: expect.stringMatching(/^(open|restricted|closed)$/),
          maxForeign: expect.any(Number),
        }),
        licensing: expect.any(Array),
        transition: expect.objectContaining({
          previousCodes: expect.any(Array),
        }),
        tier: expect.stringMatching(/^(gold|silver|bronze)$/),
        keywords: expect.any(Array),
      }),
    );
  });

  it("finds a known food-service code with transformed title and section data", () => {
    const code = getCode("56101");

    expect(code).toBeDefined();
    expect(code).toMatchObject({
      code: "56101",
      titleId: "Aktivitas Penyediaan Makanan di Bangunan Tetap",
      section: "I",
      sectionName: "Accommodation & Food Service",
    });
    expect(code?.keywords).toContain("penyediaan");
  });

  it("groups codes by section and reports matching section counts", () => {
    const sectionCodes = getCodesBySection("i");
    const sections = getSections();
    const sectionI = sections.find((section) => section.id === "I");

    expect(sectionCodes.length).toBeGreaterThan(0);
    expect(sectionI).toMatchObject({
      id: "I",
      nameEn: "Accommodation & Food Service",
      codeCount: sectionCodes.length,
    });
    expect(sectionCodes.every((code) => code.section === "I")).toBe(true);
  });

  it("returns related codes without repeating the target code", () => {
    const related = getRelatedCodes("56101", 4);

    expect(related.length).toBeGreaterThan(0);
    expect(related.length).toBeLessThanOrEqual(4);
    expect(related.map((item) => item.code)).not.toContain("56101");
    expect(related[0].code.startsWith("561")).toBe(true);
  });

  it("returns empty related-code results for unknown codes", () => {
    expect(getRelatedCodes("00000")).toEqual([]);
  });

  it("distributes related links to neighbors instead of the section head", () => {
    const sectionCodes = getCodesBySection("C");
    expect(sectionCodes.length).toBeGreaterThan(20);

    const last = sectionCodes[sectionCodes.length - 1];
    const relatedCodes = getRelatedCodes(last.code, 6).map((r) => r.code);

    // Neighbor-window: the immediate predecessor is always linked...
    expect(relatedCodes).toContain(sectionCodes[sectionCodes.length - 2].code);
    // ...and the old head-of-list fill (which concentrated every inbound
    // link on the first section codes) no longer happens.
    expect(relatedCodes).not.toContain(sectionCodes[0].code);
  });

  it("normalizes section metadata and hero styles with safe fallbacks", () => {
    expect(getSectionMeta("i")).toMatchObject({
      nameEn: "Accommodation & Food Service",
      icon: "🏨",
    });
    expect(getSectionMeta("unknown")).toBeNull();

    // 2026-07-07: getHeroStyle now derives from the deterministic
    // kbli-cover-design.ts palette (dark editorial, no neon) instead of the
    // old SECTOR_HERO map — assert per-section distinctness + stable
    // fallback rather than a specific hardcoded hex.
    expect(getHeroStyle("I").gradient).not.toEqual(getHeroStyle("J").gradient);
    expect(getHeroStyle(null)).toEqual(getHeroStyle("unknown"));
  });

  // Batch-B step 4 (2026-07-25): the additive `bps_2020_ancestors` canonical
  // field surfaces as `transition.bpsCrosswalk`, DISTINCT from the pp28-sourced
  // `previousCodes`. These are the guilt+innocence + no-regression tripwires.
  describe("bps_2020_ancestors → transition.bpsCrosswalk (additive, no regression)", () => {
    it("derives bpsCrosswalk on an OSS-native Batch-B code and shows the honest mechanical-only status", () => {
      // 01111 is OSS-native (_l2_status is null) and carries the field.
      const code = getCode("01111");
      expect(code).toBeDefined();
      const bps = code?.transition.bpsCrosswalk;
      expect(bps).toBeDefined();
      expect(bps?.codes.length).toBeGreaterThan(0);
      // At this migration step NOTHING is adjudicated — the surface must NOT
      // imply a licensing/regime transfer. Mechanical presence ≠ inheritance.
      expect(bps?.adjudicationStatus).toBe("mechanical-only");
      expect(bps?.inheritanceVerdict).toBe("not-adjudicated");
      // Regression guard: the legacy pp28-sourced list is UNTOUCHED alongside it.
      expect(Array.isArray(code?.transition.previousCodes)).toBe(true);
    });

    it("leaves bpsCrosswalk undefined on a Batch-A (no_oss_risk) code and keeps previousCodes intact", () => {
      // 01287 is _l2_status: no_oss_risk → out of Batch-B scope, no field.
      const code = getCode("01287");
      expect(code).toBeDefined();
      expect(code?.transition.bpsCrosswalk).toBeUndefined();
      expect(Array.isArray(code?.transition.previousCodes)).toBe(true);
    });

    it("carries bpsCrosswalk on exactly the 1,338 OSS-native codes and never with an empty codes list", () => {
      const codes = getAllCodes();
      const withBps = codes.filter((c) => c.transition.bpsCrosswalk);
      // EXPECTED_BATCH_B in scripts/kbli_filiera/populate_bps_ancestors.py — the
      // frontend surface is content-bound to the same OSS-native count. If a
      // future cure changes Batch-B membership, this breaking is a feature: it
      // forces re-verification of the honesty framing on both sides.
      expect(withBps.length).toBe(1338);
      // Never render an empty/degenerate crosswalk element.
      for (const c of withBps) {
        const bps = c.transition.bpsCrosswalk!;
        expect(bps.codes.length).toBeGreaterThan(0);
        expect(typeof bps.adjudicationStatus).toBe("string");
        expect(typeof bps.inheritanceVerdict).toBe("string");
      }
    });

    it("never clobbers previousCodes — every code still exposes it as an array", () => {
      // The change is purely additive; previousCodes must remain present and an
      // array on ALL codes (both those that gained bpsCrosswalk and those that
      // did not), never turned undefined by the new derivation.
      const codes = getAllCodes();
      expect(
        codes.every((c) => Array.isArray(c.transition.previousCodes)),
      ).toBe(true);
    });
  });
});
