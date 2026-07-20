// =============================================================================
// TRACK-P — provenance derivation tests
// Guilt + innocence corpus (cicatrix #3: a guard is never shipped without both)
// plus a real-dataset partition invariant so the state machine can't silently
// drift when the canonical is recompiled.
// =============================================================================

import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { deriveProvenance, getDisputedLicensing } from "./kbli-provenance";
import type { KBLIRawCode, KBLIRawDataFile } from "./kbli-types";

function makeRaw(overrides: Partial<KBLIRawCode> = {}): KBLIRawCode {
  return {
    kode_kbli_2025: "99999",
    judul: "Test Activity",
    uraian: "Test description",
    per_skala: [],
    sektor_id: "T",
    status_mapping: "MATCH_LANGSUNG",
    pp28_sources: ["99999"],
    pma_status: "TERBUKA",
    pma_max_asing: 100,
    pma_kondisi: null,
    pma_prioritas: false,
    pma_nota: null,
    pma_source: "Perpres 10/2021, 49/2021",
    _source: "BPS_7_2025 + PP28_2025",
    ...overrides,
  } as KBLIRawCode;
}

describe("deriveProvenance — state machine (guilt corpus)", () => {
  it("OSS-native L2 source → verified", () => {
    const prov = deriveProvenance(
      makeRaw({
        _l1_source: "OSS_RBA_2025",
        _l2_source: "OSS_RBA_resiko_2025",
      }),
    );
    expect(prov.state).toBe("verified");
    expect(prov.licensing.status).toBe("oss_native");
    expect(prov.licensing.vintage).toBe("2025");
    expect(prov.licensing.locator).toBe("OSS_RBA_resiko_2025");
  });

  it("no_oss_risk WITH served rows → pending crosswalk, vintage 2020", () => {
    const prov = deriveProvenance(
      makeRaw({
        _l2_status: "no_oss_risk",
        _l2_source: null,
        per_skala: [
          {
            skala_usaha: ["Mikro"],
            kategori_risiko: "Rendah",
            perizinan: [],
            persyaratan: [],
            jangka_waktu: "",
            kewajiban: [],
            pb_umku: [],
            parameter: "",
            kewenangan: "",
            sanksi_peringatan: "",
            sanksi_denda: "",
            sanksi_penghentian: "",
            sanksi_pencabutan: "",
            fiktif_positif: false,
          },
        ],
      }),
    );
    expect(prov.state).toBe("pending");
    expect(prov.licensing.status).toBe("pending_crosswalk");
    expect(prov.licensing.vintage).toBe("2020");
  });

  it("no_oss_risk with ZERO rows (special/sectoral regime) → pending, no row vintage", () => {
    const prov = deriveProvenance(
      makeRaw({ _l2_status: "no_oss_risk", _l2_source: null, per_skala: [] }),
    );
    expect(prov.state).toBe("pending");
    expect(prov.licensing.status).toBe("pending_crosswalk");
    // There is no served row to vintage — claiming "2020 rows" here would
    // assert rows that do not exist (Codex gate finding, 2026-07-17).
    expect(prov.licensing.vintage).toBeNull();
  });

  it("stale OSS-native L2 marker on a cured code loses to the disputed key (49213-class)", () => {
    // 49213/20111 carry _l2_source=OSS_RBA_resiko_2025 from before the cure
    // while their rows are detached — disputed MUST win the precedence or
    // they would render as verified with zero rows.
    const prov = deriveProvenance(
      makeRaw({
        _l2_source: "OSS_RBA_resiko_2025",
        _data_note: "collision",
        per_skala_disputed_pp28_collision: {
          per_skala: [{ kategori_risiko: "Menengah Tinggi" }],
        },
      }),
    );
    expect(prov.state).toBe("not_classifiable");
    expect(prov.licensing.status).toBe("detached");
  });

  it("disputed block (bare-array shape) → not_classifiable + rows surfaced", () => {
    const prov = deriveProvenance(
      makeRaw({
        _l2_status: "no_oss_risk",
        _data_note: "collision documented",
        per_skala_disputed_pp28_mice: [
          { skala_usaha: ["Mikro"], kategori_risiko: "Menengah Rendah" },
        ],
      }),
    );
    expect(prov.state).toBe("not_classifiable");
    expect(prov.licensing.status).toBe("detached");
    expect(prov.dataNote).toBe("collision documented");
    expect(prov.disputed?.key).toBe("per_skala_disputed_pp28_mice");
    expect(prov.disputed?.rows).toHaveLength(1);
  });

  it("disputed block ({per_skala: rows} shape) → rows normalized", () => {
    const disputed = getDisputedLicensing(
      makeRaw({
        per_skala_disputed_pp28_collision: {
          per_skala: [
            { kategori_risiko: "Tinggi" },
            { kategori_risiko: "Rendah" },
          ],
          per_skala_legacy: [],
        },
      }),
    );
    expect(disputed?.rows).toHaveLength(2);
    expect(disputed?.rows[0].kategori_risiko).toBe("Tinggi");
  });

  it("no markers at all → conservative pending, never verified", () => {
    const prov = deriveProvenance(makeRaw());
    expect(prov.state).toBe("pending");
  });

  it("unknown _l2_source value → pending with unverified_source, never verified, no invented vintage", () => {
    // Exact-marker discipline (Codex gates F4+F6): a future or mislabeled
    // source marker must degrade to pending WITHOUT claiming OSS verification,
    // a PP28-via-2020 provenance, or any vintage for the rows.
    const prov = deriveProvenance(
      makeRaw({ _l2_source: "SOME_FUTURE_SOURCE_2027" }),
    );
    expect(prov.state).toBe("pending");
    expect(prov.licensing.status).toBe("unverified_source");
    expect(prov.licensing.vintage).toBeNull();
    expect(prov.licensing.noOssScope).toBe(false);
  });

  it("unknown _l2_source ALONGSIDE no_oss_risk with served rows → still unverified_source, no 2020 vintage", () => {
    // Contradictory provenance (unknown marker + no_oss_risk + rows): the
    // unknown marker wins — claiming "PP28 via KBLI-2020" would invent a
    // vintage for rows whose declared source we cannot read (F6 round-3).
    const prov = deriveProvenance(
      makeRaw({
        _l2_source: "SOME_FUTURE_SOURCE_2027",
        _l2_status: "no_oss_risk",
        per_skala: [
          {
            skala_usaha: ["Mikro"],
            kategori_risiko: "Rendah",
            perizinan: [],
            persyaratan: [],
            jangka_waktu: "",
            kewajiban: [],
            pb_umku: [],
            parameter: "",
            kewenangan: "",
            sanksi_peringatan: "",
            sanksi_denda: "",
            sanksi_penghentian: "",
            sanksi_pencabutan: "",
            fiktif_positif: false,
          },
        ],
      }),
    );
    expect(prov.state).toBe("pending");
    expect(prov.licensing.status).toBe("unverified_source");
    expect(prov.licensing.vintage).toBeNull();
    // The 404 fact itself is still carried — it is a retrievability fact,
    // independent of the unreadable source marker.
    expect(prov.licensing.noOssScope).toBe(true);
  });
});

