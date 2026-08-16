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
    const code = getCode("47111");
    const intel = rawCode("47111").intel_2026;
    expect(code).toBeDefined();
    expect(intel).toBeDefined();
    expect(hasCertifiedCanonicalIntel("47111", code!.pma, intel)).toBe(true);

    expect(
      hasCertifiedCanonicalIntel("47111", code!.pma, {
        ...intel,
        whatItMeans: `${intel!.whatItMeans}x`,
      }),
    ).toBe(false);
    expect(
      hasCertifiedCanonicalIntel(
        "47111",
        { ...code!.pma, maxForeign: 1 },
        intel,
      ),
    ).toBe(false);
  });

  it("certifies only manually reviewed Mouth gold bytes", () => {
    const safe = getCode("47111")!;
    const unsafe = getCode("47222")!;

    expect(hasCertifiedMouthGold("47111", safe.pma, rawGold["47111"])).toBe(
      true,
    );
    expect(
      hasCertifiedMouthGold("47111", safe.pma, {
        ...rawGold["47111"],
        whatChanged: `${rawGold["47111"].whatChanged}x`,
      }),
    ).toBe(false);
    expect(hasCertifiedMouthGold("47222", unsafe.pma, rawGold["47222"])).toBe(
      false,
    );
  });

  it("publishes exactly the reviewed partitions with compiler-owned openers", () => {
    const all = getAllCodes();
    const goldCodes = getGoldCodes();

    expect(all.filter((code) => code.intel_2026)).toHaveLength(49);
    expect(all.filter((code) => code.tier === "gold")).toHaveLength(15);
    expect(goldCodes).toHaveLength(15);
    expect(goldCodes).toEqual(
      expect.arrayContaining(["41020", "47111", "47221", "65121"]),
    );

    for (const code of ["10722", "47222", "50134", "73100", "96220"]) {
      expect(
        getCode(code)?.intel_2026,
        `${code} canonical intel`,
      ).toBeUndefined();
    }
    for (const code of [
      "21022",
      "41016",
      "41018",
      "47222",
      "55105",
      "73100",
      "96100",
    ]) {
      expect(getGoldContent(code), `${code} Mouth gold`).toBeNull();
    }

    expect(getCode("47111")?.intel_2026?.zantaraOpener).toBe(
      neutralKbliChatOpenerText("47111"),
    );
    expect(getGoldContent("47111")?.zantaraOpener).toBe(
      neutralKbliChatOpenerText("47111"),
    );
  });
});
