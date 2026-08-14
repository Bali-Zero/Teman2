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
      expect(record?.intel_2026?.editorial?.body).toMatch(
        /foreign ownership|PMA/i,
      );

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
    const record = getCode("02102");
    expect(record).toBeDefined();
    expect(isPmaVerdictVerified(record!)).toBe(true);

    const gold = getGoldContent("02102");
    const disclosed = discloseKbliEditorial(record!, gold);
    expect(disclosed.intel).toBe(record!.intel_2026);
    expect(disclosed.gold).toBe(gold);
    expect(disclosed.withheld).toBe(false);
    expect(discloseKbliBaliReason(record!)).toBe(record!.baliL4?.reason);
  });

  it("enforces the corpus partition: 1505 gaps withheld, 54 located preserved", () => {
    const codes = getAllCodes();
    const located = codes.filter(isPmaVerdictVerified);
    const gaps = codes.filter((record) => !isPmaVerdictVerified(record));

    expect(codes).toHaveLength(1559);
    expect(located).toHaveLength(54);
    expect(gaps).toHaveLength(1505);

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
  });
});
