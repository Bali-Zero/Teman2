// The twin of the KeyFacts grid — the one the NON-gold page shows. It carried
// the same defect and the same comment, and nothing rendered it in a test until
// this file, which is why three cures to the idiom reached one copy only.
//
// These three records are not hypothetical, and the first version of this
// header said they were: it claimed no canonical record reaches this component
// because the unverified-with-rows codes are "all gold". They are in the gold
// CORPUS and they do not reach the gold LAYOUT — `discloseKbliEditorial`
// withholds it when the PMA verdict is unverified, which is true of all three.
// 93114, 49213 and 93191 render through THIS component on production (read on
// the live HTML 2026-09-20: the `gap-1 p-4` cells and the "under Licensing
// Data below" wording are this file's, not KeyFacts'), and so do 1,214 of the
// 1,559 records overall.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { UNVERIFIED_LICENSING_FACT } from "@/lib/kbli-provenance";
import { LicensingQuickFacts } from "./LicensingQuickFacts";

function cellValue(label: string): string {
  const cell = screen.getByText(label).parentElement;
  return (cell?.textContent ?? "").replace(label, "").trim();
}

describe("LicensingQuickFacts — the non-gold grid keeps the same honesty rule", () => {
  // 2026-09-23 (#7136 OSS refresh ADOPT): 93114 moved pending_crosswalk ->
  // oss_native (OSS RBA 2025 published its own scope) and no longer withholds
  // here. See LicensingSection.unverified-cells.test.tsx for the sibling
  // KeyFacts-grid fix and the note that pending_crosswalk-with-rows is now an
  // extinct shape.
  it("93114 (oss_native) prints its real values and no qualifier", () => {
    const kbli = getCode("93114");
    if (!kbli) throw new Error("93114 missing from the canonical");

    render(<LicensingQuickFacts kbli={kbli} />);

    expect(cellValue("Risk Level")).not.toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("License Type")).not.toBe(UNVERIFIED_LICENSING_FACT);
    expect(
      screen.queryByText(/KBLI-2025 crosswalk is not verified/),
    ).toBeNull();
  });

  it("49213 (detached rows) withholds them and names the collision", () => {
    const kbli = getCode("49213");
    if (!kbli) throw new Error("49213 missing from the canonical");

    render(<LicensingQuickFacts kbli={kbli} />);

    expect(cellValue("Risk Level")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("Processing")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(
      screen.getByText(/detached after a code-number collision/),
    ).toBeInTheDocument();
  });

  it("innocence: 56101 (oss_native) prints its real values and no qualifier", () => {
    const kbli = getCode("56101");
    if (!kbli) throw new Error("56101 missing from the canonical");

    render(<LicensingQuickFacts kbli={kbli} />);

    expect(cellValue("Risk Level")).not.toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("License Type")).toBe(kbli.licensing[0].licenseType);
    expect(cellValue("Processing")).not.toBe(UNVERIFIED_LICENSING_FACT);
    expect(screen.queryByText(/crosswalk is not verified/)).toBeNull();
    expect(screen.queryByText(/detached after a code-number/)).toBeNull();
  });

  it("a record with no licensing rows renders nothing at all", () => {
    const kbli = getCode("84111");
    if (!kbli) throw new Error("84111 missing from the canonical");
    expect(kbli.licensing.length).toBe(0);

    const { container } = render(<LicensingQuickFacts kbli={kbli} />);
    expect(container.firstChild).toBeNull();
  });
});
