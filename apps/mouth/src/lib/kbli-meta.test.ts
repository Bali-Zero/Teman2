// =============================================================================
// kbli-meta — the indexed-metadata assertion gate
//
// Guilt + innocence corpus (cicatrix #3: a guard is never shipped without both).
// GUILT   = an unverified fact is withheld from the <title>/description.
// INNOCENCE = a verified fact still reaches them (a gate that hides everything
//             is not a gate, it is a regression to v2's undifferentiated suffix).
//
// Plus a real-dataset invariant: the gate must actually bind on the canonical,
// not just on fixtures. If a future dataset rebuild made every record verified,
// these numbers move and the test says so instead of silently passing.
// =============================================================================

import { describe, it, expect } from "vitest";
import {
  kbliMetaDescription,
  kbliMetaTitle,
  kbliMetaTitleSuffix,
  verifiedLicenseType,
  verifiedRiskLabel,
} from "./kbli-meta";
import {
  isBaliL4BlockVerifiedForBareClaim,
  isLicensingVerifiedForBareClaim,
} from "./kbli-provenance";
import { getAllCodes } from "./kbli-data";
import type {
  KBLIBaliL4,
  KBLICode,
  KBLILicenseByScale,
  KBLILicensingProvenanceStatus,
  KBLIProvenance,
} from "./kbli-types";

// -----------------------------------------------------------------------------
// Fixture factory
// -----------------------------------------------------------------------------

function makeLicensing(
  riskCategory = "Tinggi",
  licenseType = "NIB + Izin",
): KBLILicenseByScale[] {
  return [
    {
      scales: ["Kecil"],
      riskCategory: riskCategory as KBLILicenseByScale["riskCategory"],
      licenseType,
      requirements: [],
      timeframe: "3",
      obligations: [],
      authority: "OSS",
      fictivePositive: false,
    } as KBLILicenseByScale,
  ];
}

function makeProvenance(
  status: KBLILicensingProvenanceStatus = "oss_native",
  contentInheritedFrom: string[] | null = null,
): KBLIProvenance {
  return {
    state: status === "oss_native" ? "verified" : "pending",
    definition: { locator: "OSS_RBA_2025_id_version_test", assembly: null },
    licensing: {
      status,
      locator: status === "oss_native" ? "OSS_RBA_resiko_2025" : null,
      vintage: status === "oss_native" ? "2025" : "2020",
      noOssScope: status === "pending_crosswalk",
      contentInheritedFrom,
    },
    pma: {
      source: "Perpres 10/2021",
      vintage: "2021-05-25",
      status: "located",
      locator: "Perpres 49/2021 Lampiran III fixture",
    },
    dataNote: null,
    disputed: null,
  };
}

function makeCode(overrides: Partial<KBLICode> = {}): KBLICode {
  return {
    code: "56101",
    titleId: "Restoran",
    titleEn: "Restaurant",
    titleEnMeta: "Restaurant",
    description: "Test description",
    section: "I",
    sectionName: "Accommodation and Food Service",
    pma: {
      status: "open",
      maxForeign: 100,
      condition: null,
      isPriority: false,
      note: null,
      source: "Perpres 10/2021",
      verificationStatus: "located",
      officialBasis: "Perpres 49/2021 Lampiran III fixture",
      sourceVintage: "2021-05-25",
      capSpecial: false,
      capVerified: true,
      routeTo: null,
      citation: "Perpres 49/2021 Lampiran III fixture",
    },
    licensing: makeLicensing(),
    transition: {
      mappingStatus: "MATCH_LANGSUNG",
      pp28LicensingSourceCodes: [],
      kbli2020Source: null,
      mappingNote: null,
      aggregationNote: null,
    },
    tier: "silver",
    keywords: [],
    provenance: makeProvenance(),
    ...overrides,
  } as KBLICode;
}

function blockedBali(
  confidence: KBLIBaliL4["confidence"],
  needsReview = false,
): KBLIBaliL4 {
  return {
    status: "CHIUSO_PMA_NO_BESAR",
    reason: "Moratorium B.27.000/642",
    confidence,
    needsReview,
    blocked: true,
  };
}

