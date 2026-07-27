import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import { resolvePmaCap } from "./kbli-pma-cap";
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";

interface RawRecord {
  kode_kbli_2025: string;
  pma_status?: string;
  pma_max_asing?: number | string;
}

const RECORDS = (rawData as { data: RawRecord[] }).data;
const HERE = dirname(fileURLToPath(import.meta.url));

describe("resolvePmaCap — the record's adjudicated figure, never a coerced 0", () => {
  it("GUILT: an open code with no cap field is 100%, not 0% (01122)", () => {
    const record = RECORDS.find((r) => r.kode_kbli_2025 === "01122");
    expect(record, "01122 must exist in the catalogue").toBeDefined();
    expect(
      record!.pma_max_asing,
      "01122 is the one record with no cap field",
    ).toBeUndefined();
    expect(record!.pma_status).toBe("TERBUKA");

    // The old expression, applied to the real record: `|| 0` turned "absent"
    // into "0", and the page rendered "0% Open" on a fully-open activity.
    const legacy = record!.pma_max_asing || 0;
    expect(legacy).toBe(0);
    expect(resolvePmaCap(record!)).toBe(100);
  });

  it("GUILT: exactly one record in the catalogue could hit that coercion", () => {
    const coerced = RECORDS.filter(
      (r) => (r.pma_max_asing ?? 0) === 0 && r.pma_status === "TERBUKA",
    );
    expect(coerced.map((r) => r.kode_kbli_2025)).toEqual(["01122"]);
  });

  it("INNOCENCE: an adjudicated figure passes through untouched", () => {
    expect(resolvePmaCap({ pma_status: "TERBATAS", pma_max_asing: 49 })).toBe(
      49,
    );
    expect(resolvePmaCap({ pma_status: "TERBUKA", pma_max_asing: 100 })).toBe(
      100,
    );
    expect(resolvePmaCap({ pma_status: "TERTUTUP", pma_max_asing: 0 })).toBe(0);
  });

  it("INNOCENCE: a real 0% cap stays 0 — the fix must not invent openness", () => {
    // 47111 is reserved for K-UMKM: 0% is the TRUE figure, not a coercion.
    const record = RECORDS.find((r) => r.kode_kbli_2025 === "47111")!;
    expect(record.pma_max_asing).toBe(0);
    expect(resolvePmaCap(record)).toBe(0);
  });

  it("INNOCENCE: the non-percentage regime survives as 'special'", () => {
    const record = RECORDS.find((r) => r.kode_kbli_2025 === "47221")!;
    expect(resolvePmaCap(record)).toBe("special");
  });

  it("accepts a numeric string without turning it into NaN", () => {
    expect(
      resolvePmaCap({ pma_status: "TERBATAS", pma_max_asing: " 67 " }),
    ).toBe(67);
  });

  it("falls back to the status only at its two unambiguous extremes", () => {
    expect(resolvePmaCap({ pma_status: "TERBUKA" })).toBe(100);
    expect(resolvePmaCap({ pma_status: "TERTUTUP" })).toBe(0);
    // TERBATAS spans 0/49/100/special: no figure may be invented for it.
    expect(resolvePmaCap({ pma_status: "TERBATAS" })).toBe("special");
  });

  it("survives a null/undefined record without asserting 0%", () => {
    expect(resolvePmaCap(null)).toBe("special");
    expect(resolvePmaCap(undefined)).toBe("special");
  });
});

describe("population — every one of the 1,559 codes", () => {
  it("never contradicts the figure on the record", () => {
    const mismatches = RECORDS.filter(
      (r) =>
        typeof r.pma_max_asing === "number" &&
        resolvePmaCap(r) !== r.pma_max_asing,
    ).map((r) => r.kode_kbli_2025);
    expect(mismatches).toEqual([]);
  });

  it("resolves to a percentage in [0,100] or to a declared 'special'", () => {
    for (const record of RECORDS) {
      const cap = resolvePmaCap(record);
      const ok =
        cap === "special" ||
        (typeof cap === "number" && cap >= 0 && cap <= 100);
      expect(ok, `${record.kode_kbli_2025} -> ${String(cap)}`).toBe(true);
    }
  });

  it("the no-honest-number guard is a guard, not a live code path", () => {
    // A limited code carrying no cap would fall through to "special". None
    // exists today; if one appears, this test says so before a page does.
    const wouldFallThrough = RECORDS.filter(
      (r) => r.pma_status === "TERBATAS" && r.pma_max_asing === undefined,
    );
    expect(wouldFallThrough.map((r) => r.kode_kbli_2025)).toEqual([]);
  });
});

describe("one rule, one module — the two readers cannot drift apart again", () => {
  const SERVER = readFileSync(join(HERE, "kbli-data.server.ts"), "utf8");
  const CLIENT = readFileSync(join(HERE, "kbli-data.ts"), "utf8");

  it("neither data layer reads the raw cap field directly any more", () => {
    for (const [name, source] of [
      ["kbli-data.server.ts", SERVER],
      ["kbli-data.ts", CLIENT],
    ] as const) {
      expect(source, `${name} must not re-derive the cap`).not.toMatch(
        /maxForeign:\s*raw\.pma_max_asing/,
      );
      expect(source, `${name} must call the shared resolver`).toContain(
        "maxForeign: resolvePmaCap(raw)",
      );
    }
  });
});
