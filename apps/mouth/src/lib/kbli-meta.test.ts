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

/** ATTENZIONE_FASCIA_BALI fixture (added 2026-09-15, W-J B1): nationally
 * open, off Bali's 2026 applied-closure list, `blocked` is false. */
function attentionFasciaBali(): KBLIBaliL4 {
  return {
    status: "ATTENZIONE_FASCIA_BALI",
    reason: "not on the closure list",
    confidence: "MEDIUM",
    needsReview: true,
    blocked: false,
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

    expect(kbliMetaTitleSuffix(kbli)).toBe(
      "Foreign Ownership Restricted (ownership cap not verified)",
    );
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

    expect(kbliMetaTitleSuffix(kbli)).toBe(
      "Foreign Ownership Restricted (ownership cap not verified)",
    );
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

  it("qualifies a closed title and description when its cap is unavailable", () => {
    const closed = makeCode({
      pma: {
        ...makeCode().pma,
        status: "closed",
        maxForeign: null,
        capVerified: false,
      },
    });

    expect(kbliMetaTitleSuffix(closed)).toBe(
      "Closed to Foreign Investment (ownership cap not verified)",
    );
    expect(kbliMetaDescription(closed, "Restaurant")).toContain(
      "Closed to Foreign Investment (ownership cap not verified)",
    );
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

  it("qualifies title/description for ATTENZIONE_FASCIA_BALI instead of an unqualified open claim (Codex sol MAJOR finding 3, PR #6578)", () => {
    const kbli = makeCode({ baliL4: attentionFasciaBali() });

    expect(isBaliL4BlockVerifiedForBareClaim(kbli)).toBe(false);
    expect(kbliMetaTitleSuffix(kbli)).toBe(
      "Verify Bali PMA Closure List (2026)",
    );
    // Not the plain risk-tier suffix a genuinely-cleared open code would get.
    expect(kbliMetaTitleSuffix(kbli)).not.toBe(
      "100% Foreign Ownership, High Risk",
    );

    const description = kbliMetaDescription(kbli, "Restaurant");
    expect(description).toContain(
      "verify Bali's 2026 PMA closure list before filing",
    );
    // The qualifier is APPENDED, not a silent drop back to the bare sentence.
    expect(description).not.toContain(
      "Restaurant (KBLI 56101): 100% Foreign Ownership.",
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

    // SAETTA-20260915 W-J B1 v2 redo (applied onto post-#6596 main): the
    // applied-closure migration narrowed l4_bali.blocked from 518 to 131
    // raw-canonical codes, and separately the public disclosure gate
    // (disclosePmaInfo/discloseBaliL4) exposes `pma.status`/`baliL4` at all
    // for only ~57 "located" PMA records in the whole 1,559-code catalogue.
    // Those two narrow sets do not currently intersect: none of the located+
    // nationally-open codes is also Bali-blocked today. That is a fact about
    // today's PROVENANCE coverage (which codes happen to have a located PMA
    // basis), not a defect in the suffix gate — the gate's own composition
    // logic is already exercised unconditionally by the GUILT/INNOCENCE
    // fixture tests above ("drops `blocked in Bali`..." / "states `blocked
    // in Bali`...: HIGH confidence"), which prove the suffix is correct
    // whether or not any real code currently occupies this intersection. So
    // this block guards on the real population instead of asserting a false
    // floor: if it is ever non-empty again the loop below re-activates and
    // re-enforces the invariant on live data; today it is empty and there is
    // nothing to protect here that the fixtures above do not already cover.
    // Asserted explicitly (adversarial review finding, agy-gemini-3.1-pro,
    // 2026-09-15) rather than a bare early return, so a change that makes
    // this population non-zero WITHOUT anyone reading this comment still
    // fails loudly here, instead of the block silently going from "empty on
    // purpose" to "empty by accident, no one's looking." Re-measured
    // 2026-09-15 (W-J B1 cure round) against the national-cap-guard fix: the
    // 4 codes that fix un-blocked-then-re-blocked (10214/16221/95220/95299)
    // are TERTUTUP/TERBATAS-0%, never `pma.status === "open"`, so they were
    // never in this intersection and the population is still empty.
    expect(blockedOpen).toHaveLength(0);

    // MINOR (cure round 2026-09-15): the branch above used to `return` on an
    // empty population, which made the loops below dead code on every real
    // run — `stated` and the per-code assertions never executed, so this
    // "gate binds on the real dataset" test could pass forever without ever
    // calling kbliMetaTitleSuffix/isBaliL4BlockVerifiedForBareClaim on
    // anything. The population assertion above is a fact about TODAY's
    // catalogue; it is not a proof the gate itself still works. So run the
    // exact same guilt/innocence check unconditionally: on the real
    // population when it is non-empty, or — since it is empty today — on
    // synthetic codes built from this file's own makeCode/blockedBali
    // fixtures (the population-shape contract from GUILT/INNOCENCE above),
    // so the mechanism fires at least once every single run.
    const proofPopulation =
      blockedOpen.length > 0
        ? blockedOpen
        : [
            makeCode({ baliL4: blockedBali("HIGH", false) }), // verified: must state
            makeCode({ baliL4: blockedBali("MEDIUM", false) }), // low confidence: must not
            makeCode({ baliL4: blockedBali("HIGH", true) }), // needs review: must not
          ];
    const stated = proofPopulation.filter((c) =>
      kbliMetaTitleSuffix(c).includes("Bali"),
    );
    // The gate must actually FIRE at least once — a proof population that
    // never produces a "Bali" suffix would let the loops below pass emptily
    // too, the same tautology one level down.
    expect(stated.length).toBeGreaterThan(0);
    for (const c of stated) {
      expect(c.baliL4?.confidence).toBe("HIGH");
      expect(c.baliL4?.needsReview).not.toBe(true);
    }
    for (const c of proofPopulation.filter(
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

    // Compiler-owned partition: 65 whole-code verdicts have a per-code locator
    // and vintage; all other 1,494 records must reach the neutral metadata arm.
    // SAETTA-20260915 W-H PR-3a: 55201/55203/79903 moved declared_gap→located
    // (Perpres 49/2021 Lampiran II allocation), 1505→1502.
    // 2026-09-16 (W-J B1 disclose, 1502 -> 1484): 23 of the 39 newly-disclosed
    // `declared_gap` CHIUSO_BALI codes also pass `isBaliL4BlockVerifiedForBareClaim`
    // (HIGH confidence, not flagged for review); 5 of those are the hotel rows
    // whose closure carries a scope qualifier (building area under 6,000 m²),
    // which a <title> cannot state, so they stay neutral too. The other 18
    // reach "Closed to PT PMA in Bali (2026)"; the 16 MEDIUM codes stay neutral.
    // W-H PR-3b (1484 -> 1476): 8 more codes (47241 47242 47244 47245 47246
    // 47249 47712 47722) moved declared_gap→located. 47249 is MEDIUM
    // confidence, so it was one of the 16 "stays neutral" codes above (not
    // one of the 18 promoted to a bare claim) — it leaves the declared_gap
    // pool entirely and stops counting as a neutral pmaGap. The other 7 were
    // never in the disclosed-39 set (their l4_bali.status is
    // ATTENZIONE_FASCIA_BALI, not CHIUSO_BALI) but were already counted as
    // plain neutral declared_gap codes, so they also leave the count.
    // 1484 - 8 = 1476.
    // 1476 - 6 = 1470 on 2026-09-18 (naso lot): 10307 10308 16291 16293 32201
    // 55106 leave declared_gap for located under Lampiran II; 55106 is
    // CHIUSO_BALI, the other five ATTENZIONE_FASCIA_BALI — all six were plain
    // neutral declared_gap codes and simply leave the count.
    expect(pmaGaps).toBe(1470);
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
    expect(description).toMatch(
      /Foreign Ownership Restricted \(ownership cap not verified\)/,
    );
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

// =============================================================================
// A Bali APPLIED closure is self-sufficient evidence for the indexed <title>
// too — but only at the same bare-claim bar every other Bali title fact
// already clears (HIGH confidence, not flagged for review). Added 2026-09-16,
// W-J B1 disclose.
// =============================================================================
describe("kbliMetaTitleSuffix — a sourced Bali closure on an unverified national record", () => {
  it("68111 (HIGH confidence, Residential Property Development) ends the title with 'Closed to PT PMA in Bali (2026)'", () => {
    const code = getAllCodes().find((c) => c.code === "68111")!;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.confidence).toBe("HIGH");
    expect(kbliMetaTitleSuffix(code)).toBe("Closed to PT PMA in Bali (2026)");
  });

  it("47211 (MEDIUM confidence — merges several KBLI-2020 activities) stays on the neutral suffix", () => {
    const code = getAllCodes().find((c) => c.code === "47211")!;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.status).toBe("CHIUSO_BALI");
    expect(code.baliL4?.confidence).toBe("MEDIUM");
    expect(kbliMetaTitleSuffix(code)).toBe(
      "PMA Eligibility Requires Verification",
    );
  });

  it("55101 (HIGH, but the closure is scoped to buildings under 6,000 m²) stays on the neutral suffix", () => {
    const code = getAllCodes().find((c) => c.code === "55101")!;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.confidence).toBe("HIGH");
    expect(code.baliL4?.closure?.scopeQualifier).toBe(
      "building area under 6,000 m²",
    );
    expect(kbliMetaTitleSuffix(code)).toBe(
      "PMA Eligibility Requires Verification",
    );
  });
});

// =============================================================================
// Review F3: `kbliMetaDescription` needs the SAME bare-claim branch as the
// title suffix above — the title and description are two separate indexed
// surfaces, and a fix to one gate must not silently leave the other unfixed.
// =============================================================================
describe("kbliMetaDescription — the same sourced-Bali-closure branch as the title suffix", () => {
  it("68111 (HIGH confidence, unscoped, declared_gap nationally) states the closure in the description", () => {
    const code = getAllCodes().find((c) => c.code === "68111")!;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.confidence).toBe("HIGH");
    expect(code.baliL4?.closure?.scopeQualifier).toBeFalsy();

    expect(kbliMetaDescription(code, code.titleEn)).toContain(
      "nationally — closed to new PT PMA licensing in Bali (2026).",
    );
  });

  it("55101 (scoped: building area under 6,000 m²) omits the whole-code closure clause — no room for the scope text", () => {
    const code = getAllCodes().find((c) => c.code === "55101")!;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.closure?.scopeQualifier).toBe(
      "building area under 6,000 m²",
    );

    expect(kbliMetaDescription(code, code.titleEn)).not.toContain(
      "closed to new PT PMA licensing in Bali",
    );
  });

  it("47211 (MEDIUM confidence, unscoped) omits the whole-code closure clause — below the bare-claim gate", () => {
    const code = getAllCodes().find((c) => c.code === "47211")!;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.confidence).toBe("MEDIUM");

    expect(kbliMetaDescription(code, code.titleEn)).not.toContain(
      "closed to new PT PMA licensing in Bali",
    );
  });
});