// -----------------------------------------------------------------------------
// GUILT — an unverified fact never reaches an indexed surface
// -----------------------------------------------------------------------------

describe("GUILT: the gate withholds unverified facts from title/description", () => {
  it("drops the risk tier when the licensing rows await crosswalk", () => {
    const kbli = makeCode({ provenance: makeProvenance("pending_crosswalk") });

    expect(isLicensingVerifiedForBareClaim(kbli)).toBe(false);
    expect(verifiedRiskLabel(kbli)).toBeNull();
    expect(kbliMetaTitleSuffix(kbli)).toBe("100% Foreign Ownership");
    expect(kbliMetaDescription(kbli, "Restaurant")).not.toMatch(/risk/i);
  });

  it("drops the risk tier when `_l2_source` is present but unrecognized", () => {
    const kbli = makeCode({ provenance: makeProvenance("unverified_source") });

    expect(verifiedRiskLabel(kbli)).toBeNull();
    expect(kbliMetaTitleSuffix(kbli)).toBe("100% Foreign Ownership");
  });

  it("fails CLOSED — not by throwing — on a malformed provenance block", () => {
    // Adversarial review finding 2: `provenance?.licensing.status` guards a
    // null provenance and then throws on a non-null one with no `licensing`
    // key. A crash is not fail-closed, it is a 500 on an indexed page.
    const kbli = makeCode({ provenance: {} as never });

    expect(() => isLicensingVerifiedForBareClaim(kbli)).not.toThrow();
    expect(isLicensingVerifiedForBareClaim(kbli)).toBe(false);
    expect(kbliMetaTitle(kbli, kbli.titleEn)).not.toMatch(/Risk/);
    expect(kbliMetaDescription(kbli, kbli.titleEn)).not.toMatch(/license:/);
  });

  it("fails CLOSED when the provenance block is missing entirely", () => {
    // The whole point of the positive gate: absence of evidence is not evidence
    // of verification. A negative gate (`!isLicensingVerificationPending`) would
    // return true here and publish the claim.
    const kbli = makeCode({ provenance: undefined });

    expect(isLicensingVerifiedForBareClaim(kbli)).toBe(false);
    expect(verifiedRiskLabel(kbli)).toBeNull();
    expect(verifiedLicenseType(kbli)).toBeNull();
    // …and through the COMPOSERS, not only the helpers. Adversarial review
    // finding 3: asserting on the helpers alone lets a leak introduced in
    // kbliMetaTitle/kbliMetaDescription pass a test named "fails CLOSED".
    expect(kbliMetaTitle(kbli, kbli.titleEn)).not.toMatch(/Risk/);
    expect(kbliMetaDescription(kbli, kbli.titleEn)).not.toMatch(/license:/);
  });

  it("drops the license type whenever the risk tier is dropped", () => {
    const kbli = makeCode({ provenance: makeProvenance("pending_crosswalk") });

    expect(verifiedLicenseType(kbli)).toBeNull();
    expect(kbliMetaDescription(kbli, "Restaurant")).not.toMatch(/license:/);
  });

  it("drops `blocked in Bali` at MEDIUM confidence", () => {
    const kbli = makeCode({ baliL4: blockedBali("MEDIUM") });

    expect(isBaliL4BlockVerifiedForBareClaim(kbli)).toBe(false);
    expect(kbliMetaTitleSuffix(kbli)).not.toMatch(/Bali/);
    expect(kbliMetaDescription(kbli, "Restaurant")).not.toMatch(/blocked/i);
  });

  it("drops `blocked in Bali` when the verdict is flagged for review", () => {
    const kbli = makeCode({ baliL4: blockedBali("HIGH", true) });

    expect(isBaliL4BlockVerifiedForBareClaim(kbli)).toBe(false);
    expect(kbliMetaTitleSuffix(kbli)).not.toMatch(/Bali/);
  });

  it("keeps the pre-existing capVerified discipline on restricted codes", () => {
    const kbli = makeCode({
      pma: {
        ...makeCode().pma,
        status: "restricted",
        maxForeign: 67,
        capVerified: false,
      },
    });

    expect(kbliMetaTitleSuffix(kbli)).toBe("Foreign Ownership Restricted");
    expect(kbliMetaTitleSuffix(kbli)).not.toMatch(/67/);
  });

  it("withholds an unverified special-cap claim from indexed metadata", () => {
    const kbli = makeCode({
      pma: {
        ...makeCode().pma,
        status: "restricted",
        maxForeign: "special",
        capSpecial: true,
        capVerified: false,
      },
    });

    expect(kbliMetaTitleSuffix(kbli)).toBe("Foreign Ownership Restricted");
    expect(kbliMetaDescription(kbli, "Restaurant")).not.toContain("special");
  });

  it("does not synthesize 100% for an open status without a verified cap", () => {
    const missing = makeCode({
      pma: {
        ...makeCode().pma,
        status: "open",
        maxForeign: null,
        capVerified: false,
      },
    });
    const unverified = makeCode({
      pma: {
        ...makeCode().pma,
        status: "open",
        maxForeign: 100,
        capVerified: false,
      },
    });

    expect(kbliMetaTitleSuffix(missing)).toContain("cap not verified");
    expect(kbliMetaTitleSuffix(unverified)).toContain("cap not verified");
    expect(kbliMetaDescription(missing, "Restaurant")).not.toContain("100%");
    expect(kbliMetaDescription(unverified, "Restaurant")).not.toContain("100%");
  });
});

