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

// Mirrors scripts/kbli_filiera/tests/test_pma_zero_cap_basis.py exactly — see that file
// for the full "why" behind every alternative, including the 2026-09-15 review findings
// 1-4 (finding 5, the cure_specs/ sweep, is Python-only: TS has no spec files to sweep).
// Naso PR-3 (2026-09-18) added the three statutory exits from openness the 59 relabelled
// closures cite — UU 25/2007 Pasal 12(2), Perpres Pasal 2(1)(b)/2(3), Pasal 2(1a).
const ANNEX_LOCATOR =
  /lampiran\s*ii\b|lampiran\s*iii\b|dialokasikan|pasal\s*2\b[^.\n]{0,80}?tertutup|tertutup[^.\n]{0,80}?pasal\s*2\b|daftar\s+bidang\s+usaha\s+(?:yang\s+)?tertutup|uu\s*25\/2007\s+pasal\s*12\(2\)|pasal\s*2\(1\)\(b\)|pasal\s*2\(3\)|pasal\s*2\(1a\)/i;

const SCALE_ABSENCE_BASIS =
  /PMA_CLOSED_NO_BESAR_SCALE|no\s+Usaha\s+Besar\s+scale|(?:tidak\s+ada|tanpa)\s+skala(?:\s+Usaha)?\s+Besar|skala(?:\s+Usaha)?\s+Besar\s+tidak\s+tersedia|no-Besar|no\s+(?:\*\*)?(?:Usaha Besar|large-scale)(?:\*\*)?[^.\n]{0,40}?\b(?:row|slot)\b|(?:non\s+offre\s+alcun[ao]|non\s+ha\s+un[ao]|nessun[ao]?)\s+(?:riga|fila|voce|slot)[^.\n]{0,60}?(?:larga scala|Usaha Besar)|tidak\s+(?:ada|memiliki|menawarkan|menyediakan)\s+(?:baris|slot)[^.\n]{0,60}?(?:skala besar|Usaha Besar)|only\s+(?:at\s+)?(?:Mikro|Micro)(?:\s*(?:\/|,|and|dan)\s*)?(?:Kecil|Small)?\s*(?:-\s*)?scale|hanya\s+(?:tersedia\s+)?(?:pada\s+)?skala\s+Mikro(?:\s*(?:\/|,|dan)\s*Kecil)?/i;

// Gates the TERTUTUP bare-citation bypass only (finding 1) — never a guilt trigger on
// its own, that would over-match the legitimate Pasal 26 language finding 4 protects.
const SCALE_MENTION = /\bscale\b|\bskala\b/i;

type Record = {
  kode_kbli_2025: string;
  pma_max_asing?: number | null;
  pma_status?: string | null;
  pma_kondisi?: string | null;
  pma_nota?: string | null;
  pma_source?: string | null;
  pma_official_basis?: string | null;
  pma_verification_status?: string | null;
};

function basisText(rec: Record): string {
  return [rec.pma_kondisi, rec.pma_nota, rec.pma_source, rec.pma_official_basis]
    .map((v) => v || "")
    .join(" || ");
}

