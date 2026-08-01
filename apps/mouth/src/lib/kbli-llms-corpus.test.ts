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
  riskLabel,
  UNCLASSIFIED_RISK,
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
      capLabel(rec({ pma_status: "TERBATAS", pma_max_asing: "special" })),
    ).toBe("special");
  });

  it("INNOCENCE: an open code with no cap field is still 100%", () => {
    // 01122 is the one record in the catalogue carrying no cap. It is TERBUKA,
    // so 100 is the right answer and this cure must not move it.
    expect(
      capLabel(rec({ pma_status: "TERBUKA", pma_max_asing: undefined })),
    ).toBe("100%");
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

  it("states no foreign cap the canonical contradicts", () => {
    // A property rather than a byte-comparison, so it still means something if
    // the format is ever reshaped: every published cap must be the resolved
    // one, and in particular no closed code may read as open.
    const published = new Map<string, string>();
    for (const line of readFileSync(COMMITTED, "utf8").split("\n")) {
      if (!/^\d{5} \| /.test(line)) continue;
      const parts = line.split(" | ");
      published.set(parts[0], parts[3]);
    }
    const wrong = RECORDS.filter(
      (r) => published.get(r.kode_kbli_2025 ?? "") !== capLabel(r),
    ).map((r) => r.kode_kbli_2025);
    expect(wrong).toEqual([]);
    // and the corpus really does carry closed codes as 0% — guards against the
    // assertion above passing vacuously on an empty or unparsed file
    expect([...published.values()].filter((c) => c === "0%").length).toBe(
      RECORDS.filter((r) => capLabel(r) === "0%").length,
    );
    expect(published.size).toBe(RECORDS.length);
  });
});