// -----------------------------------------------------------------------------
// INNOCENCE — a verified fact still differentiates the title
// -----------------------------------------------------------------------------

describe("INNOCENCE: verified facts still reach title/description", () => {
  it("states the risk tier on an OSS-native record", () => {
    const kbli = makeCode();

    expect(isLicensingVerifiedForBareClaim(kbli)).toBe(true);
    expect(kbliMetaTitleSuffix(kbli)).toBe("100% Foreign Ownership, High Risk");
    expect(kbliMetaTitle(kbli, "Restaurant")).toBe(
      "KBLI 56101: Restaurant — 100% Foreign Ownership, High Risk",
    );
    expect(kbliMetaDescription(kbli, "Restaurant")).toBe(
      "Restaurant (KBLI 56101): 100% Foreign Ownership. High risk, license: NIB + Izin. KBLI 2025 rules + Bali notes by Bali Zero.",
    );
  });

  it("states `blocked in Bali` at HIGH confidence without a review flag", () => {
    const kbli = makeCode({ baliL4: blockedBali("HIGH") });

    expect(isBaliL4BlockVerifiedForBareClaim(kbli)).toBe(true);
    expect(kbliMetaTitleSuffix(kbli)).toBe("Blocked for PT PMA in Bali (2026)");
    expect(kbliMetaDescription(kbli, "Restaurant")).toMatch(
      /blocked for a PT PMA in Bali \(2026\)/,
    );
  });

  it("states the verified cap % on a restricted code", () => {
    const kbli = makeCode({
      pma: {
        ...makeCode().pma,
        status: "restricted",
        maxForeign: 67,
        capVerified: true,
      },
    });

    expect(kbliMetaTitleSuffix(kbli)).toBe("Max 67% Foreign Ownership");
  });

  it("keeps the special-distribution and closed variants intact", () => {
    const special = makeCode({
      pma: { ...makeCode().pma, status: "restricted", capSpecial: true },
    });
    const closed = makeCode({ pma: { ...makeCode().pma, status: "closed" } });

    expect(kbliMetaTitleSuffix(special)).toBe(
      "Foreign Ownership With Conditions",
    );
    expect(kbliMetaTitleSuffix(closed)).toBe("Closed to Foreign Investment");
  });

  it("maps every risk tier the dataset uses", () => {
    const tiers: [string, string][] = [
      ["Tinggi", "High Risk"],
      ["Rendah", "Low Risk"],
      ["Menengah Tinggi", "Medium-High Risk"],
      ["Menengah Rendah", "Medium-Low Risk"],
    ];
    for (const [raw, expected] of tiers) {
      const kbli = makeCode({ licensing: makeLicensing(raw) });
      expect(kbliMetaTitleSuffix(kbli)).toBe(
        `100% Foreign Ownership, ${expected}`,
      );
    }
  });
});

// -----------------------------------------------------------------------------
// Real-dataset invariants — the gate must BIND on the canonical
// -----------------------------------------------------------------------------

