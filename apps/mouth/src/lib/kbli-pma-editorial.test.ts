import { describe, expect, it } from "vitest";

import { getAllCodes, getCode } from "./kbli-data";
import { getGoldContent } from "./kbli-data.server";
import {
  discloseKbliBaliReason,
  discloseKbliEditorial,
  neutralKbliChatOpener,
} from "./kbli-pma-editorial";
import { isPmaVerdictVerified } from "./kbli-provenance";

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

    expect(codes).toHaveLength(1559);
    expect(located).toHaveLength(54);
    expect(gaps).toHaveLength(1505);
    expect(located.filter((record) => record.intel_2026)).toHaveLength(49);

    for (const record of gaps) {
      const disclosed = discloseKbliEditorial(
        record,
        getGoldContent(record.code),
      );
      expect(disclosed.intel).toBeUndefined();
      expect(disclosed.gold).toBeNull();
      expect(discloseKbliBaliReason(record)).toBeUndefined();
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
