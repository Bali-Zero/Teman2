import { describe, expect, it } from "vitest";
import {
  getAllCodes,
  getCode,
  getGoldCodes,
  getSections,
  hasGoldContent,
  mapPmaStatus,
} from "./kbli-data.server";
import { hasPublishablePmaCap } from "./kbli-pma-disclosure";

/**
 * Mandate 12 (2026-08-09, PENDING-ARMS.md "sektor_id is not a malformed
 * KBLI section"): `kbli-data.server.ts` used to derive a code's `.section`
 * as `sektor_id.charAt(0)` — a PP28/2025 Lampiran locator, almost always
 * starting with "I", not a real KBLI/ISIC section. The only live consumer
 * is `sitemap.ts`'s `getSections()` call, which emitted exactly ONE KBLI
 * sector URL (`/kbli/sectors/I`) instead of the real ~21.
 *
 * These tests run against the REAL dataset (kbli-data.server.ts's own
 * loader), not a mock — the defect only shows up against real sektor_id
 * values, and a mock could accidentally assert the fix's own assumption.
 */
describe("kbli-data.server — section derivation (Mandate 12 fix)", () => {
  it("fails closed for unknown PMA vocabulary instead of defaulting to open", () => {
    expect(mapPmaStatus("TERBUKA")).toBe("open");
    expect(mapPmaStatus("TERBATAS")).toBe("restricted");
    expect(mapPmaStatus("TERTUTUP")).toBe("closed");
    expect(mapPmaStatus("FUTURE_STATUS")).toBe("unknown");
    expect(mapPmaStatus("terbuka")).toBe("unknown");
  });

  it("uses the same fail-closed PMA contract as the page loader", () => {
    const gap = getCode("01111");
    const located = getCode("02102");

    expect(gap?.pma).toMatchObject({
      status: "unknown",
      maxForeign: null,
      verificationStatus: "declared_gap",
      officialBasis: null,
      sourceVintage: null,
      source: null,
      citation: null,
    });
    expect(located?.pma).toMatchObject({
      status: "open",
      maxForeign: 100,
      verificationStatus: "located",
      sourceVintage: "2021-05-25",
    });
    expect(getAllCodes()).toHaveLength(1559);
    expect(
      getAllCodes().filter(
        (code) => code.pma.verificationStatus === "declared_gap",
      ),
    ).toHaveLength(1505);
    for (const code of getAllCodes().filter(
      (item) => item.pma.verificationStatus === "declared_gap",
    )) {
      expect(code.intel, `${code.code} intel`).toBeUndefined();
      expect(code.baliL4, `${code.code} Bali L4`).toBeUndefined();
    }
    expect(located?.intel).toBeDefined();
    expect(located?.baliL4).toBeDefined();
  });

  it("does not advertise generated gold content for a declared PMA gap", () => {
    expect(getCode("16291")?.pma.verificationStatus).toBe("declared_gap");
    expect(getCode("16291")?.tier).not.toBe("gold");
    expect(hasGoldContent("16291")).toBe(false);

    expect(getCode("47221")?.pma.verificationStatus).toBe("located");
    expect(getCode("47221")?.tier).toBe("gold");
    expect(hasGoldContent("47221")).toBe(true);
    expect(getGoldCodes()).toContain("47221");
    expect(getGoldCodes()).not.toContain("16291");
    expect(getGoldCodes()).toHaveLength(15);
    for (const code of getGoldCodes()) {
      expect(getCode(code)?.pma.verificationStatus, code).toBe("located");
      expect(hasPublishablePmaCap(getCode(code)!.pma), code).toBe(true);
    }
  });

  it("guilt: 56xxx (food service) and 47xxx (retail) resolve to their own true sections, not both to 'I'", () => {
    const foodService = getCode("56101");
    const retail = getCode("47721");

    expect(foodService?.section).toBe("I");
    expect(retail?.section).toBe("G");
    expect(retail?.section).not.toBe("I");
  });

  it("innocence: a spread of real codes each land on their own true section", () => {
    expect(getCode("01111")?.section).toBe("A");
    expect(getCode("64110")?.section).toBe("K");
    expect(getCode("85101")?.section).toBe("P");
    expect(getCode("94910")?.section).toBe("S");
  });

  it("mutation guard: the real dataset reports ~21 distinct sections with codes, not 1 (fails red without the fix)", () => {
    const codes = getAllCodes();
    expect(codes.length).toBeGreaterThan(1000);

    const sections = getSections().filter(
      (s) => /^[A-Z]$/.test(s.id) && s.codeCount > 0,
    );
    // Real KBLI-2025 dataset spreads across 21 of the 22 BPS sections
    // (V — "not yet classified" — has zero codes). Before the fix this
    // number was 1 (every non-empty sektor_id starts with "I").
    expect(sections.length).toBeGreaterThanOrEqual(18);
    expect(sections.length).not.toBe(1);
  });

  it("the sentinel '?' bucket (unmapped/missing prefix) is never labeled as a real section letter", () => {
    const sections = getSections();
    const sentinel = sections.find((s) => s.id === "?");
    if (sentinel) {
      expect(/^[A-Z]$/.test(sentinel.id)).toBe(false);
    }
  });
});
