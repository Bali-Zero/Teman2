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
  const row = buildRows(c, c.provenance as KBLIProvenance).find(
    (r) => r.layer === "Bali status",
  );
  expect(row, `code ${code} must render a Bali status row`).toBeDefined();
  return row!;
};

const MORATORIUM_RULE = "Bali province blocks ALL";
const RISK_TIER_BASIS = "derived from the risk tier";

describe("the Bali provenance row attributes the verdict to what produced it", () => {
  it("GUILT: a sector-regulator closure (38122) no longer cites the moratorium", () => {
    const row = baliRow("38122");
    expect(row.source).not.toContain(MORATORIUM_RULE);
    expect(row.detail).not.toContain(RISK_TIER_BASIS);
    expect(row.detail).toContain("the sector's own regulator");
  });

  it("GUILT: an ownership restriction (11010) no longer cites the moratorium", () => {
    const row = baliRow("11010");
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

  it("pins the population: 98 codes are blocked by something other than the moratorium", () => {
    const misattributed = getAllCodes().filter(
      (c) =>
        c.baliL4?.blocked === true &&
        !isMoratoriumBasis(c.baliL4.blocked, c.baliL4.status),
    );
    // 111 → 98 on 2026-08-03. Thirteen codes moved from CHIUSO_PMA_NO_BESAR to
    // CHIUSO_MORATORIA_BALI when the "no Usaha Besar scale row ⇒ reserved for
    // UMKM" inference was withdrawn (Permeninves/BKPM 5/2025 Pasal 26(1)
    // inverts it) and each of the 39 affected codes was adjudicated against
    // Perpres 49/2021 Lampiran II. They are still blocked — the row now
    // attributes the block to the moratorium, which is the instrument that
    // actually produces it, so they legitimately leave this population.
    expect(misattributed).toHaveLength(98);
    // Every one of them must now name its own cause, never the risk tier.
    for (const c of misattributed) {
      const row = baliRow(c.code);
      expect(row.detail, `code ${c.code}`).not.toContain(RISK_TIER_BASIS);
      expect(row.source, `code ${c.code}`).not.toContain(MORATORIUM_RULE);
    }
  });
});
