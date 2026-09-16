import { describe, expect, it } from "vitest";

import { getAllCodes, getCode } from "./kbli-data";
import { getGoldContent } from "./kbli-data.server";
import {
  discloseKbliBaliReason,
  discloseKbliEditorial,
  neutralKbliChatOpener,
} from "./kbli-pma-editorial";
import { isPmaVerdictVerified } from "./kbli-provenance";
import { isSourcedBaliClosure } from "./kbli-pma-disclosure";

describe("PMA editorial disclosure boundary", () => {
  it.each(["16291", "10793"])(
    "withholds real generated ownership prose for declared-gap code %s",
    (code) => {
      const record = getCode(code);
      expect(record).toBeDefined();
      const rawGold = getGoldContent(code);
      expect(record?.intel_2026).toBeUndefined();
      expect(rawGold).toBeNull();

      const disclosed = discloseKbliEditorial(record!, rawGold);
      expect(disclosed.intel).toBeUndefined();
      expect(disclosed.gold).toBeNull();
      expect(disclosed.withheld).toBe(true);
      expect(discloseKbliBaliReason(record!)).toBeUndefined();
      expect(neutralKbliChatOpener(record!)).not.toMatch(
        /open|closed|100%|TERBUKA|TERBATAS|TERTUTUP/i,
      );
    },
  );

  it("preserves editorial identity for a located verdict", () => {
    const record = getCode("47221");
    expect(record).toBeDefined();
    expect(isPmaVerdictVerified(record!)).toBe(true);

    const gold = getGoldContent("47221");
    expect(gold).not.toBeNull();
    const disclosed = discloseKbliEditorial(record!, gold);
    expect(disclosed.intel).toBe(record!.intel_2026);
    expect(disclosed.gold).toBe(gold);
    expect(disclosed.withheld).toBe(false);
    expect(discloseKbliBaliReason(record!)).toBe(record!.baliL4?.reason);
  });

  it("withholds generated prose when the verdict is located but its cap is not verified", () => {
    const base = getCode("47221");
    expect(base).toBeDefined();
    const malformed = {
      ...base!,
      pma: {
        ...base!.pma,
        maxForeign: 100,
        capSpecial: false,
        capVerified: false,
      },
    };
    const sentinelGold = getGoldContent("47221");
    expect(sentinelGold).not.toBeNull();

    expect(discloseKbliEditorial(malformed, sentinelGold)).toEqual({
      gold: null,
      intel: undefined,
      withheld: true,
    });
  });

  it("rejects a torn located tuple whose public fields disagree with provenance", () => {
    const base = getCode("47221");
    expect(base).toBeDefined();
    const torn = {
      ...base!,
      pma: {
        ...base!.pma,
        officialBasis: "different locator",
      },
    };

    expect(isPmaVerdictVerified(torn)).toBe(false);
    expect(discloseKbliEditorial(torn, getGoldContent("47221"))).toMatchObject({
      gold: null,
      intel: undefined,
      withheld: true,
    });
  });

  it("enforces the corpus partition: gaps withheld and only reviewed located prose exposed", () => {
    const codes = getAllCodes();
    const located = codes.filter(isPmaVerdictVerified);
    const gaps = codes.filter((record) => !isPmaVerdictVerified(record));

    // SAETTA-20260915 W-H PR-3a moved 3 codes (55201/55203/79903) from
    // declared_gap to located (Lampiran II allocation): 1505 -> 1502, 54 -> 57.
    // The intel-bearing subset does NOT move with it: none of the 3 are
    // registered in pma-editorial-certifications.json's `canonicalIntel`
    // section, so `intel_2026` on the public KBLICode stays `undefined` for
    // all 3 regardless of this PR. W-H PR-3c v3 then de-certified 12 of the
    // 49 canonicalIntel entries (10214/16221/22121/47111/50111/50112/51102/
    // 55105/65111/79122/95220/96100) whose prose still claimed an openness
    // their own tuple denies: 49 -> 37.
    expect(codes).toHaveLength(1559);
    expect(located).toHaveLength(57);
    expect(gaps).toHaveLength(1502);
    expect(located.filter((record) => record.intel_2026)).toHaveLength(37);

    for (const record of gaps) {
      const disclosed = discloseKbliEditorial(
        record,
        getGoldContent(record.code),
      );
      expect(disclosed.intel).toBeUndefined();
      expect(disclosed.gold).toBeNull();
      // Added 2026-09-16 (W-J B1 disclose): a Bali APPLIED closure sourced to
      // a public press release discloses its reason too, even on a
      // `declared_gap` national record — the ONE named exception, scoped
      // exactly to `isSourcedBaliClosure`.
      if (isSourcedBaliClosure(record.baliL4)) {
        expect(discloseKbliBaliReason(record)).toBe(record.baliL4?.reason);
      } else {
        expect(discloseKbliBaliReason(record)).toBeUndefined();
      }
    }
    for (const record of located) {
      const gold = getGoldContent(record.code);
      const disclosed = discloseKbliEditorial(record, gold);
      expect(disclosed.intel).toBe(record.intel_2026);
      expect(disclosed.gold).toBe(gold);
      expect(discloseKbliBaliReason(record)).toBe(record.baliL4?.reason);
    }
    for (const code of ["10722", "47222", "50134", "73100", "96220"]) {
      const record = getCode(code)!;
      expect(record.intel_2026, code).toBeUndefined();
      expect(discloseKbliEditorial(record, getGoldContent(code)).withheld).toBe(
        getGoldContent(code) === null,
      );
    }
  });
});
