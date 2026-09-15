// =============================================================================
// kbli-pma-no-besar.test.ts — a code OSS gives no Usaha Besar scale cannot be
// operated by a PT PMA, so the figure this site publishes for it must be 0.
//
// Owner ruling 2026-09-14. Basis: Perpres 10/2021 Pasal 7(1) (a foreign
// investor may carry on business only as an Usaha Besar) and Permeninves/BKPM
// 5/2025 Pasal 26(1) («yang dikategorikan PMA merupakan usaha besar»).
//
// WHAT THIS GUARD DOES NOT DO, and it is the whole reason it can be trusted:
// it never infers a missing Besar scale from an EMPTY `per_skala`. An empty
// scale matrix is a gap in our snapshot of OSS, not a statement by OSS that no
// large-scale form exists. 217 records are in that state and 164 of them carry
// a non-zero cap; convicting them would be asserting a regulatory fact from our
// own missing data — the exact inference a previous closure made and had to be
// withdrawn for. The rule fires only on an OBSERVED absence: `per_skala` is
// populated AND no entry names Besar.
// =============================================================================

import { describe, it, expect } from "vitest";
import { resolvePmaCap } from "./kbli-pma-cap";
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";

interface RawRecord {
  kode_kbli_2025: string;
  pma_status?: string;
  pma_max_asing?: number | string;
  per_skala?: { skala_usaha?: unknown }[];
}

const RECORDS = (rawData as { data: RawRecord[] }).data;

/** The Usaha Besar scale, as an ENTITY: one element of a `skala_usaha` list.
 *
 * `skala_usaha` is a LIST per entry ("Mikro" / "Kecil" / "Menengah" / "Besar"),
 * so membership is the only honest test. Superscar #3 forbids deciding this by
 * substring, and here that is not a theoretical preference — see the
 * OVER-MATCH case below, which is measured on the live corpus. */
function hasUsahaBesarScale(record: RawRecord): boolean {
  return (record.per_skala ?? []).some((entry) => {
    const scales = entry?.skala_usaha;
    if (!Array.isArray(scales)) return false;
    return scales.some((s) => typeof s === "string" && s.trim() === "Besar");
  });
}

const POPULATED = RECORDS.filter((r) => (r.per_skala ?? []).length > 0);
/** The rule's subjects: scale matrix populated, and no Besar row in it. */
const NO_BESAR = POPULATED.filter((r) => !hasUsahaBesarScale(r));
/** Never subjects: an empty scale matrix says nothing either way. */
const EMPTY_SCALE = RECORDS.filter((r) => (r.per_skala ?? []).length === 0);

/** The published figure, read through the one resolver every surface uses. */
function publishedCap(record: RawRecord): number | "special" {
  return resolvePmaCap(record);
}

describe("no Usaha Besar scale => 0% foreign ownership", () => {
  it("the corpus splits exactly three ways, and the split is measured", () => {
    expect(RECORDS.length).toBe(1559);
    expect(POPULATED.length - NO_BESAR.length).toBe(1319);
    expect(NO_BESAR.length).toBe(23);
    expect(EMPTY_SCALE.length).toBe(217);
  });

  it("THE GUARD: no populated-without-Besar code publishes a non-zero cap", () => {
    const offenders = NO_BESAR.filter((r) => publishedCap(r) !== 0).map(
      (r) => `${r.kode_kbli_2025}=${String(publishedCap(r))}`,
    );
    expect(
      offenders,
      "OSS names no Usaha Besar scale for these codes, so a PT PMA cannot " +
        "operate them; any figure above 0 is a foreign-ownership promise the " +
        "regulation does not support",
    ).toEqual([]);
  });

  it("GUILT: the guard convicts a subject whose cap is put back to 100", () => {
    const subject = NO_BESAR.find((r) => r.kode_kbli_2025 === "55201");
    expect(subject, "55201 must be one of the rule's subjects").toBeDefined();
    expect(publishedCap(subject!)).toBe(0);

    // The mutation is the pre-ruling state of this very record, not a fiction.
    const mutated: RawRecord = {
      ...subject!,
      pma_status: "TERBUKA",
      pma_max_asing: 100,
    };
    expect(hasUsahaBesarScale(mutated)).toBe(false);
    expect(publishedCap(mutated)).toBe(100);
    expect(
      [mutated].filter((r) => !hasUsahaBesarScale(r) && publishedCap(r) !== 0),
    ).toHaveLength(1);
  });

  it("GUILT: dropping the cap field entirely does not launder the verdict", () => {
    // `resolvePmaCap` falls back to 100 on a TERBUKA record with no figure, so
    // deleting the datum is a second way back to a foreign-ownership promise.
    const subject = NO_BESAR.find((r) => r.kode_kbli_2025 === "55201")!;
    const stripped: RawRecord = { ...subject, pma_status: "TERBUKA" };
    delete stripped.pma_max_asing;
    expect(publishedCap(stripped)).toBe(100);
    expect(hasUsahaBesarScale(stripped)).toBe(false);
  });

  it("OVER-MATCH: a substring selector acquits every subject it should catch", () => {
    // Superscar #3, measured rather than argued. Each subject now carries its
    // own citation text — "No Usaha Besar scale in OSS for this code..." — so
    // the word "Besar" appears in all 23 records that have NO Besar scale. A
    // selector that searched the serialized record for the word would call
    // every one of them Besar-bearing and wave the whole class through, and it
    // would do so precisely because the cure was applied. The entity test is
    // what keeps the guard honest.
    const bySubstring = (r: RawRecord) => JSON.stringify(r).includes("Besar");
    const wronglyAcquitted = NO_BESAR.filter(bySubstring);
    expect(wronglyAcquitted).toHaveLength(23);
    expect(NO_BESAR.filter(hasUsahaBesarScale)).toHaveLength(0);
  });

  it("INNOCENCE: a Besar-bearing code at 100% stays green", () => {
    const open = RECORDS.find((r) => r.kode_kbli_2025 === "01111");
    expect(open, "01111 must exist in the catalogue").toBeDefined();
    expect(hasUsahaBesarScale(open!)).toBe(true);
    expect(publishedCap(open!)).toBe(100);
    expect(NO_BESAR).not.toContain(open!);

    // Not one lucky record: the rule must leave the whole open majority alone.
    // 1,266 and not the 1,265 that carry a literal `pma_max_asing: 100` — the
    // extra is 01122, the single record with no cap field at all, which
    // `resolvePmaCap` resolves to 100 from its TERBUKA status. Counting the
    // published figure rather than the stored one is the point of this guard.
    const besarAt100 = RECORDS.filter(
      (r) => hasUsahaBesarScale(r) && publishedCap(r) === 100,
    );
    expect(besarAt100.length).toBe(1266);
  });

  it("SCOPE: an empty scale matrix is never convicted", () => {
    expect(EMPTY_SCALE.every((r) => !NO_BESAR.includes(r))).toBe(true);
    const stillNonZero = EMPTY_SCALE.filter((r) => publishedCap(r) !== 0);
    expect(
      stillNonZero.length,
      "these keep their cap: the ruling does not reach a gap in our snapshot",
    ).toBe(164);
  });
});
