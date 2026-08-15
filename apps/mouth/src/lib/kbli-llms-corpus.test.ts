/**
 * The corpus written for machines, and the pin that stops it going stale.
 *
 * `public/llms-kbli.txt` is a COMMITTED artifact: `package.json` runs the
 * generator as `LLMS_GENERATE_FULL_ONLY=1`, and that flag returns before the
 * KBLI section, so no build regenerates it. It was last written on 2026-07-07
 * and had drifted through every dataset correction since. The last test in this
 * file is what makes that impossible to repeat quietly — a compiler that writes
 * the canonical and leaves its derivatives stale is a half-cure.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";

import {
  buildKbliCorpus,
  capLabel,
  pmaColumns,
  riskLabel,
  UNCLASSIFIED_RISK,
  UNVERIFIED_PMA_CAP,
  UNVERIFIED_PMA_STATUS,
  type CorpusRecord,
} from "./kbli-llms-corpus";
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";

const RECORDS = (rawData as { data: CorpusRecord[] }).data;
const HERE = dirname(fileURLToPath(import.meta.url));
const COMMITTED = join(HERE, "..", "..", "public", "llms-kbli.txt");

const rec = (over: Partial<CorpusRecord> = {}): CorpusRecord => ({
  kode_kbli_2025: "62010",
  judul: "x",
  pma_status: "TERBUKA",
  pma_max_asing: 100,
  pma_verification_status: "located",
  pma_official_basis: "Perpres 10/2021 Lampiran III",
  pma_source_vintage: "2021-05-25",
  pma_cap_verified: true,
  ...over,
});

describe("the cap", () => {
  it("GUILT: 0% is published as 0%, not as 100%", () => {
    // `c.pma_max_asing || 100` published `11010` (alcohol distilling, TERTUTUP)
    // as 100% open to foreign ownership.
    expect(capLabel(rec({ pma_status: "TERTUTUP", pma_max_asing: 0 }))).toBe(
      "0%",
    );
  });

  it("a non-percentage regime stays a word, never an invented number", () => {
    expect(
      capLabel(
        rec({
          pma_status: "TERBATAS",
          pma_max_asing: "special",
          pma_cap_special: true,
        }),
      ),
    ).toBe("special");
  });

  it("withholds a missing or unverified cap without inferring 100%", () => {
    expect(
      capLabel(rec({ pma_status: "TERBUKA", pma_max_asing: undefined })),
    ).toBe(UNVERIFIED_PMA_CAP);
    expect(capLabel(rec({ pma_max_asing: 49, pma_cap_verified: false }))).toBe(
      UNVERIFIED_PMA_CAP,
    );
  });

  it.each(["49", true, Number.POSITIVE_INFINITY])(
    "rejects malformed runtime cap %p",
    (pma_max_asing) => {
      expect(capLabel(rec({ pma_max_asing: pma_max_asing as never }))).toBe(
        UNVERIFIED_PMA_CAP,
      );
    },
  );

  it("requires the special marker as well as cap verification", () => {
    expect(
      capLabel(
        rec({
          pma_status: "TERBATAS",
          pma_max_asing: "special",
          pma_cap_special: false,
        }),
      ),
    ).toBe(UNVERIFIED_PMA_CAP);
  });
});

describe("the risk column", () => {
  it("GUILT: an unclassified code is not published as low risk", () => {
    expect(riskLabel(rec({ per_skala: [] }))).toBe(UNCLASSIFIED_RISK);
    expect(riskLabel(rec({ per_skala: undefined }))).toBe(UNCLASSIFIED_RISK);
  });

  it("GUILT: a code whose scales disagree lists every tier, not the first", () => {
    const r = rec({
      per_skala: [
        { kategori_risiko: "Rendah" },
        { kategori_risiko: "Menengah Tinggi" },
        { kategori_risiko: "Rendah" },
      ],
    });
    expect(riskLabel(r)).toBe("Rendah / Menengah Tinggi");
  });

  it("INNOCENCE: a code whose scales agree reads as one plain tier", () => {
    const r = rec({
      per_skala: [{ kategori_risiko: "Tinggi" }, { kategori_risiko: "Tinggi" }],
    });
    expect(riskLabel(r)).toBe("Tinggi");
  });
});

describe("the row", () => {
  it("refuses to publish a guessed status", () => {
    expect(() => buildKbliCorpus([rec({ pma_status: undefined })])).toThrow(
      /no pma_status/,
    );
  });

  it("emits one line per record after the header", () => {
    const body = buildKbliCorpus([
      rec({ kode_kbli_2025: "62010", judul: "Software" }),
    ]);
    expect(body).toContain(
      "62010 | Software | TERBUKA | 100% | Not classified\n",
    );
  });

  it("GUILT: withholds a declared-gap PMA status and cap", () => {
    const gap = rec({
      kode_kbli_2025: "01111",
      pma_verification_status: "declared_gap",
      pma_official_basis: undefined,
      pma_source_vintage: undefined,
    });

    expect(pmaColumns(gap)).toEqual({
      status: UNVERIFIED_PMA_STATUS,
      cap: UNVERIFIED_PMA_CAP,
    });
    expect(buildKbliCorpus([gap])).toContain(
      "01111 | x | NOT_VERIFIED | Not verified | Not classified\n",
    );
    expect(buildKbliCorpus([gap])).not.toContain("TERBUKA | 100%");
  });

  it("fails closed when located provenance is incomplete", () => {
    expect(pmaColumns(rec({ pma_official_basis: "   " }))).toEqual({
      status: UNVERIFIED_PMA_STATUS,
      cap: UNVERIFIED_PMA_CAP,
    });
    expect(pmaColumns(rec({ pma_source_vintage: undefined }))).toEqual({
      status: UNVERIFIED_PMA_STATUS,
      cap: UNVERIFIED_PMA_CAP,
    });
  });

  it("fails closed when a located row carries an unknown PMA status token", () => {
    const future = rec({ pma_status: "FUTURE_STATUS" });

    expect(pmaColumns(future)).toEqual({
      status: UNVERIFIED_PMA_STATUS,
      cap: UNVERIFIED_PMA_CAP,
    });
    expect(buildKbliCorpus([future])).not.toContain("FUTURE_STATUS | 100%");
  });
});

describe("the committed artifact", () => {
  it("is exactly what the current dataset produces", () => {
    // THE POINT OF THIS FILE. `public/llms-kbli.txt` is served at
    // balizero.com/llms-kbli.txt and no build regenerates it, so without this
    // pin it silently drifts from the canonical — as it did, for four weeks.
    // REMEDIATION when this fails: `npx tsx scripts/generate-llms-full.ts`
    // (without LLMS_GENERATE_FULL_ONLY=1, which returns before this section),
    // then commit the regenerated file.
    expect(readFileSync(COMMITTED, "utf8")).toBe(buildKbliCorpus(RECORDS));
  });

  it("states no unverified or contradictory foreign cap", () => {
    // A property rather than a byte-comparison, so it still means something if
    // the format is ever reshaped: every published cap must be the resolved
    // one, and in particular no closed code may read as open.
    const published = new Map<string, { status: string; cap: string }>();
    for (const line of readFileSync(COMMITTED, "utf8").split("\n")) {
      if (!/^\d{5} \| /.test(line)) continue;
      const parts = line.split(" | ");
      published.set(parts[0], { status: parts[2], cap: parts[3] });
    }
    const wrong = RECORDS.filter((r) => {
      const expected = pmaColumns(r);
      const actual = published.get(r.kode_kbli_2025 ?? "");
      return actual?.status !== expected.status || actual?.cap !== expected.cap;
    }).map((r) => r.kode_kbli_2025);
    expect(wrong).toEqual([]);
    // The corpus really carries every verified closed code as 0%, while every
    // declared gap withholds both raw ownership columns.
    expect([...published.values()].filter((p) => p.cap === "0%").length).toBe(
      RECORDS.filter((r) => pmaColumns(r).cap === "0%").length,
    );
    expect(
      [...published.values()].filter(
        (p) =>
          p.status === UNVERIFIED_PMA_STATUS && p.cap === UNVERIFIED_PMA_CAP,
      ).length,
    ).toBe(
      RECORDS.filter((r) => pmaColumns(r).status === UNVERIFIED_PMA_STATUS)
        .length,
    );
    expect(published.size).toBe(RECORDS.length);
  });
});
