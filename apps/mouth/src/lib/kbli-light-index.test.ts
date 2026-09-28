import { gzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { getAllCodes } from "./kbli-data";
import { isPmaVerdictVerified } from "./kbli-provenance";
import { searchCodes } from "./kbli-search";
import { buildKbliLightIndex, lightRowsToSearchable } from "./kbli-light-index";

// BRIEF-v2 §3.4: the client index is wired only if it gzips to ≤ 150 KB
// (decimal, the stricter reading).
const BUDGET_GZIP_BYTES = 150_000;

describe("KBLI light index", () => {
  const codes = getAllCodes();
  const rows = buildKbliLightIndex(codes);
  const json = JSON.stringify(rows);

  it("fits the 150 KB gzip budget on the real dataset", () => {
    const gz = gzipSync(json).length;
    // Printed so the measured figure is on the record of every run.
    console.info(
      `[kbli-light-index] rows=${rows.length} raw=${json.length}B gzip=${gz}B budget=${BUDGET_GZIP_BYTES}B`,
    );
    expect(gz).toBeLessThanOrEqual(BUDGET_GZIP_BYTES);
  });

  it("carries one row per served code", () => {
    expect(rows.length).toBe(codes.length);
    expect(new Set(rows.map((r) => r.c)).size).toBe(codes.length);
  });

  it("carries an ownership figure only where the verdict AND the cap are verified", () => {
    const byCode = new Map(codes.map((c) => [c.code, c]));
    for (const row of rows) {
      const code = byCode.get(row.c)!;
      if (row.f !== undefined) {
        expect(isPmaVerdictVerified(code)).toBe(true);
        expect(code.pma.capVerified).toBe(true);
        expect(code.pma.maxForeign).toBe(row.f);
      }
      if (!isPmaVerdictVerified(code)) expect(row.p).toBeUndefined();
    }
  });

  it("answers an exact code through the unchanged searchCodes", () => {
    const target = codes[0].code;
    const hits = searchCodes(lightRowsToSearchable(rows), target);
    expect(hits[0]?.code.code).toBe(target);
  });
});
