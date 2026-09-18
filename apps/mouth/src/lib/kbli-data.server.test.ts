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
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";

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
    // SAETTA-20260915 W-H PR-3a moved 3 codes (55201/55203/79903) from
    // declared_gap to located (Lampiran II allocation): 1505 -> 1502.
    // W-H PR-3b moves 8 more codes (47241 47242 47244 47245 47246 47249
    // 47712 47722) from declared_gap to located (Lampiran II entry 46):
    // 1502 -> 1494.
    const gaps = getAllCodes().filter(
      (code) => code.pma.verificationStatus === "declared_gap",
    );
    // 2026-09-18 naso lot: 10307 10308 16291 16293 32201 55106 moved
    // declared_gap→located under Perpres 49/2021 Lampiran II (whole-code rows
    // via 1:1 BPS crosswalk), 1494→1488.
    // 2026-09-18 naso PR-2: 13133 closed by the union of Lampiran II item 11 +
    // Lampiran III entry #2, declared_gap→located, 1488→1487.
    expect(gaps).toHaveLength(1487);
    for (const code of gaps) {
      expect(code.intel, `${code.code} intel`).toBeUndefined();
    }

    // Added 2026-09-16 (W-J B1 disclose, review F5): "no baliL4 on a gap" has
    // exactly ONE named exception — a Bali APPLIED closure sourced to a
    // public press release. Testing that exception through the very
    // function that implements it (`isSourcedBaliClosure`, which by its own
    // definition REQUIRES `status === "CHIUSO_BALI"`) would be tautological:
    // it cannot catch a bug that widens the exception, only one that changes
    // which field it inspects. Instead this derives the expected set
    // independently from the raw JSON and asserts the served set matches it
    // exactly — no more, no fewer members.
    const rawDeclaredGapChiusoBali = (
      rawData as {
        data: Array<{
          kode_kbli_2025: string;
          pma_verification_status?: string;
          l4_bali?: { status?: string };
        }>;
      }
    ).data
      .filter(
        (r) =>
          r.l4_bali?.status === "CHIUSO_BALI" &&
          r.pma_verification_status !== "located",
      )
      .map((r) => r.kode_kbli_2025)
      .sort();
    const disclosedOnAGap = gaps
      .filter((code) => code.baliL4 !== undefined)
      .map((code) => code.code)
      .sort();
    expect(disclosedOnAGap).toEqual(rawDeclaredGapChiusoBali);
    // 39 -> 38 (W-H PR-3b): 47249 was one of the 39 declared_gap/CHIUSO_BALI
    // records the disclose change (above) surfaces. This cure moves it to
    // `pma_verification_status: "located"`, so it now fails this filter's
    // own `!== "located"` guard and leaves BOTH the raw-JSON-derived set and
    // `gaps` (it is no longer declared_gap at all) — not a disclosure bug,
    // the code is simply no longer a gap.
    // 38 -> 37 on 2026-09-18 (naso lot): 55106 (CHIUSO_BALI, ex-Hotel Melati)
    // moved to located under Lampiran II, so it leaves this set the same way
    // 47249 did — the other five naso codes are ATTENZIONE_FASCIA_BALI.
    expect(disclosedOnAGap).toHaveLength(37);
    for (const code of gaps) {
      if (code.baliL4 !== undefined) {
        expect(code.baliL4.status, code.code).toBe("CHIUSO_BALI");
        expect(code.baliL4.closure?.url, code.code).toMatch(/^https:\/\//);
      }
    }

    expect(located?.intel).toBeDefined();
    expect(located?.baliL4).toBeDefined();
  });

  it("does not advertise generated gold content for a declared PMA gap", () => {
    // 16291 → 16292 on 2026-09-18: 16291 is now located (Lampiran II, naso
    // lot) and its gold renders; 16292 is the declared-gap sibling with gold.
    expect(getCode("16292")?.pma.verificationStatus).toBe("declared_gap");
    expect(getCode("16292")?.tier).not.toBe("gold");
    expect(hasGoldContent("16292")).toBe(false);

    expect(getCode("47221")?.pma.verificationStatus).toBe("located");
    expect(getCode("47221")?.tier).toBe("gold");
    expect(hasGoldContent("47221")).toBe(true);
    expect(getGoldCodes()).toContain("47221");
    expect(getGoldCodes()).not.toContain("16292");
    // 15 -> 14: 47111 was de-certified from mouthGold by W-H PR-3c (its gold
    // prose named 47191/47192 as "fully open to 100% PMA" while both are
    // declared_gap; withdrawn rather than hand-edited, no compiler exists
    // for non-whatYouNeed gold fields). 14 -> 8: W-H PR-3c v3 de-certified
    // 41020/50133/65121/79122/96210/96220, whose prose still claimed an
    // openness their own tuple denies.
    expect(getGoldCodes()).not.toContain("47111");
    expect(getGoldCodes()).not.toContain("41020");
    expect(getGoldCodes()).not.toContain("50133");
    expect(getGoldCodes()).not.toContain("65121");
    expect(getGoldCodes()).not.toContain("79122");
    expect(getGoldCodes()).not.toContain("96210");
    expect(getGoldCodes()).not.toContain("96220");
    expect(getGoldCodes()).toHaveLength(8);
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
