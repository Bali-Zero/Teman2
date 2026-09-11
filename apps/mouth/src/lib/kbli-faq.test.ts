import { describe, expect, it } from "vitest";
import { buildKbliFaq } from "./kbli-faq";
import { getAllCodes, getCode } from "./kbli-data";
import type { KBLICode } from "./kbli-types";

function withLocatedPma(code: KBLICode): KBLICode {
  return {
    ...code,
    pma: {
      ...code.pma,
      verificationStatus: "located",
      officialBasis: "Perpres 49/2021 fixture locator",
      sourceVintage: "2021-05-25",
    },
    provenance: {
      ...code.provenance!,
      pma: {
        source: code.pma.source,
        status: "located",
        locator: "Perpres 49/2021 fixture locator",
        vintage: "2021-05-25",
      },
    },
  };
}

describe("buildKbliFaq", () => {
  it("qualifies the open answer on a Bali-blocked code — never an unqualified yes", () => {
    const blocked = getCode("56101");
    expect(blocked).toBeDefined();
    const base = withLocatedPma(blocked as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      pma: { ...base.pma, status: "open" },
      baliL4: { ...(base.baliL4 ?? {}), blocked: true, reason: "test reason" },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("NOT in Bali");
    expect(pmaAnswer).not.toMatch(/^Yes\./);
  });

  it("routes to the team on a NON_CLASSIFICABILE code — never claims open or blocked in Bali", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      pma: { ...base.pma, status: "open" },
      baliL4: {
        ...(base.baliL4 ?? {}),
        blocked: false,
        status: "NON_CLASSIFICABILE",
        reason: "test reason",
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("cannot be determined");
    expect(pmaAnswer).toContain("Bali Zero team");
    expect(pmaAnswer).not.toContain("NOT in Bali");
    expect(pmaAnswer).not.toMatch(/^Yes\./);
  });

  it("innocence: an OK_or_HIGHER_RISK code keeps the plain unqualified open answer", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      pma: {
        ...base.pma,
        status: "open",
        maxForeign: 100,
        capSpecial: false,
        capVerified: true,
      },
      baliL4: {
        ...(base.baliL4 ?? {}),
        blocked: false,
        status: "OK_or_HIGHER_RISK",
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toMatch(/^Yes\./);
    expect(pmaAnswer).not.toContain("cannot be determined");
    expect(pmaAnswer).not.toContain("Bali Zero team");
  });

  it("handles an exact special restricted cap without stating a percentage", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "restricted",
        capSpecial: true,
        maxForeign: "special",
        capVerified: true,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("special distribution conditions");
    expect(pmaAnswer).not.toContain("special%");
  });

  it("does not promote a mismatched special marker over a verified numeric cap", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "restricted",
        capSpecial: true,
        capVerified: true,
        maxForeign: 0,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("ceiling for foreign capital is 0%");
    expect(pmaAnswer).not.toContain("special distribution conditions");
  });

  it("never manufactures 100% ownership from a located TERBUKA status", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const withoutCap: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "open",
        maxForeign: null,
        capSpecial: false,
        capVerified: false,
      },
    } as KBLICode;
    const unverifiedHundred: KBLICode = {
      ...withoutCap,
      pma: {
        ...withoutCap.pma,
        maxForeign: 100,
      },
    } as KBLICode;

    const missingAnswer = buildKbliFaq(withoutCap)[0].answer;
    const unverifiedAnswer = buildKbliFaq(unverifiedHundred)[0].answer;
    expect(missingAnswer).toContain("ownership cap is not verified");
    expect(unverifiedAnswer).toContain("ownership cap is not verified");
    for (const answer of [missingAnswer, unverifiedAnswer]) {
      expect(answer).not.toContain("100%");
      expect(answer).not.toContain("No local Indonesian partner required");
    }
  });

  it("does not classify an unverified restricted 0% value as a closure", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "restricted",
        maxForeign: 0,
        capSpecial: false,
        capVerified: false,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("ownership cap not yet verified");
    expect(pmaAnswer).not.toContain("0%");
    expect(pmaAnswer).not.toMatch(/^No\./);
  });

  it("does not disclose an unverified special-cap claim", () => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "restricted",
        maxForeign: "special",
        capSpecial: true,
        capVerified: false,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("ownership cap not yet verified");
    expect(pmaAnswer).not.toContain("special distribution conditions");
  });

  it("qualifies a located closed verdict when its cap is not verified", () => {
    const base = withLocatedPma(getCode("65111") as KBLICode);
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "closed",
        maxForeign: null,
        capSpecial: false,
        capVerified: false,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain(
      "Closed to Foreign Investment (ownership cap not verified)",
    );
  });

  it("declares the licensing gap on every cure-detached subtype — never 'special regime', never asserting regulatory absence", () => {
    // Real cured pilot codes across cause subtypes still genuinely detached
    // (per_skala empty): 60312 (unlocatable source), 64310 (wrong-pointer
    // transplant). The class answer must be the weakest common truthful
    // claim: about OUR verification, not about the regulation (Codex gate F1).
    // 49213 (authority collision) is NOT in this list — it graduated to a
    // RESTORE (see the "graduates 49213" test below).
    for (const c of ["60312", "64310"]) {
      const cured = getCode(c);
      expect(cured, `code ${c}`).toBeDefined();
      expect(cured!.provenance?.state, `code ${c}`).toBe("not_classifiable");
      const licenseAnswer = buildKbliFaq(cured as KBLICode)[1].answer;
      expect(licenseAnswer).toContain("could not be verified");
      expect(licenseAnswer).toContain("Regulatory Divergence");
      expect(licenseAnswer).not.toContain("special or sectoral regime");
      // Never assert absence of a regulation — only our verification state.
      expect(licenseAnswer).not.toContain("not yet defined");
      expect(licenseAnswer).not.toContain("does not apply");
    }
  });

  it("graduates 49213 to a real licensing answer — its historical collision marker stays an audit trail, not an active gap", () => {
    // 49213 was RESTORED (not detached) via the per-ancestor cure spec
    // (scripts/kbli_filiera/cure_specs/restore_49213.json): per_skala now
    // serves real PP28-image-verified rows, so the licensing answer must
    // show them, never the gap-language above. The record's
    // `per_skala_disputed_pp28_collision` key deliberately stays on the
    // record (historical audit trail per the cure spec's own _doc), so
    // provenance.state alone would still read "not_classifiable" — the
    // licensing answer must branch on served rows, not that marker alone.
    const restored = getCode("49213");
    expect(restored).toBeDefined();
    const licenseAnswer = buildKbliFaq(restored as KBLICode)[1].answer;
    expect(licenseAnswer).toContain("Medium-High");
    expect(licenseAnswer).not.toContain("could not be verified");
    expect(licenseAnswer).not.toContain("Regulatory Divergence");
  });

  it("innocence: a legit no-OSS-rows code keeps the special-regime answer", () => {
    // A code with zero licensing rows but NO collision cure (the ~100-code
    // special/sectoral group) must keep the special-regime answer.
    const special = getAllCodes().find(
      (c) =>
        c.licensing.length === 0 && c.provenance?.state !== "not_classifiable",
    );
    expect(special).toBeDefined();
    const licenseAnswer = buildKbliFaq(special as KBLICode)[1].answer;
    expect(licenseAnswer).toContain("special or sectoral regime");
    expect(licenseAnswer).not.toContain("Regulatory Divergence");
  });

  it("returns 3-4 entries and every answer names the code", () => {
    const code = getCode("56101") as KBLICode;
    const faq = buildKbliFaq(code);
    expect(faq.length).toBeGreaterThanOrEqual(3);
    expect(faq.length).toBeLessThanOrEqual(4);
    for (const entry of faq) {
      expect(entry.answer).toContain(code.code);
    }
  });

  it("qualifies the license answer on pending-with-rows codes; verified codes stay unqualified", () => {
    // 114 real codes serve rows whose provenance awaits crosswalk
    // adjudication — the FAQ (visible + JSON-LD) must qualify them.
    const pending = getAllCodes().find(
      (c) =>
        c.licensing.length > 0 &&
        c.provenance?.licensing.status === "pending_crosswalk",
    );
    expect(pending).toBeDefined();
    const pendingAnswer = buildKbliFaq(pending as KBLICode)[1].answer;
    expect(pendingAnswer).toContain("crosswalk adjudication is pending");

    // Innocence: an OSS-verified code keeps the plain factual answer.
    const verified = getAllCodes().find(
      (c) =>
        c.licensing.length > 0 &&
        c.provenance?.licensing.status === "oss_native",
    );
    expect(verified).toBeDefined();
    const verifiedAnswer = buildKbliFaq(verified as KBLICode)[1].answer;
    expect(verifiedAnswer).not.toContain("crosswalk adjudication is pending");
  });
});

