import { describe, expect, it } from "vitest";
import { buildKbliFaq } from "./kbli-faq";
import { getAllCodes, getCode } from "./kbli-data";
import type { KBLICode } from "./kbli-types";

describe("buildKbliFaq", () => {
  it("qualifies the open answer on a Bali-blocked code — never an unqualified yes", () => {
    const blocked = getCode("56101");
    expect(blocked).toBeDefined();
    const base = blocked as KBLICode;
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
    const base = getCode("56101") as KBLICode;
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
    const base = getCode("56101") as KBLICode;
    const synthetic: KBLICode = {
      ...base,
      pma: { ...base.pma, status: "open" },
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

  it("handles capSpecial restricted codes without stating a numeric cap as fact", () => {
    const base = getCode("56101") as KBLICode;
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "restricted",
        capSpecial: true,
        maxForeign: 0,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("special distribution conditions");
    expect(pmaAnswer).not.toContain("capped at 0%");
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
    expect(licenseAnswer).toContain("Menengah Tinggi");
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
    const base = getCode("56101") as KBLICode;
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
