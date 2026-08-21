/**
 * Snapshot tests for the frontend mirror of the backend E33 case state
 * machine. The shape MUST match `VALID_TRANSITIONS` in
 * `apps/backend-rag/backend/services/crm/e33_lifecycle.py`.
 *
 * The mandatory assertion from the spec (PR-2 acceptance criteria): every
 * UI-offered transition is a SUBSET of the backend table, and `itap_eval`
 * is never offered as a destination — regardless of stage or the local
 * feature-flag mirror.
 */
import { describe, expect, it } from "vitest";

import {
  ITAP_EVAL_ENABLED,
  STAGE_GROUP,
  STAGE_LABELS,
  TERMINAL_STAGES,
  VALID_TRANSITIONS,
  VISIBLE_STAGES,
  getOfferedNextStages,
  isTerminalStage,
  type E33StageKey,
} from "./state-machine";

const ALL_STAGES: E33StageKey[] = [
  "fit_memo",
  "bank_precheck",
  "application",
  "payment",
  "visa_issued",
  "entry",
  "itas_active",
  "guarantee_proof_due",
  "annual_maintenance",
  "renewal",
  "epo",
  "status_change",
  "itap_eval",
];

describe("VALID_TRANSITIONS — backend snapshot (e33_lifecycle.py:97-125)", () => {
  it("has exactly the 13 backend stages", () => {
    expect(Object.keys(VALID_TRANSITIONS).sort()).toEqual(
      [...ALL_STAGES].sort(),
    );
  });

  it("matches the exact backend table (drift detector)", () => {
    expect(VALID_TRANSITIONS).toEqual({
      fit_memo: ["bank_precheck"],
      bank_precheck: ["application", "fit_memo"],
      application: ["payment", "bank_precheck"],
      payment: ["visa_issued", "application"],
      visa_issued: ["entry"],
      entry: ["itas_active"],
      itas_active: ["guarantee_proof_due", "epo", "status_change", "itap_eval"],
      guarantee_proof_due: ["annual_maintenance", "epo", "status_change"],
      annual_maintenance: ["renewal", "epo", "status_change", "itap_eval"],
      renewal: ["itas_active"],
      epo: [],
      status_change: [],
      itap_eval: ["status_change"],
    });
  });

  it("has the canonical forward-progress chain", () => {
    expect(VALID_TRANSITIONS.fit_memo).toContain("bank_precheck");
    expect(VALID_TRANSITIONS.bank_precheck).toContain("application");
    expect(VALID_TRANSITIONS.application).toContain("payment");
    expect(VALID_TRANSITIONS.payment).toContain("visa_issued");
    expect(VALID_TRANSITIONS.visa_issued).toContain("entry");
    expect(VALID_TRANSITIONS.entry).toContain("itas_active");
    expect(VALID_TRANSITIONS.itas_active).toContain("guarantee_proof_due");
    expect(VALID_TRANSITIONS.guarantee_proof_due).toContain(
      "annual_maintenance",
    );
    expect(VALID_TRANSITIONS.annual_maintenance).toContain("renewal");
    expect(VALID_TRANSITIONS.renewal).toContain("itas_active");
  });

  it("marks epo and status_change as terminal (no outgoing edges)", () => {
    expect(VALID_TRANSITIONS.epo).toEqual([]);
    expect(VALID_TRANSITIONS.status_change).toEqual([]);
    expect(TERMINAL_STAGES).toEqual(["epo", "status_change"]);
  });

  it("provides a label and group for every one of the 13 stages", () => {
    for (const stage of ALL_STAGES) {
      expect(STAGE_LABELS[stage]).toBeTruthy();
      expect(STAGE_GROUP[stage]).toBeTruthy();
    }
  });

  it("groups stages per spec: pipeline / permit / terminal", () => {
    expect(STAGE_GROUP.fit_memo).toBe("pipeline");
    expect(STAGE_GROUP.bank_precheck).toBe("pipeline");
    expect(STAGE_GROUP.application).toBe("pipeline");
    expect(STAGE_GROUP.payment).toBe("pipeline");
    expect(STAGE_GROUP.visa_issued).toBe("pipeline");

    expect(STAGE_GROUP.entry).toBe("permit");
    expect(STAGE_GROUP.itas_active).toBe("permit");
    expect(STAGE_GROUP.guarantee_proof_due).toBe("permit");
    expect(STAGE_GROUP.annual_maintenance).toBe("permit");
    expect(STAGE_GROUP.renewal).toBe("permit");

    expect(STAGE_GROUP.epo).toBe("terminal");
    expect(STAGE_GROUP.status_change).toBe("terminal");
    expect(STAGE_GROUP.itap_eval).toBe("terminal");
  });
});