describe("buildKbliFaq — BPS-authoritative transition populations", () => {
  function transitionAnswer(codeValue: string): string {
    const code = getCode(codeValue) as KBLICode;
    const entry = buildKbliFaq(code).find((item) =>
      item.question.startsWith("How did KBLI"),
    );
    expect(entry).toBeDefined();
    return entry!.answer;
  }

  it("guilt: conflicting 01138 cites BPS ancestry, never PP28 as predecessor", () => {
    const answer = transitionAnswer("01138");
    expect(answer).toContain(
      "According to the official BPS 2020 → 2025 crosswalk, KBLI 01138 has recorded KBLI 2020 ancestor(s) 01283. This is provenance only, not a licensing claim; no predecessor licensing regime is asserted to transfer.",
    );
    expect(answer).not.toContain("01122");
    expect(answer).not.toContain("previous code");
  });

  it("guilt: 01287 cites its BPS ancestor while PMA remains an explicit gap", () => {
    const code = getCode("01287") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.provenance?.pma.vintage).toBeNull();
    const faq = buildKbliFaq(code);
    expect(transitionAnswer("01287")).toContain(
      "According to the official BPS 2020 → 2025 crosswalk, KBLI 01287 has recorded KBLI 2020 ancestor(s) 01287.",
    );
    expect(JSON.stringify(faq)).not.toContain(
      "No official BPS 2020 → 2025 crosswalk ancestor is recorded",
    );
  });

  it("innocence: BPS-only 01122 keeps its transition answer without promoting PMA", () => {
    const code = getCode("01122") as KBLICode;
    expect(code.transition.pp28LicensingSourceCodes).toEqual([]);
    expect(code.provenance?.pma).toMatchObject({
      status: "declared_gap",
      vintage: null,
    });
    expect(transitionAnswer("01122")).toContain(
      "According to the official BPS 2020 → 2025 crosswalk",
    );
    expect(transitionAnswer("01122")).not.toContain(
      "PP 28/2025 licensing-source codes",
    );
  });

  it("innocence: 64995 keeps no PP28 source but now cites its BPS ancestor", () => {
    const code = getCode("64995") as KBLICode;
    expect(code.transition.pp28LicensingSourceCodes).toEqual([]);
    expect(code.provenance?.pma.status).toBe("declared_gap");
    const answer = transitionAnswer("64995");
    expect(answer).toContain(
      "According to the official BPS 2020 → 2025 crosswalk, KBLI 64995 has recorded KBLI 2020 ancestor(s) 64999.",
    );
    expect(answer).not.toContain("PP 28/2025 licensing-source codes");
  });
});

