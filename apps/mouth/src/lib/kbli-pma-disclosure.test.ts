import { describe, expect, it } from "vitest";

import { deriveProvenance } from "./kbli-provenance";
import {
  discloseBaliL4,
  disclosePmaInfo,
  formatPmaOwnership,
  hasPublishablePmaCap,
  isSourcedBaliClosure,
} from "./kbli-pma-disclosure";
import type { KBLIRawCode } from "./kbli-types";

function located(overrides: Record<string, unknown> = {}): KBLIRawCode {
  return {
    kode_kbli_2025: "47221",
    judul: "fixture",
    uraian: "fixture",
    per_skala: [],
    sektor_id: null,
    status_mapping: "",
    pp28_sources: [],
    pma_status: "TERBATAS",
    pma_max_asing: 49,
    pma_kondisi: null,
    pma_prioritas: false,
    pma_nota: null,
    pma_source: "Perpres",
    pma_verification_status: "located",
    pma_official_basis: "official locator",
    pma_source_vintage: "2021-05-25",
    pma_cap_verified: true,
    _source: "test",
    l4_bali: {
      status: "OK_or_HIGHER_RISK",
      blocked: false,
      needs_review: false,
      reason: "OK_or_HIGHER_RISK",
    },
    ...overrides,
  } as unknown as KBLIRawCode;
}

