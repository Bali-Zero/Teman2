import { describe, expect, it } from "vitest";

import { pmaReviewNotice } from "./kbli-pma-review";
import type { KBLIRawCode } from "./kbli-types";

function raw(overrides: Record<string, unknown> = {}): KBLIRawCode {
  return {
    kode_kbli_2025: "38110",
    judul: "fixture",
    uraian: "fixture",
    per_skala: [],
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
});