// =============================================================================
// The FAQ was the FIFTH render site of the Bali-block cause — and the one that
// leaves the page.
//
// It was missed by the L2.10 sweep because the sweep looked for the licensing
// frame's wording. This builder had its own: "(reserved for UMKM / 2026
// moratorium)", hardcoded for every blocking status. Its own header comment
// claims every fact "comes from dataset fields already rendered elsewhere on
// the same page (PMA verdict banner …)" — so curing the banner alone did not
// leave the FAQ merely stale, it put the two copies in contradiction.
//
// This one also emits FAQPage JSON-LD, so the wrong cause is what a search
// engine ingests, not just what a reader sees.
// =============================================================================
describe("buildKbliFaq — the Bali-block cause is derived, and Italian never leaves", () => {
  const blocked = (status: string, reason: string): KBLICode => {
    const base = withLocatedPma(getCode("56101") as KBLICode);
    return {
      ...base,
      pma: { ...base.pma, status: "open" },
      baliL4: { ...(base.baliL4 ?? {}), blocked: true, status, reason },
    } as KBLICode;
  };

  it("GUILT: a statutory ownership bar is no longer blamed on the moratorium or on UMKM", () => {
    const answer = buildKbliFaq(
      blocked("TERTUTUP", "Reserved to Indonesian citizens by UU 30/2004."),
    )[0].answer;
    expect(answer).not.toContain("reserved for UMKM");
    // Not a ban on the WORD: this clause deliberately says "— not by the Bali
    // moratorium", and that denial is what makes it useful. What must not
    // survive is the moratorium being ASSERTED as the cause.
    expect(answer).not.toContain("under the 13 May 2026 moratorium");
    expect(answer).toContain("ownership restriction on the activity itself");
  });

  it("GUILT: a sectoral-regulator closure states its own cause", () => {
    const answer = buildKbliFaq(
      blocked(
        "CHIUSO_REGOLATORE_SETTORIALE",
        "Sector regulator bars private capital.",
      ),
    )[0].answer;
    expect(answer).not.toContain("reserved for UMKM");
    expect(answer).toContain("the sector's own regulator");
  });

  it("INNOCENCE: the genuinely MSME-reserved codes keep the meaning they always had", () => {
    const answer = buildKbliFaq(
      blocked("CHIUSO_PMA_NO_BESAR", "Besar scale not permitted."),
    )[0].answer;
    expect(answer).toContain("micro/small/medium enterprises");
  });

  it("GUILT: 69104's Italian reason never reaches the answer — nor the JSON-LD built from it", () => {
    // Verbatim from the canonical record; it was spliced in unconditionally.
    const answer = buildKbliFaq(
      blocked(
        "TERTUTUP",
        "Notaio/PPAT è ufficio personale e statale, solo WNI (UU 30/2004 mod. UU 2/2014). PMA impossibile.",
      ),
    )[0].answer;
    expect(answer).not.toContain("Notaio");
    expect(answer).not.toContain("impossibile");
    // The cause survives the suppression — it comes from the status, not the prose.
    expect(answer).toContain("ownership restriction on the activity itself");
  });

  it("INNOCENCE: a useful English reason is still spliced in", () => {
    const answer = buildKbliFaq(
      blocked(
        "CHIUSO_PMA_NO_BESAR",
        "For PMA use 86103 (klinik, TERBATAS 67%).",
      ),
    )[0].answer;
    expect(answer).toContain("For PMA use 86103");
  });

  it("no double space is left where the reason was suppressed", () => {
    const answer = buildKbliFaq(blocked("TERTUTUP", "PMA impossibile."))[0]
      .answer;
    expect(answer).not.toContain("  ");
  });
});

