import { describe, expect, it } from "vitest";

import { pmaReviewNotice } from "./kbli-pma-review";
import type { KBLIRawCode } from "./kbli-types";

function skalaRow(scales: string[]) {
  return { skala_usaha: scales, kategori_risiko: "Menengah Rendah" };
}

// The three registered codes this file exercises, with their REAL scale set
// (matches apps/mouth/data/kbli-pma-review-notices.json) — a fixture whose
// per_skala doesn't match the notice's own `scales` field would trip the
// drift guard by accident, not by the test's intent.
const REGISTERED_SCALES: Record<string, string[]> = {
  "38110": ["Mikro", "Kecil", "Menengah"],
  "73300": ["Mikro", "Kecil", "Menengah"],
  "56102": ["Mikro", "Kecil"],
};

function raw(overrides: Record<string, unknown> = {}): KBLIRawCode {
  const code = (overrides.kode_kbli_2025 as string) ?? "38110";
  return {
    kode_kbli_2025: "38110",
    judul: "fixture",
    uraian: "fixture",
    per_skala: [skalaRow(REGISTERED_SCALES[code] ?? [])],
    sektor_id: null,
    status_mapping: "",
    pp28_sources: [],
    pma_status: "TERBUKA",
    pma_max_asing: 100,
    pma_kondisi: null,
    pma_prioritas: false,
    pma_nota: null,
    pma_source: "Perpres 10/2021, 49/2021",
    pma_verification_status: "declared_gap",
    _source: "test",
    l4_bali: {
      status: "CHIUSO_MORATORIA_BALI",
      blocked: true,
      needs_review: true,
      reason: "fixture",
    },
    ...overrides,
  } as unknown as KBLIRawCode;
}

describe("pmaReviewNotice", () => {
  it("discloses the specific notice for one of the 12 hold codes", () => {
    const note = pmaReviewNotice(raw({ kode_kbli_2025: "73300" }));
    expect(note).toContain("Not a national 0% finding");
    expect(note).toContain("confirm in OSS");
  });

  it("names a per-code {scales} fill, not a copy-pasted constant", () => {
    const note38110 = pmaReviewNotice(raw({ kode_kbli_2025: "38110" }));
    const note56102 = pmaReviewNotice(raw({ kode_kbli_2025: "56102" }));
    expect(note38110).toContain("Mikro, Kecil and Menengah scale");
    expect(note56102).toContain("Mikro and Kecil scale");
  });

  it("returns null for a code with no registered notice", () => {
    expect(pmaReviewNotice(raw({ kode_kbli_2025: "96220" }))).toBeNull();
  });

  it("withdraws the notice when pma_status has drifted from what it was authored against", () => {
    const drifted = raw({ kode_kbli_2025: "73300", pma_status: "TERTUTUP" });
    expect(pmaReviewNotice(drifted)).toBeNull();
  });

  it("withdraws the notice when pma_verification_status is no longer declared_gap", () => {
    const drifted = raw({
      kode_kbli_2025: "73300",
      pma_verification_status: "located",
    });
    expect(pmaReviewNotice(drifted)).toBeNull();
  });

  it("withdraws the notice when pma_max_asing has drifted", () => {
    const drifted = raw({ kode_kbli_2025: "73300", pma_max_asing: 0 });
    expect(pmaReviewNotice(drifted)).toBeNull();
  });

  it("withdraws the notice when OSS adds a Besar row — the whole reason the notice exists", () => {
    const gainedBesar = raw({
      kode_kbli_2025: "73300",
      per_skala: [skalaRow(["Mikro", "Kecil", "Menengah", "Besar"])],
    });
    expect(pmaReviewNotice(gainedBesar)).toBeNull();
  });

  it("withdraws the notice when a scale row is REMOVED — the note's own scale list would overstate it", () => {
    const lostAScale = raw({
      kode_kbli_2025: "73300",
      per_skala: [skalaRow(["Mikro"])],
    });
    expect(pmaReviewNotice(lostAScale)).toBeNull();
  });
});