describe("deriveProvenance — innocence corpus", () => {
  it("collision-flavored PROSE on a verified record does not flip the state", () => {
    // The derivation must read structured markers only — a record whose text
    // mentions "collision"/"MICE"/"detached" is still verified when its L2
    // marker says OSS-native (cicatrix #3: no substring guards on prose).
    const prov = deriveProvenance(
      makeRaw({
        judul: "Penyewaan Venue MICE",
        uraian:
          "This activity text mentions code-number collision and detached rows and MICE venues.",
        _l2_source: "OSS_RBA_resiko_2025",
      }),
    );
    expect(prov.state).toBe("verified");
    expect(prov.disputed).toBeNull();
  });

  it("a legitimate no-scope neighbor (no disputed key) stays pending, not not_classifiable", () => {
    const prov = deriveProvenance(
      makeRaw({ _l2_status: "no_oss_risk", _data_note: undefined }),
    );
    expect(prov.state).toBe("pending");
  });

  it("PMA layer is a vintage disclosure on every state, source passed through", () => {
    const prov = deriveProvenance(
      makeRaw({ _l2_source: "OSS_RBA_resiko_2025" }),
    );
    expect(prov.pma.vintage).toBe("2020");
    expect(prov.pma.source).toBe("Perpres 10/2021, 49/2021");
  });
});

describe("deriveProvenance — real dataset partition invariants", () => {
  const DATA_PATH = path.join(
    process.cwd(),
    "data",
    "KBLI_2025_FINAL_CLEAN.json",
  );
  const parsed = JSON.parse(
    fs.readFileSync(DATA_PATH, "utf-8"),
  ) as KBLIRawDataFile;

  it("every record lands in exactly one state; disputed ⇒ not_classifiable ∧ note", () => {
    let verified = 0;
    let pending = 0;
    let notClassifiable = 0;
    for (const raw of parsed.data) {
      const prov = deriveProvenance(raw);
      if (prov.state === "verified") verified++;
      else if (prov.state === "pending") pending++;
      else notClassifiable++;
      const hasDisputedKey = Object.keys(raw).some((k) =>
        k.startsWith("per_skala_disputed_"),
      );
      if (hasDisputedKey) {
        expect(prov.state).toBe("not_classifiable");
        // A detach without its honest-gap note would be a silent gap — the
        // cure compiler always writes both.
        expect(prov.dataNote).toBeTruthy();
        expect(prov.disputed?.rows.length).toBeGreaterThan(0);
      }
    }
    expect(verified + pending + notClassifiable).toBe(parsed.data.length);
    // The cured-pilot set can only grow (batch A remainder) — never shrink
    // below the 8 proven collision cures, and verified codes must dominate.
    expect(notClassifiable).toBeGreaterThanOrEqual(8);
    expect(verified).toBeGreaterThan(1000);
  });

  it("ALL 8 cured pilot codes derive not_classifiable (every cause subtype)", () => {
    // The full pilot set — digit collisions (68112, 51103, 51203, 50115),
    // authority-level collision (49213), many-to-one merge (20111),
    // wrong-pointer transplant (64310), unlocatable source (60312). The
    // class handling must hold for every subtype, not just collisions.
    const byCode = new Map(parsed.data.map((r) => [r.kode_kbli_2025, r]));
    for (const code of [
      "68112",
      "49213",
      "51103",
      "51203",
      "20111",
      "50115",
      "60312",
      "64310",
    ]) {
      const raw = byCode.get(code);
      expect(raw, `code ${code} missing from dataset`).toBeTruthy();
      const prov = deriveProvenance(raw!);
      expect(prov.state, `code ${code}`).toBe("not_classifiable");
      expect(prov.dataNote, `code ${code} note`).toBeTruthy();
      expect(
        prov.disputed?.rows.length,
        `code ${code} disputed rows`,
      ).toBeGreaterThan(0);
    }
  });
});