// =============================================================================
// 2026-08-08 fix-pack, items E + F: the pmaSourceNote and the
// restrictedPmaAnswer trailing "An Indonesian partner holds the remaining
// shares" both hardcoded a claim that is false for a subset of TERBATAS
// codes — the source attribution because it never read `code.pma.source`,
// the trailing absolute because it ignored `code.pma.condition` entirely.
// =============================================================================
describe("buildKbliFaq — pmaSourceNote is source-aware (item E)", () => {
  it("guilt: a sector-law-sourced code (65111, this fix-pack) attributes PP 14/2018, not Perpres", () => {
    const code = getCode("65111") as KBLICode;
    expect(code).toBeDefined();
    expect(code.pma.source).toContain("PP 14/2018");
    const answer = buildKbliFaq(code)[0].answer;
    expect(answer).toContain("PP 14/2018");
    expect(answer).not.toContain("crosswalk audit in progress");
  });

  it("innocence: a located Perpres-sourced TERBATAS code cites its instrument", () => {
    // 52292 (cargo/freight forwarding, max 49% WNA per the l4_bali sample
    // elsewhere in this file) carries the plain Perpres residual-open
    // default — untouched by this fix-pack.
    const code = getAllCodes().find(
      (c) =>
        c.pma.status === "restricted" &&
        c.provenance?.pma.status === "located" &&
        !!c.pma.source?.startsWith("Perpres 10/2021"),
    );
    expect(code).toBeDefined();
    const answer = buildKbliFaq(code as KBLICode)[0].answer;
    expect(answer).toContain("(Source: Perpres 10/2021");
    expect(answer).not.toContain("crosswalk audit in progress");
  });
});

describe("restrictedPmaAnswer — the trailing absolute only holds when there is no condition (item F)", () => {
  it("guilt: a condition that narrates exemptions (65111, listed insurers exempt / grandfathered) drops the trailing absolute", () => {
    const code = getCode("65111") as KBLICode;
    expect(code.pma.condition).toBeTruthy();
    expect(code.pma.condition).toContain("exempt");
    const answer = buildKbliFaq(code)[0].answer;
    expect(answer).not.toContain(
      "An Indonesian partner holds the remaining shares.",
    );
    // The condition itself still renders — dropping the absolute must not
    // silently drop the real condition prose too.
    expect(answer).toContain("Condition:");
  });

  it("innocence: a plain percentage cap with no condition keeps the trailing absolute", () => {
    const base = getCode("65111") as KBLICode;
    const synthetic: KBLICode = {
      ...base,
      pma: { ...base.pma, condition: null },
    } as KBLICode;
    const answer = buildKbliFaq(synthetic)[0].answer;
    expect(answer).toContain(
      "An Indonesian partner holds the remaining shares.",
    );
  });
});
