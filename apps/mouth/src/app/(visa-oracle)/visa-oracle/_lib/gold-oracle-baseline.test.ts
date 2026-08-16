import { describe, expect, it } from "vitest";
import {
  findGoldOraclePersona,
  GOLD_ORACLE_PACK_HASH,
  goldOracleReviewReasonCode,
} from "./gold-oracle-baseline";

describe("gold oracle baseline (QW-2 independent SHADOW-parity oracle)", () => {
  it("pins a stable, non-empty source identifier", () => {
    expect(GOLD_ORACLE_PACK_HASH).toBe(
      "evaluate_path.py@8ee131a989fc786f1fc54ad531ddefaa9614756361f284b6412ee8a23120e569",
    );
  });

  it("predicts the disclosed-uncertainty review reason", () => {
    expect(goldOracleReviewReasonCode()).toBe("DISCLOSED_UNCERTAINTY_REVIEW");
  });

  it("matches the remote-worker persona (unsure whether employer is Indonesian)", () => {
    const persona = findGoldOraclePersona({
      category: "remote",
      work_payer: "unsure",
      remote_compensation: "no",
      remote_clients: "foreign",
      review_gate: "none",
    });
    expect(persona?.personaId).toBe("remote-worker-payer-unsure");
  });

  it("matches the family-spouse persona (unsure whether marriage is registered)", () => {
    const persona = findGoldOraclePersona({
      category: "family",
      family_relation: "SPOUSE",
      family_sponsor_nationalities: "ID",
      family_sponsor_confirmed: "yes",
      family_marriage_registered: "unsure",
      review_gate: "none",
    });
    expect(persona?.personaId).toBe("family-spouse-marriage-registered-unsure");
  });

  it("does not match once the unsure answer is actually resolved", () => {
    expect(
      findGoldOraclePersona({
        category: "remote",
        work_payer: "no",
        remote_compensation: "no",
        remote_clients: "foreign",
        review_gate: "none",
      }),
    ).toBeUndefined();
  });

  it("does not match a DIFFERENT unsure answer than the pinned one", () => {
    expect(
      findGoldOraclePersona({
        category: "remote",
        work_payer: "no",
        remote_compensation: "unsure",
        remote_clients: "foreign",
        review_gate: "none",
      }),
    ).toBeUndefined();
  });

  it("returns undefined for interviews outside the pinned subset", () => {
    expect(
      findGoldOraclePersona({
        category: "work",
        work_payer: "yes",
        review_gate: "none",
      }),
    ).toBeUndefined();
    expect(findGoldOraclePersona({})).toBeUndefined();
  });
});
