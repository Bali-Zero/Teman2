// The twin of the KeyFacts grid — the one the NON-gold page shows. It carried
// the same defect and the same comment, and nothing rendered it in a test until
// this file, which is why three cures to the idiom reached one copy only.
//
// Today no canonical record can reach it (the three unverified-with-rows codes
// are all gold, so they render through LicensingSection), so these fixtures
// prove the component's own honesty rather than a live page. That is the point:
// the next lot can move a code between the two branches without a review.

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
  it("93114 (pending_crosswalk) withholds risk, licence and processing", () => {
    const kbli = getCode("93114");
    if (!kbli) throw new Error("93114 missing from the canonical");

    render(<LicensingQuickFacts kbli={kbli} />);

    expect(cellValue("Risk Level")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("License Type")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(cellValue("Processing")).toBe(UNVERIFIED_LICENSING_FACT);
    expect(
      screen.getByText(/KBLI-2025 crosswalk is not verified/),
    ).toBeInTheDocument();
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
