import { describe, expect, it } from "vitest";

import { deriveProvenance } from "./kbli-provenance";
import {
  discloseBaliL4,
  disclosePmaInfo,
  formatPmaOwnership,
  hasPublishablePmaCap,
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
      "Restricted · cap not published",
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
        "Restricted · cap not published",
      );
      expect(formatPmaOwnership(disclosed, "metadata")).toBe(
        "Foreign Ownership Restricted (cap not published)",
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
      "Open · ownership cap not published",
    );
    expect(formatPmaOwnership(unverifiedDisclosure)).toBe(
      "Open · ownership cap not published",
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

  it("preserves a valid Bali tuple without truthiness coercion", () => {
    const raw = located({
      l4_bali: {
        status: "OK_or_HIGHER_RISK",
        blocked: false,
        needs_review: "false",
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