describe("real dataset: the gate binds, and v3 actually differentiates", () => {
  it("states a Bali block only when its bare-claim gate passes", () => {
    const codes = getAllCodes();
    const blockedOpen = codes.filter(
      (c) => c.pma.status === "open" && c.baliL4?.blocked,
    );
    const stated = blockedOpen.filter((c) =>
      kbliMetaTitleSuffix(c).includes("Bali"),
    );

    // The public compiler now withholds declared-gap PMA rows altogether, so
    // the old raw-dataset cardinalities no longer belong at this boundary.
    // Keep the invariant: every surviving indexed Bali claim passed the exact
    // confidence/review gate, and every failed gate remains silent.
    expect(blockedOpen.length).toBeGreaterThan(0);
    for (const c of stated) {
      expect(c.baliL4?.confidence).toBe("HIGH");
      expect(c.baliL4?.needsReview).not.toBe(true);
    }
    for (const c of blockedOpen.filter(
      (code) => !isBaliL4BlockVerifiedForBareClaim(code),
    )) {
      expect(kbliMetaTitleSuffix(c)).not.toContain("Bali");
    }
  });

  it("never states a risk tier on a code whose licensing is unverified", () => {
    const offenders = getAllCodes().filter(
      (c) =>
        !isLicensingVerifiedForBareClaim(c) &&
        /\b(High|Low|Medium-High|Medium-Low) Risk\b/.test(
          kbliMetaTitleSuffix(c),
        ),
    );

    expect(offenders.map((c) => c.code)).toEqual([]);
  });

  // Was: "produces more than one distinct suffix". Struck by adversarial review
  // as vacuous — v2's four suffixes survive complete removal of the gate, so the
  // assertion passed either way and read like coverage. Replaced with the claim
  // that actually depends on the gate existing: on the real dataset the neutral
  // degradations must be REACHED, i.e. some records really do fail verification.
  it("actually degrades on the real dataset (the gate is not a no-op here)", () => {
    const suffixes = getAllCodes().map(kbliMetaTitleSuffix);
    const pmaGaps = suffixes.filter(
      (s) => s === "PMA Eligibility Requires Verification",
    ).length;

    // Compiler-owned partition: 54 whole-code verdicts have a per-code locator
    // and vintage; all other 1,505 records must reach the neutral metadata arm.
    expect(pmaGaps).toBe(1505);
    expect(suffixes).toHaveLength(1559);
  });

  it("degrades the cap in the DESCRIPTION when capVerified is false", () => {
    // The dataset-wide check below cannot see this today (measured: zero live
    // records are restricted + !capVerified + !capSpecial), so the synthetic
    // record is the ONLY thing constraining this branch. Without it the leak
    // Codex found would have been "fixed" with a test that passes either way.
    const kbli = makeCode({
      pma: {
        ...makeCode().pma,
        status: "restricted",
        maxForeign: 67,
        capVerified: false,
      },
    });

    const description = kbliMetaDescription(kbli, kbli.titleEn);
    expect(description).not.toMatch(/67/);
    expect(description).toMatch(/Restricted for foreign ownership/);
  });

  it("keeps the cap in the DESCRIPTION when capVerified is true", () => {
    const kbli = makeCode({
      pma: {
        ...makeCode().pma,
        status: "restricted",
        maxForeign: 67,
        capVerified: true,
      },
    });

    expect(kbliMetaDescription(kbli, kbli.titleEn)).toMatch(/max 67% foreign/);
  });

  it("never prints an unverified cap percentage in the DESCRIPTION either", () => {
    // Finding 1 of the adversarial pass: the title gated `maxForeign` on
    // capVerified and the description did not, so the same page refused the
    // number in one surface and printed it in the other.
    const offenders = getAllCodes().filter((c) => {
      if (c.pma.status !== "restricted" || c.pma.capVerified) return false;
      if (c.pma.capSpecial) return false;
      return /max \d+% foreign/.test(kbliMetaDescription(c, c.titleEn));
    });

    expect(offenders.map((c) => c.code)).toEqual([]);
  });
});

