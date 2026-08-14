// =============================================================================
// TRACK-P — provenance derivation tests
// Guilt + innocence corpus (cicatrix #3: a guard is never shipped without both)
// plus a real-dataset partition invariant so the state machine can't silently
// drift when the canonical is recompiled.
// =============================================================================

import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import {
  deriveProvenance,
  getDisputedLicensing,
  isBaliL4BlockVerifiedForBareClaim,
  isLicensingVerifiedForBareClaim,
  licensingContentInheritedFrom,
  pp28ContentInheritedFrom,
} from "./kbli-provenance";
import type {
  KBLICode,
  KBLILicensingProvenanceStatus,
  KBLIProvenance,
  KBLIRawCode,
  KBLIRawDataFile,
} from "./kbli-types";

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

  it("PMA provenance is independent of licensing state and passes through only an explicit locator + vintage", () => {
    const prov = deriveProvenance(
      makeRaw({
        _l2_source: "OSS_RBA_resiko_2025",
        pma_verification_status: "located",
        pma_official_basis: "Perpres 49/2021 Lampiran III fixture",
        pma_source_vintage: "2021-05-25",
      }),
    );
    expect(prov.pma.status).toBe("located");
    expect(prov.pma.vintage).toBe("2021-05-25");
    expect(prov.pma.source).toBe("Perpres 10/2021, 49/2021");
    expect(prov.pma.locator).toBe("Perpres 49/2021 Lampiran III fixture");
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

describe("deriveProvenance — PMA verification gate (guilt + innocence)", () => {
  it("GUILT: a legacy value and crosswalk ancestry cannot verify a verdict", () => {
    const prov = deriveProvenance(
      makeRaw({
        bps_2020_ancestors: {
          codes: ["01111"],
          adjudication_status: "not-adjudicated",
          inheritance_verdict: "not-adjudicated",
        },
      }),
    );
    expect(prov.pma.status).toBe("declared_gap");
    expect(prov.pma.locator).toBeNull();
    expect(prov.pma.vintage).toBeNull();
  });

  it("GUILT: located without locator or vintage fails closed", () => {
    const missingLocator = deriveProvenance(
      makeRaw({
        pma_verification_status: "located",
        pma_source_vintage: "2021-05-25",
      }),
    );
    const missingVintage = deriveProvenance(
      makeRaw({
        pma_verification_status: "located",
        pma_official_basis: "Perpres 49/2021 Lampiran III",
      }),
    );
    expect(missingLocator.pma.status).toBe("declared_gap");
    expect(missingVintage.pma.status).toBe("declared_gap");
  });

  it("INNOCENCE: explicit located + locator + vintage verifies the verdict", () => {
    const prov = deriveProvenance(
      makeRaw({
        pma_verification_status: "located",
        pma_official_basis: "Perpres 49/2021 Lampiran III baris 7",
        pma_source_vintage: "2021-05-25",
      }),
    );
    expect(prov.pma).toMatchObject({
      status: "located",
      locator: "Perpres 49/2021 Lampiran III baris 7",
      vintage: "2021-05-25",
    });
  });

  it("GUILT: an explicit declared gap cannot be promoted by stray fields", () => {
    const prov = deriveProvenance(
      makeRaw({
        pma_verification_status: "declared_gap",
        pma_official_basis: "stray locator",
        pma_source_vintage: "2021-05-25",
      }),
    );
    expect(prov.pma.status).toBe("declared_gap");
    expect(prov.pma.locator).toBeNull();
    expect(prov.pma.vintage).toBeNull();
  });
});

describe("deriveProvenance — PMA traceability on the real dataset", () => {
  const DATA_PATH = path.join(
    process.cwd(),
    "data",
    "KBLI_2025_FINAL_CLEAN.json",
  );
  const parsed = JSON.parse(
    fs.readFileSync(DATA_PATH, "utf-8"),
  ) as KBLIRawDataFile;

  it("pins the canonical honesty partition: 54 located, 1,505 gaps", () => {
    const located = parsed.data.filter(
      (r) => deriveProvenance(r).pma.status === "located",
    );
    const gaps = parsed.data.filter(
      (r) => deriveProvenance(r).pma.status === "declared_gap",
    );
    expect(located).toHaveLength(54);
    expect(gaps).toHaveLength(1505);
    for (const r of located) {
      const prov = deriveProvenance(r).pma;
      expect(prov.locator, `code ${r.kode_kbli_2025}`).toBeTruthy();
      expect(prov.vintage, `code ${r.kode_kbli_2025}`).toBeTruthy();
    }
  });
});

// =============================================================================
// Bare-claim gates (2026-07-26) — the POSITIVE complement used by surfaces that
// cannot carry a "verification pending" qualifier (indexed <title>/meta).
// The distinction under test is precisely the one a negative gate gets wrong:
// a record with NO provenance block must be false, not true.
// =============================================================================

describe("bare-claim gates", () => {
  function codeWith(
    licensing: KBLICode["licensing"],
    provenance?: KBLIProvenance,
    baliL4?: KBLICode["baliL4"],
  ): KBLICode {
    return { licensing, provenance, baliL4 } as KBLICode;
  }

  const rows = [{ riskCategory: "Tinggi" }] as KBLICode["licensing"];

  function prov(status: KBLILicensingProvenanceStatus): KBLIProvenance {
    return {
      licensing: { status, locator: null, vintage: null, noOssScope: false },
    } as KBLIProvenance;
  }

  it("licensing: true ONLY for oss_native with rows served", () => {
    expect(
      isLicensingVerifiedForBareClaim(codeWith(rows, prov("oss_native"))),
    ).toBe(true);
  });

  it("licensing: false for pending_crosswalk, unverified_source, detached", () => {
    for (const s of [
      "pending_crosswalk",
      "unverified_source",
      "detached",
    ] as KBLILicensingProvenanceStatus[]) {
      expect(
        isLicensingVerifiedForBareClaim(codeWith(rows, prov(s))),
        `status ${s}`,
      ).toBe(false);
    }
  });

  it("licensing: false when the provenance block is absent (fail closed)", () => {
    expect(isLicensingVerifiedForBareClaim(codeWith(rows, undefined))).toBe(
      false,
    );
  });

  it("licensing: false when oss_native but no rows are actually served", () => {
    expect(
      isLicensingVerifiedForBareClaim(
        codeWith([] as KBLICode["licensing"], prov("oss_native")),
      ),
    ).toBe(false);
  });

  it("baliL4: true only for blocked + HIGH + not needing review", () => {
    const l4 = (
      confidence: "HIGH" | "MEDIUM" | "LOW",
      needsReview: boolean,
      blocked = true,
    ) =>
      ({
        status: "CHIUSO_PMA_NO_BESAR",
        reason: "r",
        confidence,
        needsReview,
        blocked,
      }) as KBLICode["baliL4"];

    expect(
      isBaliL4BlockVerifiedForBareClaim(
        codeWith(rows, undefined, l4("HIGH", false)),
      ),
    ).toBe(true);
    expect(
      isBaliL4BlockVerifiedForBareClaim(
        codeWith(rows, undefined, l4("HIGH", true)),
      ),
    ).toBe(false);
    expect(
      isBaliL4BlockVerifiedForBareClaim(
        codeWith(rows, undefined, l4("MEDIUM", false)),
      ),
    ).toBe(false);
    expect(
      isBaliL4BlockVerifiedForBareClaim(
        codeWith(rows, undefined, l4("HIGH", false, false)),
      ),
    ).toBe(false);
    expect(
      isBaliL4BlockVerifiedForBareClaim(codeWith(rows, undefined, undefined)),
    ).toBe(false);
  });
});

// =============================================================================
// licensingContentInheritedFrom (2026-08-06) — the BODY complement of the meta
// gate. The indexed <meta> goes silent on an inherited licence type; a body can
// qualify, so it keeps the value and names the source. Opposite behaviours from
// the same fact, which is why they are two helpers.
// =============================================================================

describe("licensingContentInheritedFrom", () => {
  function codeWithProv(
    licensing: KBLICode["licensing"],
    contentInheritedFrom: string[] | null,
  ): KBLICode {
    return {
      licensing,
      provenance: {
        licensing: {
          status: "oss_native",
          locator: null,
          vintage: "2025",
          noOssScope: false,
          contentInheritedFrom,
        },
      },
    } as KBLICode;
  }

  const someRows = [{ riskCategory: "Tinggi" }] as KBLICode["licensing"];

  it("GUILT: returns the source codes when rows are served and inherited", () => {
    expect(
      licensingContentInheritedFrom(
        codeWithProv(someRows, ["62011", "62019", "62015"]),
      ),
    ).toEqual(["62011", "62019", "62015"]);
  });

  it("INNOCENCE: null for a self-sourced record", () => {
    expect(
      licensingContentInheritedFrom(codeWithProv(someRows, null)),
    ).toBeNull();
  });

  it("INNOCENCE: null when no rows are served — nothing on screen to qualify", () => {
    expect(
      licensingContentInheritedFrom(
        codeWithProv([] as KBLICode["licensing"], ["62011"]),
      ),
    ).toBeNull();
  });

  it("fails CLOSED — not by throwing — on a missing/malformed provenance block", () => {
    expect(() =>
      licensingContentInheritedFrom({ licensing: someRows } as KBLICode),
    ).not.toThrow();
    expect(
      licensingContentInheritedFrom({ licensing: someRows } as KBLICode),
    ).toBeNull();
    expect(
      licensingContentInheritedFrom({
        licensing: someRows,
        provenance: {},
      } as unknown as KBLICode),
    ).toBeNull();
  });
});

describe("pp28ContentInheritedFrom (raw-record derivation)", () => {
  it("GUILT: sources naming only OTHER codes are inheritance", () => {
    expect(
      pp28ContentInheritedFrom(
        makeRaw({ kode_kbli_2025: "62110", pp28_sources: ["62011", "62019"] }),
      ),
    ).toEqual(["62011", "62019"]);
  });

  it("INNOCENCE: a record listing its OWN code has a row of its own", () => {
    expect(
      pp28ContentInheritedFrom(
        makeRaw({ kode_kbli_2025: "56101", pp28_sources: ["56101", "56102"] }),
      ),
    ).toBeNull();
  });

  it("INNOCENCE: an empty source list is absence, not inheritance", () => {
    // 175 codes record no PP 28 source at all. Withdrawing a claim on missing
    // data would be asserting inheritance we cannot show.
    expect(
      pp28ContentInheritedFrom(
        makeRaw({ kode_kbli_2025: "99999", pp28_sources: [] }),
      ),
    ).toBeNull();
  });

  it("real dataset: 390 inherited, and deriveProvenance carries it on every branch", () => {
    const parsed = JSON.parse(
      fs.readFileSync(
        path.join(process.cwd(), "data", "KBLI_2025_FINAL_CLEAN.json"),
        "utf-8",
      ),
    ) as KBLIRawDataFile;

    const inherited = parsed.data.filter(
      (r) => pp28ContentInheritedFrom(r) !== null,
    );
    expect(inherited.length).toBe(390);

    // The field must survive derivation on EVERY record, not only the branch
    // that motivated it — a branch that dropped it would read as self-sourced.
    for (const r of parsed.data) {
      const prov = deriveProvenance(r);
      expect(
        prov.licensing.contentInheritedFrom,
        `code ${r.kode_kbli_2025}`,
      ).toEqual(pp28ContentInheritedFrom(r));
    }
  });
});

// =============================================================================
// The note's VINTAGE — pinned on the source, because the sentence lives in JSX
//
// `pp28_sources` holds KBLI-2020 numbers. A client reading "carried over from
// KBLI code 62011" looks 62011 up on THIS site, whose catalogue is 2025.
// Measured over the 378 distinct codes the note can name: 345 do not exist as
// 2025 codes and 33 do — as a DIFFERENT activity, since numbers are reused
// across vintages. So the year is part of the claim, not formatting.
//
// The same sentence exists in the backend (kbli_pp28_provenance.py, which has
// its own test). Two surfaces carrying one sentence is exactly how one of them
// drifts, so each pins its own copy rather than trusting the other's.
// =============================================================================

describe("inherited-licensing note", () => {
  const SOURCE = fs.readFileSync(
    path.join(
      process.cwd(),
      "src",
      "components",
      "kbli",
      "LicensingSection.tsx",
    ),
    "utf-8",
  );

  it("dates the codes it names to the 2020 vintage", () => {
    expect(SOURCE).toContain("carried over from KBLI 2020 code");
  });

  it("never names a source code without its vintage", () => {
    // Guilt for the exact shipped-then-corrected wording, in both grammatical
    // branches: the plural is the one 62110 renders.
    expect(SOURCE).not.toContain("carried over from KBLI code");
    expect(SOURCE).not.toContain("carried over from KBLI codes");
  });
});