function tertutupBareCitationOk(rec: Record): boolean {
  if (rec.pma_status !== "TERTUTUP" || rec.pma_official_basis) return false;
  if (!/perpres\s*10\/2021/i.test(rec.pma_source || "")) return false;
  const rationale = `${rec.pma_kondisi || ""} ${rec.pma_nota || ""}`;
  return !SCALE_MENTION.test(rationale);
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
  if (tertutupBareCitationOk(rec)) {
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

  it("INNOCENCE — a TERTUTUP code with a bare Perpres citation passes (20119)", () => {
    // 01287 was the exemplar until naso PR-3 located it under UU 25/2007
    // Pasal 12(2)(a); 20119 is the one TERTUTUP record still on the bare citation.
    const byCode = new Map(loadRows().map((r) => [r.kode_kbli_2025, r]));
    const rec = byCode.get("20119")!;
    expect(rec.pma_status).toBe("TERTUTUP");
    expect(rec.pma_official_basis ?? "").toBe("");
    const { ok, reason } = judge(rec);
    expect(ok, `20119: TERTUTUP closure wrongly refused (${reason})`).toBe(
      true,
    );
  });

  it("naso PR-3 INNOCENCE — the three statutory exits are locators (01287, 84111, 99000)", () => {
    const byCode = new Map(loadRows().map((r) => [r.kode_kbli_2025, r]));
    for (const code of ["01287", "84111", "99000"]) {
      const rec = byCode.get(code)!;
      expect(rec.pma_verification_status).toBe("located");
      const { ok, reason } = judge(rec);
      expect(ok, `${code}: statutory exit wrongly refused (${reason})`).toBe(
        true,
      );
    }
  });

  it("naso PR-3 GUILT — a Pasal 2(3) mention does not launder scale absence", () => {
    const { ok } = judge({
      kode_kbli_2025: "99003",
      pma_status: "TERTUTUP",
      pma_max_asing: 0,
      pma_official_basis:
        "Perpres 10/2021 Pasal 2(3) names government activities; this code is closed because OSS lists no Usaha Besar scale for it.",
      pma_source: "Perpres 10/2021, 49/2021",
    });
    expect(ok).toBe(false);
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

  // --- Review findings, 2026-09-15 (Codex GPT-5.6 sol xhigh) ---

  it("finding 1 GUILT — a TERTUTUP bare citation with a scale rationale is refused", () => {
    const rec: Record = {
      kode_kbli_2025: "99001",
      pma_status: "TERTUTUP",
      pma_max_asing: 0,
      pma_source: "Perpres 10/2021, 49/2021",
      pma_nota: "Hanya cocok untuk skala kecil menurut catatan OSS internal",
    };
    expect(tertutupBareCitationOk(rec)).toBe(false);
    const { ok, reason } = judge(rec);
    expect(
      ok,
      `scale-bearing TERTUTUP rationale wrongly accepted (${reason})`,
    ).toBe(false);
  });

  it("finding 1 INNOCENCE — a TERTUTUP bare citation without scale mention passes", () => {
    const rec: Record = {
      kode_kbli_2025: "99002",
      pma_status: "TERTUTUP",
      pma_max_asing: 0,
      pma_source: "Perpres 10/2021, 49/2021",
      pma_nota: "Perjudian dan pertaruhan",
    };
    expect(tertutupBareCitationOk(rec)).toBe(true);
    const { ok, reason } = judge(rec);
    expect(
      ok,
      `genuine Pasal 2 bare-citation wrongly refused (${reason})`,
    ).toBe(true);
  });

  it("finding 2 GUILT — widened wordings convict even beside an unrelated annex token", () => {
    const guiltyKondisi = [
      "Lampiran II lists this KBLI for an unrelated activity; here, the OSS system has " +
        "no large-scale row for this code, so it is closed to a PT PMA.",
      "Skala Usaha Besar tidak tersedia di OSS untuk kode ini (lihat juga Lampiran II " +
        "untuk kode lain) — tertutup bagi PMA.",
      "Only at Mikro/Kecil scale is this code registrable in OSS (cf. Lampiran III for a " +
        "sibling code); a PT PMA cannot enter.",
      "il sistema OSS non ha una voce per registrazioni su larga scala per questo codice " +
        "(si veda anche Lampiran II per un altro settore)",
    ];
    for (const kondisi of guiltyKondisi) {
      const rec: Record = {
        kode_kbli_2025: "x",
        pma_status: "TERBATAS",
        pma_max_asing: 0,
        pma_kondisi: kondisi,
        pma_source: "Perpres 10/2021, 49/2021",
      };
      const { ok, reason } = judge(rec);
      expect(
        ok,
        `scale-absence wording wrongly accepted: ${kondisi} (${reason})`,
      ).toBe(false);
    }
  });

  it("finding 2 INNOCENCE — a real Lampiran II row citation still passes", () => {
    const rec: Record = {
      kode_kbli_2025: "x",
      pma_status: "TERBATAS",
      pma_max_asing: 0,
      pma_official_basis:
        "Perpres 49/2021 Lampiran II (DIALOKASIKAN untuk Koperasi dan UMKM), p2, row " +
        '"Industri pemindangan ikan" — allocated to Koperasi/UMKM.',
      pma_source: "Perpres 10/2021, 49/2021",
    };
    const { ok, reason } = judge(rec);
    expect(
      ok,
      `real Lampiran II row citation wrongly refused (${reason})`,
    ).toBe(true);
  });

  it("finding 3 INNOCENCE — an explicit Pasal 2 closed-list locator passes", () => {
    const rec: Record = {
      kode_kbli_2025: "x",
      pma_status: "TERTUTUP",
      pma_max_asing: 0,
      pma_official_basis:
        "Perpres 10/2021 Pasal 2(2), daftar bidang usaha tertutup — closed to all " +
        "foreign and domestic private investment.",
      pma_source: "Perpres 10/2021, 49/2021",
    };
    const { ok, reason } = judge(rec);
    expect(
      ok,
      `explicit Pasal 2 closed-list locator wrongly refused (${reason})`,
    ).toBe(true);
  });

  it("finding 3 GUILT — a stray Pasal 2 mention does not launder scale absence", () => {
    const rec: Record = {
      kode_kbli_2025: "x",
      pma_status: "TERBATAS",
      pma_max_asing: 0,
      pma_official_basis:
        "Perpres 10/2021 Pasal 2 states the closed list in general terms; however this " +
        "code is closed here because OSS lists no Usaha Besar scale for it.",
      pma_source: "Perpres 10/2021, 49/2021",
    };
    const { ok, reason } = judge(rec);
    expect(
      ok,
      `stray Pasal 2 mention wrongly laundered scale absence (${reason})`,
    ).toBe(false);
  });

  it("finding 4 INNOCENCE — a Pasal 26 legal-fact note beside a real locator passes", () => {
    const rec: Record = {
      kode_kbli_2025: "x",
      pma_status: "TERBATAS",
      pma_max_asing: 0,
      pma_kondisi:
        "Bidang usaha dialokasikan untuk Koperasi dan UMKM (Perpres 49/2021 Lampiran II) " +
        "— foreign ownership 0%. Note: a PT PMA is Besar by law (BKPM 5/2025 Pasal " +
        "26(1)), a separate investor-eligibility condition, not the reason for this " +
        "reservation.",
      pma_source: "Perpres 10/2021, 49/2021",
    };
    const { ok, reason } = judge(rec);
    expect(
      ok,
      `legitimate Pasal 26 note beside a real locator wrongly refused (${reason})`,
    ).toBe(true);
  });
});
