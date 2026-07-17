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
    // Real cured pilot codes across cause subtypes: 49213 (authority
    // collision), 60312 (unlocatable source), 64310 (wrong-pointer
    // transplant). The class answer must be the weakest common truthful
    // claim: about OUR verification, not about the regulation (Codex gate F1).
    for (const c of ["49213", "60312", "64310"]) {
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