describe("atomic PMA and Bali disclosure", () => {
  it("exposes a narrower Perpres citation only with a complete located tuple", () => {
    const raw = located();
    const disclosed = disclosePmaInfo(
      raw,
      deriveProvenance(raw),
      "Perpres 49/2021 fixture",
    );

    expect(disclosed.citation).toContain("Perpres");

    const gap = located({
      pma_verification_status: "declared_gap",
      pma_official_basis: null,
      pma_source_vintage: null,
    });
    expect(
      disclosePmaInfo(gap, deriveProvenance(gap), "unsafe citation").citation,
    ).toBeNull();
  });

  it("does not coerce malformed cap or auxiliary values", () => {
    const raw = located({
      pma_max_asing: "49",
      pma_prioritas: "false",
      pma_cap_verified: "true",
      pma_kondisi: 7,
      pma_nota: ["unsafe"],
      pma_source: { unsafe: true },
      pma_route_to: 86103,
    });

    const disclosed = disclosePmaInfo(raw, deriveProvenance(raw));
    expect(disclosed).toMatchObject({
      status: "restricted",
      maxForeign: null,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
      capSpecial: false,
      capVerified: false,
      routeTo: null,
    });
    expect(formatPmaOwnership(disclosed)).toBe(
      "Restricted · ownership cap not verified",
    );
    expect(formatPmaOwnership(disclosed)).not.toContain("null%");
  });

  it("preserves only the explicitly marked special cap", () => {
    const marked = located({
      pma_max_asing: "special",
      pma_cap_special: true,
    });
    const unmarked = located({
      pma_max_asing: "special",
      pma_cap_special: false,
    });

    expect(disclosePmaInfo(marked, deriveProvenance(marked))).toMatchObject({
      maxForeign: "special",
      capSpecial: true,
    });
    expect(disclosePmaInfo(unmarked, deriveProvenance(unmarked))).toMatchObject(
      { maxForeign: null, capSpecial: false },
    );
    expect(
      formatPmaOwnership(disclosePmaInfo(marked, deriveProvenance(marked))),
    ).toBe("Special non-percentage conditions");
  });

  it("withholds numeric and special cap claims until the cap is verified", () => {
    const numeric = located({ pma_max_asing: 49, pma_cap_verified: false });
    const special = located({
      pma_max_asing: "special",
      pma_cap_special: true,
      pma_cap_verified: false,
    });

    for (const raw of [numeric, special]) {
      const disclosed = disclosePmaInfo(raw, deriveProvenance(raw));
      expect(formatPmaOwnership(disclosed)).toBe(
        "Restricted · ownership cap not verified",
      );
      expect(formatPmaOwnership(disclosed, "metadata")).toBe(
        "Foreign Ownership Restricted (ownership cap not verified)",
      );
      expect(disclosed.maxForeign).toBeNull();
      expect(hasPublishablePmaCap(disclosed)).toBe(false);
    }
  });

  it("does not synthesize 100% for a located open status without a verified cap", () => {
    const missing = located({
      pma_status: "TERBUKA",
      pma_max_asing: undefined,
      pma_cap_verified: false,
    });
    const unverified = located({
      pma_status: "TERBUKA",
      pma_max_asing: 100,
      pma_cap_verified: false,
    });

    const missingDisclosure = disclosePmaInfo(
      missing,
      deriveProvenance(missing),
    );
    const unverifiedDisclosure = disclosePmaInfo(
      unverified,
      deriveProvenance(unverified),
    );
    expect(formatPmaOwnership(missingDisclosure)).toBe(
      "Open · ownership cap not verified",
    );
    expect(formatPmaOwnership(unverifiedDisclosure)).toBe(
      "Open · ownership cap not verified",
    );
    expect(unverifiedDisclosure.maxForeign).toBeNull();
    expect(formatPmaOwnership(missingDisclosure, "metadata")).not.toContain(
      "100%",
    );
    expect(formatPmaOwnership(unverifiedDisclosure, "metadata")).not.toContain(
      "100%",
    );
    expect(hasPublishablePmaCap(missingDisclosure)).toBe(false);
    expect(hasPublishablePmaCap(unverifiedDisclosure)).toBe(false);
  });

  it("qualifies a located closed verdict when its independent cap is unavailable", () => {
    const raw = located({
      pma_status: "TERTUTUP",
      pma_max_asing: null,
      pma_cap_verified: false,
    });
    const disclosed = disclosePmaInfo(raw, deriveProvenance(raw));

    expect(formatPmaOwnership(disclosed)).toBe(
      "Closed · ownership cap not verified",
    );
    expect(formatPmaOwnership(disclosed, "metadata")).toBe(
      "Closed to Foreign Investment (ownership cap not verified)",
    );
    expect(hasPublishablePmaCap(disclosed)).toBe(false);
  });

  it.each([
    [" OK ", false],
    ["OK", "false"],
    ["OK", 0],
    ["", false],
  ])("rejects malformed Bali tuple status=%p blocked=%p", (status, blocked) => {
    const raw = located({
      l4_bali: { status, blocked, reason: "must not escape" },
    });

    expect(discloseBaliL4(raw, true)).toBeUndefined();
  });

  it("rejects a malformed Bali review flag instead of coercing it to false", () => {
    const malformed = located({
      l4_bali: {
        status: "OK_or_HIGHER_RISK",
        blocked: false,
        needs_review: "false",
        reason: "must not escape",
      },
    });

    expect(discloseBaliL4(malformed, true)).toBeUndefined();
  });

  it("rejects an unknown Bali status even when both booleans are valid", () => {
    const future = located({
      l4_bali: {
        status: "FUTURE_STATUS",
        blocked: false,
        needs_review: false,
        reason: "must not become registrable",
      },
    });

    expect(discloseBaliL4(future, true)).toBeUndefined();
  });

  it("preserves a valid Bali tuple without truthiness coercion", () => {
    const raw = located({
      l4_bali: {
        status: "OK_or_HIGHER_RISK",
        blocked: false,
        needs_review: false,
        confidence: "FUTURE",
        reason: "OK_or_HIGHER_RISK",
      },
    });

    expect(discloseBaliL4(raw, true)).toMatchObject({
      status: "OK_or_HIGHER_RISK",
      blocked: false,
      needsReview: false,
      confidence: "MEDIUM",
      reason: "Registrable in Bali",
    });
    expect(discloseBaliL4(raw, false)).toBeUndefined();
  });
});

