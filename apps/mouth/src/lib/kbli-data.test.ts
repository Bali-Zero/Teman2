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

  it("normalizes section metadata and hero styles with safe fallbacks", () => {
    expect(getSectionMeta("i")).toMatchObject({
      nameEn: "Accommodation & Food Service",
      icon: "🏨",
    });
    expect(getSectionMeta("unknown")).toBeNull();

    expect(getHeroStyle("I").gradient).toContain("#e85d04");
    expect(getHeroStyle(null)).toEqual(getHeroStyle("unknown"));
  });
});
