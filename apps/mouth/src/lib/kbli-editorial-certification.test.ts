import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  hasCertifiedCanonicalIntel,
  hasCertifiedMouthGold,
  neutralKbliChatOpenerText,
} from "./kbli-editorial-certification";
import { getAllCodes, getCode } from "./kbli-data";
import { getGoldCodes, getGoldContent } from "./kbli-data.server";
import type { KBLIGoldContent, KBLIRawCode } from "./kbli-types";

const canonical = JSON.parse(
  fs.readFileSync(
    path.join(process.cwd(), "data", "KBLI_2025_FINAL_CLEAN.json"),
    "utf8",
  ),
) as { data: KBLIRawCode[] };
const parsedGold = JSON.parse(
  fs.readFileSync(
    path.join(process.cwd(), "data", "kbli-gold-all.json"),
    "utf8",
  ),
) as { data?: Record<string, KBLIGoldContent> } & Record<
  string,
  KBLIGoldContent
>;
const rawGold = parsedGold.data ?? parsedGold;

function rawCode(code: string): KBLIRawCode {
  const record = canonical.data.find((item) => item.kode_kbli_2025 === code);
  if (!record) throw new Error(`missing canonical code ${code}`);
  return record;
}

describe("PMA editorial certification", () => {
  it("binds reviewed prose to both exact content and the complete PMA fingerprint", () => {
    const code = getCode("41016");
    const intel = rawCode("41016").intel_2026;
    expect(code).toBeDefined();
    expect(intel).toBeDefined();
    expect(hasCertifiedCanonicalIntel("41016", code!.pma, intel)).toBe(true);

    expect(
      hasCertifiedCanonicalIntel("41016", code!.pma, {
        ...intel,
        whatItMeans: `${intel!.whatItMeans}x`,
      }),
    ).toBe(false);
    expect(
      hasCertifiedCanonicalIntel(
        "41016",
        { ...code!.pma, maxForeign: 1 },
        intel,
      ),
    ).toBe(false);
  });

  it("certifies only manually reviewed Mouth gold bytes", () => {
    const safe = getCode("47221")!;
    const unsafe = getCode("47222")!;

    expect(hasCertifiedMouthGold("47221", safe.pma, rawGold["47221"])).toBe(
      true,
    );
    expect(
      hasCertifiedMouthGold("47221", safe.pma, {
        ...rawGold["47221"],
        whatChanged: `${rawGold["47221"].whatChanged}x`,
      }),
    ).toBe(false);
    expect(hasCertifiedMouthGold("47222", unsafe.pma, rawGold["47222"])).toBe(
      false,
    );
  });

  it("publishes exactly the reviewed partitions with compiler-owned openers", () => {
    const all = getAllCodes();
    const goldCodes = getGoldCodes();

    // SAETTA-20260915 W-H PR-3c v3 de-certified 12 canonicalIntel entries and
    // 6 mouthGold entries whose prose still claimed openness a record's own
    // tuple denies (49 -> 37 canonicalIntel; 14 -> 8 mouthGold). A fresh gate
    // on the predecessor (#6593/#6594) BLOCKED partly because this file still
    // pinned the pre-decertification counts and 47111 as certified gold —
    // do not let these numbers drift from the registry again without a test
    // failure naming the exact mismatch.
    expect(all.filter((code) => code.intel_2026)).toHaveLength(35);
    expect(all.filter((code) => code.tier === "gold")).toHaveLength(8);
    expect(goldCodes).toHaveLength(8);
    expect(goldCodes).toEqual(
      expect.arrayContaining(["47221", "50113", "51101", "53200"]),
    );

    for (const code of [
      "10214",
      "16221",
      "22121",
      "47111",
      "50111",
      "50112",
      "51102",
      "55105",
      "65111",
      "79122",
      "95220",
      "96100",
      "47221",
      "10722",
      "47222",
      "50134",
      "73100",
      "96220",
    ]) {
      expect(
        getCode(code)?.intel_2026,
        `${code} canonical intel`,
      ).toBeUndefined();
    }
    for (const code of [
      "21022",
      "41016",
      "41018",
      "41020",
      "47222",
      "50133",
      "55105",
      "65121",
      "73100",
      "79122",
      "96100",
      "96210",
      "96220",
    ]) {
      expect(getGoldContent(code), `${code} Mouth gold`).toBeNull();
    }

    // Explicit withheld assertions (GATE-6593's second reason): 47111 lost
    // BOTH canonicalIntel and mouthGold certification in this same PR, and
    // 95220 is a representative canonical-only de-certification (its
    // pullQuote claimed "National openness remains real" on a 0%
    // Koperasi/UMKM-allocated record) — the page must fail closed on both
    // rather than serve stale certified prose.
    expect(
      getCode("47111")?.intel_2026,
      "47111 canonical intel withheld",
    ).toBeUndefined();
    expect(getGoldContent("47111"), "47111 Mouth gold withheld").toBeNull();
    expect(
      getCode("95220")?.intel_2026,
      "95220 canonical intel withheld",
    ).toBeUndefined();

    // W-H PR-3f: 47221's canonicalIntel.whatYouNeed claimed a UMKM/Koperasi
    // partnership condition that the record's own pma_kondisi denies (a
    // distribution-network/location requirement instead, Perpres 10/2021
    // Lampiran III line 4202 #44) — de-certify canonicalIntel ONLY.
    // mouthGold's 47221 prose was reviewed separately and stays certified.
    expect(
      getCode("47221")?.intel_2026,
      "47221 canonical intel withheld",
    ).toBeUndefined();

    expect(getCode("41016")?.intel_2026?.zantaraOpener).toBe(
      neutralKbliChatOpenerText("41016"),
    );
    expect(getGoldContent("47221")?.zantaraOpener).toBe(
      neutralKbliChatOpenerText("47221"),
    );
  });
});