// =============================================================================
// ATTENZIONE_FASCIA_BALI (added 2026-09-15, W-J B1 overlay) — GUILT + INNOCENCE
// =============================================================================
describe("discloseBaliL4 — ATTENZIONE_FASCIA_BALI", () => {
  it("INNOCENCE: the new status is allowed through, not dropped like an unknown one", () => {
    const raw = located({
      l4_bali: {
        status: "ATTENZIONE_FASCIA_BALI",
        blocked: false,
        needs_review: true,
        confidence: "MEDIUM",
        reason: "not on the closure list",
      },
    });
    expect(discloseBaliL4(raw, true)).toMatchObject({
      status: "ATTENZIONE_FASCIA_BALI",
      blocked: false,
      needsReview: true,
    });
  });

  it("GUILT: a status one character off ATTENZIONE_FASCIA_BALI is still dropped", () => {
    const raw = located({
      l4_bali: {
        status: "ATTENZIONE_FASCIA_BALI_X",
        blocked: false,
        needs_review: false,
        reason: "must not escape",
      },
    });
    expect(discloseBaliL4(raw, true)).toBeUndefined();
  });
});

// =============================================================================
// l4_bali.closure (CHIUSO_BALI applied-closure citation) — the ONLY place a
// URL is validated, so a bad one is caught here rather than trusted by a
// component downstream.
// =============================================================================
describe("discloseBaliL4 — closure citation", () => {
  function withClosure(closure: Record<string, unknown>) {
    return located({
      l4_bali: {
        status: "CHIUSO_BALI",
        blocked: true,
        needs_review: false,
        confidence: "HIGH",
        reason: "closed to new PMA licensing",
        closure,
      },
    });
  }

  it("INNOCENCE: a well-formed closure survives with its http(s) URLs intact", () => {
    const raw = withClosure({
      instrument: "Pemprov Bali press release",
      published: "2026-07-24",
      url: "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss",
      list_source: "ANTARA Bali",
      list_url: "https://bali.antaranews.com/berita/410161",
      effective: "third week of May 2026",
      ancestors_2020: ["55110", "55120"],
      scope_qualifier: null,
    });
    const disclosed = discloseBaliL4(raw, true);
    expect(disclosed?.closure).toMatchObject({
      instrument: "Pemprov Bali press release",
      url: "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss",
      listSource: "ANTARA Bali",
      listUrl: "https://bali.antaranews.com/berita/410161",
      ancestors2020: ["55110", "55120"],
    });
  });

  it("GUILT: a non-http(s) url and list_url are rejected, never rendered as a link", () => {
    const raw = withClosure({
      instrument: "Pemprov Bali press release",
      url: "javascript:alert(1)",
      list_source: "ANTARA Bali",
      list_url: "ftp://bali.antaranews.com/berita/410161",
    });
    const disclosed = discloseBaliL4(raw, true);
    expect(disclosed?.closure?.url).toBeNull();
    expect(disclosed?.closure?.listUrl).toBeNull();
    // The text fields survive even when their URL is rejected.
    expect(disclosed?.closure?.instrument).toBe("Pemprov Bali press release");
    expect(disclosed?.closure?.listSource).toBe("ANTARA Bali");
  });

  it("INNOCENCE: a record with no closure object still discloses normally", () => {
    const raw = located({
      l4_bali: {
        status: "CHIUSO_BALI",
        blocked: true,
        needs_review: false,
        confidence: "HIGH",
        reason: "closed to new PMA licensing",
      },
    });
    const disclosed = discloseBaliL4(raw, true);
    expect(disclosed?.status).toBe("CHIUSO_BALI");
    expect(disclosed?.closure).toBeUndefined();
  });
});

