import { describe, expect, it } from "vitest";
import {
  pmaSourceAttributionStructured,
  pmaSourceNoteFaq,
} from "./kbli-pma-source";

const PERPRES_SOURCE = "Perpres 10/2021, 49/2021";
const SECTOR_LAW_SOURCE = "PP 14/2018, PP 3/2020 (sector-law carve-out)";

describe("pmaSourceNoteFaq", () => {
  it("located: cites the record source directly", () => {
    expect(pmaSourceNoteFaq(PERPRES_SOURCE, "located")).toBe(
      ` (Source: ${PERPRES_SOURCE}.)`,
    );
    expect(pmaSourceNoteFaq(SECTOR_LAW_SOURCE, "located")).toBe(
      ` (Source: ${SECTOR_LAW_SOURCE}.)`,
    );
  });

  it("declared gap: withholds even a named raw instrument", () => {
    const note = pmaSourceNoteFaq(PERPRES_SOURCE, "declared_gap");
    expect(note).toContain("No adjudicated per-code official basis");
    expect(note).toContain("confirm it at oss.go.id");
    expect(note).not.toContain(PERPRES_SOURCE);
    expect(note).not.toContain("Instrument context recorded as");
    expect(note).not.toContain("audit in progress");
  });

  it("declared gap without source remains explicit", () => {
    const note = pmaSourceNoteFaq(null, "declared_gap");
    expect(note).toContain("No adjudicated per-code official basis");
    expect(note).not.toContain("Source:");
  });
});

describe("pmaSourceAttributionStructured", () => {
  it("located: attributes the named instrument", () => {
    expect(pmaSourceAttributionStructured(PERPRES_SOURCE, "located")).toBe(
      ` per ${PERPRES_SOURCE}`,
    );
  });

  it("declared gap: emits a verification warning, never a bare attribution", () => {
    const clause = pmaSourceAttributionStructured(
      SECTOR_LAW_SOURCE,
      "declared_gap",
    );
    expect(clause).toContain("no adjudicated per-code official basis");
    expect(clause).not.toContain(SECTOR_LAW_SOURCE);
    expect(clause).not.toBe(` per ${SECTOR_LAW_SOURCE}`);
  });

  it("located without a source emits no fabricated clause", () => {
    expect(pmaSourceAttributionStructured(null, "located")).toBe("");
  });
});