// -----------------------------------------------------------------------------
// PP 28 content inherited from OTHER codes (2026-08-06)
//
// `isLicensingVerifiedForBareClaim` reads `_l2_source`, which names the OSS-RBA
// RISK source. `pp28_sources` separately records where the PP 28 licensing rows
// came from, and on 337 codes the two disagree: risk genuinely 2025-native,
// licensing content carried from other codes. 62110 (video game development) is
// sourced from five 62xxx computer-programming codes and inherits three
// defence-industry permits that way.
//
// The gate is deliberately asymmetric — it withdraws the LICENCE claim and
// leaves the RISK claim standing, because only one of the two is inherited.
// -----------------------------------------------------------------------------

describe("inherited PP 28 content withdraws the licence claim, not the risk", () => {
  it("GUILT: an inherited-content record states its risk and NOT its licence", () => {
    const kbli = makeCode({
      provenance: makeProvenance("oss_native", ["62011", "62019", "62015"]),
    });

    // The risk gate is untouched: the tier is OSS-2025-native and still stated.
    expect(isLicensingVerifiedForBareClaim(kbli)).toBe(true);
    expect(verifiedRiskLabel(kbli)).toBe("High");
    // ...and the licence type, which may belong to another code, goes silent.
    expect(verifiedLicenseType(kbli)).toBeNull();

    const description = kbliMetaDescription(kbli, "Restaurant");
    expect(description).toContain("High risk.");
    expect(description).not.toContain("license:");
    // The title only ever carried the risk, so it must be unchanged — a gate
    // that also moved the title would be suppressing a fact it does not judge.
    expect(kbliMetaTitleSuffix(kbli)).toBe("100% Foreign Ownership, High Risk");
  });

  it("INNOCENCE: a self-sourced record still states both facts", () => {
    const kbli = makeCode({ provenance: makeProvenance("oss_native", null) });

    expect(verifiedLicenseType(kbli)).toBe("NIB + Izin");
    expect(kbliMetaDescription(kbli, "Restaurant")).toContain(
      "High risk, license: NIB + Izin.",
    );
  });

  it("INNOCENCE: inheritance cannot RESURRECT a claim the risk gate withheld", () => {
    // Both gates must hold. A pending_crosswalk record with no inheritance is
    // still silent on both facts — the new condition only ever subtracts.
    const kbli = makeCode({
      provenance: makeProvenance("pending_crosswalk", null),
    });

    expect(verifiedRiskLabel(kbli)).toBeNull();
    expect(verifiedLicenseType(kbli)).toBeNull();
    const description = kbliMetaDescription(kbli, "Restaurant");
    expect(description).not.toContain("risk");
    expect(description).not.toContain("license:");
  });

  it("real dataset: the gate binds, and on how many codes is pinned", () => {
    const codes = getAllCodes();
    const inherited = codes.filter(
      (c) => c.provenance?.licensing?.contentInheritedFrom != null,
    );
    const inheritedAndOssNative = inherited.filter(
      (c) => c.provenance?.licensing?.status === "oss_native",
    );

    // Measured on the 1,559-code canonical 2026-08-06. Pinned so a dataset
    // rebuild that widens or narrows the set fails loudly instead of quietly
    // re-labelling pages.
    expect(inherited.length).toBe(390);
    // 336, not the 337 a raw `_l2_source === "OSS_RBA_resiko_2025"` count
    // gives: `49213` (Angkutan Perkotaan, sourced from 49214/49219/49413)
    // carries a `per_skala_disputed_pp28_collision` block, so `deriveProvenance`
    // resolves it to `detached` BEFORE it can reach `oss_native`. The marker and
    // the derived status are different questions — this pin asserts the derived
    // one, because the derived one is what gates the page.
    expect(inheritedAndOssNative.length).toBe(336);

    // ...and the gate actually bites: every one of those 336 would have stated
    // a licence type before this change and states none now.
    for (const c of inheritedAndOssNative) {
      expect(verifiedLicenseType(c), `code ${c.code}`).toBeNull();
    }
    // Innocence at dataset scale: SOME code still states a licence, or the
    // gate is not a gate but a blanket.
    expect(codes.some((c) => verifiedLicenseType(c) !== null)).toBe(true);
  });
});
