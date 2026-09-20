// The key-fact grid used to print risk, licence and processing at full weight
// for a code whose licensing provenance the dataset does NOT verify, marking it
// with one 11px line below the grid — while the Foreign Ownership cell in the
// same grid replaced its value. Measured live on 2026-09-20 before this cure:
//
//   /kbli/93114 -> "Risk Level Medium-Low  License Type NIB dan Sertifikat
//                   Standar  Foreign Ownership Not verified — confirm in OSS
//                   Processing Instant" + the ⏳ footnote
//   /kbli/49213 -> the same shape and NO footnote at all (its rows are
//                   detached, not pending), on a page whose Regulatory
//                   Divergence panel states the licensing "was removed because
//                   its source could not be verified"
//
// Real records, not synthetic overrides: the three codes below are the whole
// live population of the two unverified shapes plus one verified control.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { UNVERIFIED_LICENSING_FACT } from "@/lib/kbli-provenance";
import { LicensingSection } from "./LicensingSection";

function cellValue(label: string): string {
  const nodes = screen.getAllByText(label);
  // The grid label is the only one rendered as its own element; take the first
  // and strip the label itself from the cell's text.
  const cell = nodes[0].parentElement;
  return (cell?.textContent ?? "").replace(label, "").trim();
}

describe("KeyFacts — a licensing cell withholds a value it cannot source", () => {
  it("93114 (pending_crosswalk, rows served) withholds risk, licence and processing", () => {
    const kbli = getCode("93114");
    if (!kbli) throw new Error("93114 missing from the canonical");
    expect(kbli.provenance?.licensing.status).toBe("pending_crosswalk");
    expect(kbli.licensing.length).toBeGreaterThan(0);

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(cellValue("Risk Level")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("License Type")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("Processing")).toBe(UNVERIFIED_LICENSING_FACT);
    // The withheld values are not lost — they stay in the PP28 block, which
    // states its own provenance. What changed is that the grid no longer
    // states them as fact.
    expect(
      screen.getByText(/KBLI-2025 crosswalk is not verified/),
    ).toBeInTheDocument();
  });

  it("49213 (rows detached by a code-number collision) withholds them too, and says why", () => {
    const kbli = getCode("49213");
    if (!kbli) throw new Error("49213 missing from the canonical");
    expect(kbli.provenance?.licensing.status).toBe("detached");
    expect(kbli.licensing.length).toBeGreaterThan(0);

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(cellValue("Risk Level")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("License Type")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("Processing")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(
      screen.getByText(/detached after a code-number collision/),
    ).toBeInTheDocument();
    // The pre-cure page printed "Medium-High" here with no qualifier at all.
    expect(screen.queryByText(/crosswalk is not verified/)).toBeNull();
  });

  it("innocence: 56101 (oss_native) keeps every value and grows no qualifier", () => {
    const kbli = getCode("56101");
    if (!kbli) throw new Error("56101 missing from the canonical");
    expect(kbli.provenance?.licensing.status).toBe("oss_native");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(cellValue("Risk Level")).toContain(kbli.licensing[0].riskCategory);
    expect(cellValue("License Type")).toBe(kbli.licensing[0].licenseType);
    expect(cellValue("Processing")).not.toBe(UNVERIFIED_LICENSING_FACT);
    expect(screen.queryByText(/crosswalk is not verified/)).toBeNull();
    expect(screen.queryByText(/detached after a code-number/)).toBeNull();
  });
});
