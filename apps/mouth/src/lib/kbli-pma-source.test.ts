import { describe, expect, it } from "vitest";
import {
  pmaSourceAttributionStructured,
  pmaSourceNoteFaq,
} from "./kbli-pma-source";

const PERPRES_SOURCE = "Perpres 10/2021, 49/2021";
const SECTOR_LAW_SOURCE =
  "PP 14/2018, PP 3/2020 (sector law — Perpres 10/2021 Pasal 11(2) carve-out, not the Perpres 10/2021/49/2021 annexes)";

describe("pmaSourceNoteFaq", () => {
  it("innocence: a Perpres-sourced code keeps the existing crosswalk note verbatim", () => {
    expect(pmaSourceNoteFaq(PERPRES_SOURCE)).toBe(
      " (Source: Perpres 10/2021 as amended by Perpres 49/2021 — the investment-list annexes predate KBLI 2025; per-code crosswalk audit in progress.)",
    );
  });

  it("guilt: a record whose pma_source names PP 14/2018 renders that, not Perpres", () => {
    const note = pmaSourceNoteFaq(SECTOR_LAW_SOURCE);
    expect(note).toContain("PP 14/2018");
    expect(note).not.toContain("crosswalk audit in progress");
    // The sector-law source string itself MENTIONS Perpres 10/2021 (naming
    // the carve-out it was routed away from) — the guard is that the
    // Perpres CROSSWALK CAVEAT never fires here, not that the word never
    // appears.
    expect(note).toBe(` (Source: ${SECTOR_LAW_SOURCE}.)`);
  });

  it("no source recorded: no note, never a fabricated one", () => {
    expect(pmaSourceNoteFaq(null)).toBe("");
  });
});

describe("pmaSourceAttributionStructured", () => {
  it("innocence: a Perpres-sourced code keeps the existing structured-data clause verbatim", () => {
    expect(pmaSourceAttributionStructured(PERPRES_SOURCE)).toBe(
      " per Perpres 10/2021 as amended (crosswalk to KBLI 2025 pending)",
    );
  });

  it("guilt: a sector-law source is attributed directly, not folded into the Perpres clause", () => {
    const clause = pmaSourceAttributionStructured(SECTOR_LAW_SOURCE);
    expect(clause).toBe(` per ${SECTOR_LAW_SOURCE}`);
    expect(clause).not.toContain("crosswalk to KBLI 2025 pending");
  });

  it("no source recorded: no clause", () => {
    expect(pmaSourceAttributionStructured(null)).toBe("");
  });
});