// =============================================================================
// A Bali APPLIED closure is self-sufficient evidence — disclosed even when
// the NATIONAL PMA verdict is not located (added 2026-09-16, W-J B1
// disclose). Every OTHER Bali status on an unlocated record stays hidden
// exactly as before: GUILT proves the one exception, INNOCENCE (a-g) proves
// the fail-closed default still holds for everything else.
// =============================================================================
describe("discloseBaliL4 — a sourced Bali closure discloses even when the national verdict is not located", () => {
  function chiusoBali(l4Overrides: Record<string, unknown> = {}) {
    return located({
      l4_bali: {
        status: "CHIUSO_BALI",
        blocked: true,
        needs_review: false,
        confidence: "HIGH",
        reason: "closed to new PMA licensing",
        closure: {
          instrument: "Pemprov Bali press release",
          url: "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss",
        },
        ...l4Overrides,
      },
    });
  }

  it("GUILT: CHIUSO_BALI + blocked + a sourced http(s) closure discloses with pmaVerdictLocated=false", () => {
    const disclosed = discloseBaliL4(chiusoBali(), false);
    expect(disclosed).toMatchObject({ status: "CHIUSO_BALI", blocked: true });
    expect(disclosed?.closure?.url).toBe(
      "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss",
    );
  });

  it("also discloses when the national verdict IS located (unchanged path)", () => {
    expect(discloseBaliL4(chiusoBali(), true)).toMatchObject({
      status: "CHIUSO_BALI",
      blocked: true,
    });
  });

  it("INNOCENCE (a): ATTENZIONE_FASCIA_BALI stays hidden when unlocated", () => {
    const raw = located({
      l4_bali: {
        status: "ATTENZIONE_FASCIA_BALI",
        blocked: false,
        needs_review: true,
        confidence: "MEDIUM",
        reason: "not on the closure list",
      },
    });
    expect(discloseBaliL4(raw, false)).toBeUndefined();
  });

  it("INNOCENCE (b): OK_or_HIGHER_RISK stays hidden when unlocated", () => {
    expect(discloseBaliL4(located(), false)).toBeUndefined();
  });

  it("INNOCENCE (c): a blocked TERTUTUP stays hidden when unlocated", () => {
    const raw = located({
      l4_bali: {
        status: "TERTUTUP",
        blocked: true,
        needs_review: false,
        confidence: "HIGH",
        reason: "closed to a PT PMA by an ownership restriction",
      },
    });
    expect(discloseBaliL4(raw, false)).toBeUndefined();
  });

  it("INNOCENCE (d): a blocked CHIUSO_MORATORIA_BALI stays hidden when unlocated", () => {
    const raw = located({
      l4_bali: {
        status: "CHIUSO_MORATORIA_BALI",
        blocked: true,
        needs_review: false,
        confidence: "HIGH",
        reason: "OSS risk at scale Besar is Rendah/Menengah-Rendah",
      },
    });
    expect(discloseBaliL4(raw, false)).toBeUndefined();
  });

  it("INNOCENCE (e): CHIUSO_BALI with a javascript: url stays hidden when unlocated", () => {
    const raw = chiusoBali({
      closure: {
        instrument: "Pemprov Bali press release",
        url: "javascript:alert(1)",
      },
    });
    expect(discloseBaliL4(raw, false)).toBeUndefined();
  });

  it("INNOCENCE (f): CHIUSO_BALI with no closure object stays hidden when unlocated", () => {
    const raw = located({
      l4_bali: {
        status: "CHIUSO_BALI",
        blocked: true,
        needs_review: false,
        confidence: "HIGH",
        reason: "closed to new PMA licensing",
      },
    });
    expect(discloseBaliL4(raw, false)).toBeUndefined();
  });

  it("INNOCENCE (g): CHIUSO_BALI with blocked false stays hidden when unlocated", () => {
    expect(
      discloseBaliL4(chiusoBali({ blocked: false }), false),
    ).toBeUndefined();
  });
});

describe("isSourcedBaliClosure", () => {
  it("true only for CHIUSO_BALI + blocked + a non-empty closure.url string", () => {
    expect(
      isSourcedBaliClosure({
        status: "CHIUSO_BALI",
        blocked: true,
        closure: { url: "https://www.baliprov.go.id/x" },
      }),
    ).toBe(true);
  });

  it("false for a null/undefined/malformed input, never throws", () => {
    expect(isSourcedBaliClosure(null)).toBe(false);
    expect(isSourcedBaliClosure(undefined)).toBe(false);
    expect(isSourcedBaliClosure({})).toBe(false);
    expect(isSourcedBaliClosure({ status: "CHIUSO_BALI", blocked: true })).toBe(
      false,
    );
    expect(
      isSourcedBaliClosure({
        status: "CHIUSO_BALI",
        blocked: true,
        closure: { url: "" },
      }),
    ).toBe(false);
    expect(
      isSourcedBaliClosure({
        status: "TERTUTUP",
        blocked: true,
        closure: { url: "https://www.baliprov.go.id/x" },
      }),
    ).toBe(false);
  });
});
