import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * No whole-code 0% foreign-ownership verdict on the mouth copy of the canonical dataset
 * may rest on a missing Usaha Besar scale (PR #6488, never merged — see
 * DOSSIER-no-besar-normativo-2026-09-15.md).
 *
 * TWIN of `scripts/kbli_filiera/tests/test_pma_zero_cap_basis.py` — same predicate, same
 * regexes, same guilt fixture (the #6488 patch actually written to `73300`/`38110` on
 * branch `5535726236`), read against `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json`
 * (byte-identical to canonical, verified via `cmp` before this test was written) because
 * that is the copy this app serves. See the Python file for the full "why": the
 * l4_bali-vs-pma_* scope decision and why a bare `per_skala` trigger is excluded.
 */

const DATA_PATH = path.join(
  process.cwd(),
  "data",
  "KBLI_2025_FINAL_CLEAN.json",
);

const ANNEX_LOCATOR = /lampiran\s*ii\b|lampiran\s*iii\b|dialokasikan/i;

const SCALE_ABSENCE_BASIS =
  /PMA_CLOSED_NO_BESAR_SCALE|no\s+Usaha\s+Besar\s+scale|(?:tidak\s+ada|tanpa)\s+skala(?:\s+Usaha)?\s+Besar|no-Besar|PMA\s+is\s+Besar\s+by\s+law/i;

type Record = {
  kode_kbli_2025: string;
  pma_max_asing?: number | null;
  pma_status?: string | null;
  pma_kondisi?: string | null;
  pma_nota?: string | null;
  pma_source?: string | null;
  pma_official_basis?: string | null;
};

function basisText(rec: Record): string {
  return [rec.pma_kondisi, rec.pma_nota, rec.pma_source, rec.pma_official_basis]
    .map((v) => v || "")
    .join(" || ");
}

function judge(rec: Record): { ok: boolean; reason: string } {
  if (rec.pma_max_asing !== 0) return { ok: true, reason: "not a 0% verdict" };
  const text = basisText(rec);
  if (SCALE_ABSENCE_BASIS.test(text)) {
    return {
      ok: false,
      reason: `basis argues from scale absence: ${text.slice(0, 200)}`,
    };
  }
  if (ANNEX_LOCATOR.test(text))
    return { ok: true, reason: "annex locator present" };
  if (
    rec.pma_status === "TERTUTUP" &&
    !rec.pma_official_basis &&
    /perpres\s*10\/2021/i.test(rec.pma_source || "")
  ) {
    return {
      ok: true,
      reason: "TERTUTUP bare Perpres 10/2021 citation (Pasal 2 closed-list)",
    };
  }
  return {
    ok: false,
    reason: `no annex/closed-list locator named: ${text.slice(0, 200)}`,
  };
}

function loadRows(): Record[] {
  const parsed = JSON.parse(fs.readFileSync(DATA_PATH, "utf-8"));
  return parsed.data as Record[];
}

describe("no 0% PMA verdict in the mouth dataset copy cites a missing scale row", () => {
  it("reads a store that is actually there", () => {
    expect(fs.existsSync(DATA_PATH)).toBe(true);
    expect(loadRows().length).toBe(1559);
  });

  it("every 0% verdict on this branch passes today", () => {
    const rows = loadRows();
    const zero = rows.filter((r) => r.pma_max_asing === 0);
    expect(zero.length).toBeGreaterThan(0);
    const offenders = zero
      .map((r) => ({ code: r.kode_kbli_2025, ...judge(r) }))
      .filter((r) => !r.ok);
    expect(offenders, JSON.stringify(offenders)).toEqual([]);
  });

  it("GUILT — refuses the #6488 patch verbatim (73300, 38110)", () => {
    const kondisi =
      "No Usaha Besar scale in OSS for this code and a PT PMA must be an Usaha Besar — " +
      "foreign ownership 0% / Tidak ada skala Usaha Besar di OSS untuk KBLI ini, sedangkan " +
      "PMA wajib Usaha Besar — kepemilikan asing 0% (Perpres 10/2021 Pasal 7(1); " +
      "Permeninves/BKPM 5/2025 Pasal 26(1))";
    const nota =
      "PMA_CLOSED_NO_BESAR_SCALE: closed to PT PMA, no Usaha Besar scale / tertutup bagi " +
      "PMA, tanpa skala Usaha Besar";
    const source =
      "Perpres 10/2021 Pasal 7(1); Permeninves/BKPM 5/2025 Pasal 26(1) (retrieved 2026-09-14)";
    const officialBasis =
      "Perpres 10/2021 (as amended by Perpres 49/2021) Pasal 7 ayat (1) — a foreign investor " +
      "may carry on business only as an Usaha Besar. OSS publishes no Usaha Besar scale for " +
      "this KBLI 2025 code, so a PT PMA cannot operate it; max foreign 0% " +
      "[PMA_CLOSED_NO_BESAR_SCALE, owner ruling 2026-09-14].";
    for (const code of ["73300", "38110"]) {
      const patched: Record = {
        kode_kbli_2025: code,
        pma_status: "TERBATAS",
        pma_max_asing: 0,
        pma_kondisi: kondisi,
        pma_nota: nota,
        pma_source: source,
        pma_official_basis: officialBasis,
      };
      const { ok, reason } = judge(patched);
      expect(ok, `${code}: must be refused, was accepted (${reason})`).toBe(
        false,
      );
    }
  });

  it("INNOCENCE — the certified Lampiran II codes pass (95291, 96100, 96210, 96220)", () => {
    const byCode = new Map(loadRows().map((r) => [r.kode_kbli_2025, r]));
    for (const code of ["95291", "96100", "96210", "96220"]) {
      const rec = byCode.get(code)!;
      expect(rec.pma_max_asing, `${code}: fixture assumption drifted`).toBe(0);
      const { ok, reason } = judge(rec);
      expect(
        ok,
        `${code}: certified allocation wrongly refused (${reason})`,
      ).toBe(true);
    }
  });

  it("INNOCENCE — a TERTUTUP code with a bare Perpres citation passes (01287)", () => {
    const byCode = new Map(loadRows().map((r) => [r.kode_kbli_2025, r]));
    const rec = byCode.get("01287")!;
    expect(rec.pma_status).toBe("TERTUTUP");
    const { ok, reason } = judge(rec);
    expect(ok, `01287: TERTUTUP closure wrongly refused (${reason})`).toBe(
      true,
    );
  });

  it("INNOCENCE — a Lampiran III code passes (16221)", () => {
    const byCode = new Map(loadRows().map((r) => [r.kode_kbli_2025, r]));
    const rec = byCode.get("16221")!;
    expect(rec.pma_official_basis || "").toContain("Lampiran III");
    const { ok, reason } = judge(rec);
    expect(ok, `16221: Lampiran III basis wrongly refused (${reason})`).toBe(
      true,
    );
  });

  it("does not fire on a legitimate Pasal 26 investment-threshold mention", () => {
    const sentence =
      "Perpres 10/2021 Pasal 7(1) and BKPM 5/2025 Pasal 26(1) require a foreign investor " +
      "to invest as Usaha Besar, above Rp10 miliar per KBLI — a condition on the investor, " +
      "not a closure of the activity.";
    expect(SCALE_ABSENCE_BASIS.test(sentence)).toBe(false);
  });
});
