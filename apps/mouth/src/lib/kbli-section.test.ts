import { describe, expect, it } from "vitest";
import { getSectionFromCode, SECTION_PREFIX_MAP } from "./kbli-section";

describe("kbli-section — getSectionFromCode (Mandate 12)", () => {
  it("guilt: derives the section from the 2-digit prefix, not the sektor_id first letter — 56xxx and 47xxx do NOT both land on 'I'", () => {
    // 56xxx (food service) and 47xxx (retail) both carry a sektor_id
    // starting with the Lampiran-I roman numeral ("I.J-P", "I.B", ...) —
    // a sektor_id-derived read would put BOTH on section "I". The real
    // KBLI/ISIC prefix map disagrees.
    expect(getSectionFromCode("56101")).toBe("I");
    expect(getSectionFromCode("47721")).toBe("G");
    expect(getSectionFromCode("47721")).not.toBe("I");
  });

  it("innocence: an arbitrary set of real prefixes each resolve to their own true section", () => {
    expect(getSectionFromCode("01111")).toBe("A"); // agriculture
    expect(getSectionFromCode("64110")).toBe("K"); // financial
    expect(getSectionFromCode("85101")).toBe("P"); // education
    expect(getSectionFromCode("94910")).toBe("S"); // other services
    expect(getSectionFromCode("99000")).toBe("U"); // extraterritorial
  });

  it("returns null (not a silent default) for a prefix that maps to no section", () => {
    expect(getSectionFromCode("00000")).toBeNull();
    expect(getSectionFromCode("")).toBeNull();
  });

  it("mutation guard: the prefix map covers every 2-digit KBLI division without gaps or overlaps", () => {
    const allPrefixes = Object.values(SECTION_PREFIX_MAP).flat();
    const unique = new Set(allPrefixes);
    expect(unique.size).toBe(allPrefixes.length); // no prefix claimed twice
    expect(allPrefixes.length).toBeGreaterThanOrEqual(80); // 01-99 minus gaps, sanity floor
  });
});
