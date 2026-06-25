import { describe, expect, it } from "vitest";
import {
  LAB_VISUAL_PHASES,
  activeLabProcessesForPhase,
  archivedLabProcesses,
  firstProcessForPhase,
  labTotals,
} from "../lib/lab-selectors";

describe("autonomous lab selectors", () => {
  it("keeps the public phase map at eleven steps", () => {
    expect(LAB_VISUAL_PHASES).toHaveLength(11);
    expect(LAB_VISUAL_PHASES.at(-1)?.id).toBe("archive");
  });

  it("moves finished processes into the archive view", () => {
    const archived = archivedLabProcesses();

    expect(archived.length).toBeGreaterThan(0);
    expect(activeLabProcessesForPhase("archive")).toEqual(archived);
    expect(archived.every((process) => process.archive)).toBe(true);
  });

  it("summarizes control-room totals for the standalone home", () => {
    const totals = labTotals();

    expect(totals.active).toBeGreaterThan(0);
    expect(totals.archived).toBe(archivedLabProcesses().length);
    expect(totals.avgProgress).toBeGreaterThan(0);
    expect(firstProcessForPhase("tribunal")?.phaseId).toBe("tribunal");
  });
});