describe("itap_eval — gated feature (E33_ITAP_EVAL_ENABLED = False)", () => {
  it("mirrors the backend flag as disabled", () => {
    expect(ITAP_EVAL_ENABLED).toBe(false);
  });

  it("is excluded from VISIBLE_STAGES", () => {
    expect(VISIBLE_STAGES).not.toContain("itap_eval");
    expect(VISIBLE_STAGES.length).toBe(ALL_STAGES.length - 1);
  });

  it("is NEVER offered as a next stage from itas_active or annual_maintenance, even though the backend table lists it as a valid edge", () => {
    // The backend VALID_TRANSITIONS table lists itap_eval as a reachable
    // edge from both stages (the domain model always encodes it; the
    // *runtime* gate is the E33_ITAP_EVAL_ENABLED flag) — the UI must never
    // surface it as an option regardless.
    expect(VALID_TRANSITIONS.itas_active).toContain("itap_eval");
    expect(VALID_TRANSITIONS.annual_maintenance).toContain("itap_eval");

    expect(getOfferedNextStages("itas_active")).not.toContain("itap_eval");
    expect(getOfferedNextStages("annual_maintenance")).not.toContain(
      "itap_eval",
    );
  });

  it("is never offered from ANY stage in the table", () => {
    for (const stage of ALL_STAGES) {
      expect(getOfferedNextStages(stage)).not.toContain("itap_eval");
    }
  });
});

describe("getOfferedNextStages — UI transitions are a subset of the backend table", () => {
  it("every offered transition is contained in VALID_TRANSITIONS[current]", () => {
    for (const stage of ALL_STAGES) {
      const offered = getOfferedNextStages(stage);
      const backendAllowed = VALID_TRANSITIONS[stage];
      for (const target of offered) {
        expect(backendAllowed).toContain(target);
      }
    }
  });

  it("offers nothing from terminal stages", () => {
    expect(getOfferedNextStages("epo")).toEqual([]);
    expect(getOfferedNextStages("status_change")).toEqual([]);
  });

  it("offers the canonical forward chain minus itap_eval", () => {
    expect(getOfferedNextStages("fit_memo")).toEqual(["bank_precheck"]);
    expect(getOfferedNextStages("itas_active").sort()).toEqual(
      ["epo", "guarantee_proof_due", "status_change"].sort(),
    );
    expect(getOfferedNextStages("annual_maintenance").sort()).toEqual(
      ["epo", "renewal", "status_change"].sort(),
    );
  });

  it("falls back to no offered transitions on unknown/legacy stage values", () => {
    expect(getOfferedNextStages("some_unknown_stage")).toEqual([]);
  });
});

describe("isTerminalStage", () => {
  it("identifies epo and status_change as terminal", () => {
    expect(isTerminalStage("epo")).toBe(true);
    expect(isTerminalStage("status_change")).toBe(true);
  });

  it("does not flag non-terminal or itap_eval as terminal", () => {
    expect(isTerminalStage("fit_memo")).toBe(false);
    expect(isTerminalStage("itap_eval")).toBe(false);
  });
});
