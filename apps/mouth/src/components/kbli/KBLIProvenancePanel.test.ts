// =============================================================================
// The provenance panel had NO test — and that is how it came to misattribute
// the very thing it exists to disclose.
//
// Its "Bali status" row cited `l4_bali.moratorium.rule` as the SOURCE of every
// Bali verdict and described every one as "Conservative posture derived from the
// risk tier". That rule is not per-code evidence: it is one identical string on
// all 1,559 records. For the codes blocked by an activity-level restriction the
// attribution is simply false, and it was false ON PROD — verified 2026-07-27:
//
//   /kbli/38122  Pengumpulan Limbah Radioaktif   (closed by its sector regulator)
//   /kbli/11010  Industri Penyulingan            (ownership restriction)
//
// both served "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA" as
// their source and "derived from the risk tier" as their basis.
// =============================================================================
import { describe, expect, it } from "vitest";
import { buildRows } from "./KBLIProvenancePanel";
import { getAllCodes, getCode } from "@/lib/kbli-data";
import { isMoratoriumBasis } from "@/lib/kbli-bali-block";
import type { KBLICode, KBLIProvenance } from "@/lib/kbli-types";

const baliRow = (code: string) => {
  const kbli = getCode(code);
  expect(kbli, `code ${code} must exist`).toBeDefined();
  const c = kbli as KBLICode;
  expect(c.provenance, `code ${code} must carry provenance`).toBeDefined();
  const provenance = c.provenance as KBLIProvenance;
  expect(
    provenance.pma.status,
    `code ${code} must have located PMA proof`,
  ).toBe("located");
  const row = buildRows(c, provenance).find((r) => r.layer === "Bali status");
  expect(row, `code ${code} must render a Bali status row`).toBeDefined();
  return row!;
};

const pmaRow = (code: string) => {
  const kbli = getCode(code) as KBLICode;
  expect(kbli).toBeDefined();
  return buildRows(kbli, kbli.provenance as KBLIProvenance).find(
    (row) => row.layer === "Foreign ownership (PMA)",
  )!;
};

const MORATORIUM_RULE = "Bali province blocks ALL";
const RISK_TIER_BASIS = "derived from the risk tier";

describe("the Bali provenance row attributes the verdict to what produced it", () => {
  it("withholds the Bali row when the whole-code PMA verdict is a gap", () => {
    const c = getCode("38122") as KBLICode;
    expect(c.provenance?.pma.status).toBe("declared_gap");
    const row = buildRows(c, c.provenance as KBLIProvenance).find(
      (candidate) => candidate.layer === "Bali status",
    );
    expect(row).toBeUndefined();
  });

  it("withholds the Bali row for every checked declared-gap example", () => {
    for (const code of ["38122", "11010"]) {
      const c = getCode(code) as KBLICode;
      expect(c.provenance?.pma.status, `code ${code}`).toBe("declared_gap");
      expect(c.baliL4, `code ${code}`).toBeUndefined();
      expect(
        buildRows(c, c.provenance as KBLIProvenance).find(
          (candidate) => candidate.layer === "Bali status",
        ),
        `code ${code}`,
      ).toBeUndefined();
    }
  });

  it("GUILT: a located ownership restriction no longer cites the moratorium", () => {
    const row = baliRow("47111");
    expect(row.source).not.toContain(MORATORIUM_RULE);
    expect(row.detail).not.toContain(RISK_TIER_BASIS);
    expect(row.detail).toContain(
      "ownership restriction on the activity itself",
    );
  });

  it("INNOCENCE: a genuine risk-class block keeps the moratorium attribution", () => {
    const riskClass = getAllCodes().find(
      (c) => c.baliL4?.status === "BLOCCATO_CLASSE_RISCHIO",
    );
    expect(riskClass).toBeDefined();
    const row = baliRow(riskClass!.code);
    expect(row.source).toContain(MORATORIUM_RULE);
    expect(row.detail).toContain(RISK_TIER_BASIS);
  });

  it("INNOCENCE: a code that is NOT blocked keeps it too — the risk-tier test is what cleared it", () => {
    const open = getAllCodes().find(
      (c) =>
        c.baliL4 &&
        !c.baliL4.blocked &&
        c.baliL4.status !== "NON_CLASSIFICABILE" &&
        c.provenance,
    );
    expect(open).toBeDefined();
    const row = baliRow(open!.code);
    expect(row.source).toContain(MORATORIUM_RULE);
    expect(row.detail).toContain(RISK_TIER_BASIS);
  });

  it("INNOCENCE: a NON_CLASSIFICABILE code keeps its own gap wording, untouched", () => {
    const nc = getAllCodes().find(
      (c) => c.baliL4?.status === "NON_CLASSIFICABILE" && c.provenance,
    );
    if (!nc) return; // none in the current dataset — nothing to protect
    const row = baliRow(nc.code);
    expect(row.verdict).toBe("gap");
    expect(row.detail).toContain("Not classifiable until the true risk tier");
  });

  it("pins the verified population: 6 located codes are blocked by something other than the moratorium", () => {
    const misattributed = getAllCodes().filter(
      (c) =>
        c.baliL4?.blocked === true &&
        !isMoratoriumBasis(c.baliL4.blocked, c.baliL4.status),
    );
    // The public loader exposes Bali only for the exact located+basis+vintage
    // PMA atom. The former 98-record population included unverified Bali
    // verdicts; six independently adjudicated non-moratorium blocks remain.
    expect(misattributed).toHaveLength(6);
    // Every one of them must now name its own cause, never the risk tier.
    for (const c of misattributed) {
      const row = baliRow(c.code);
      expect(row.detail, `code ${c.code}`).not.toContain(RISK_TIER_BASIS);
      expect(row.source, `code ${c.code}`).not.toContain(MORATORIUM_RULE);
    }
  });
});

describe("the PMA provenance row follows the canonical verification state", () => {
  it("guilt: 01287 renders a declared gap, not a crosswalk promise", () => {
    const row = pmaRow("01287");
    expect(row.verdict).toBe("gap");
    expect(row.vintage).toBe("—");
    expect(row.detail).toContain("declares a verification gap");
    expect(row.detail).not.toContain("in progress");
  });

  it("innocence: a located sector-law code renders verified locator + vintage", () => {
    const row = pmaRow("65111");
    expect(row.verdict).toBe("verified");
    expect(row.vintage).toBe("2020-01-20");
    expect(row.locator).toContain("PP 14/2018 Pasal 5(1)");
    expect(row.detail).toContain("adjudicated official basis");
  });
});
