// A Bali APPLIED closure (CHIUSO_BALI, sourced to a public press release) is
// self-sufficient evidence — disclosed even when the NATIONAL PMA verdict is
// not yet located (added 2026-09-16, W-J B1 disclose). This frame must never
// reuse the verified block's "valid for a foreign-owned company outside
// Bali" sentence, which would assert an unverified national permission.
//
// A real render, using a REAL code from the live artifact via kbli-data.ts
// (68111, real estate rental — the business-problem example the mandate
// names), the same discipline as LicensingSection.perpres-slice.test.tsx.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { LicensingSection } from "./LicensingSection";

describe("LicensingSection — unlocated sourced Bali closure frame", () => {
  it("68111 (declared_gap nationally, CHIUSO_BALI in Bali) renders the Bali-only closure frame", () => {
    const kbli = getCode("68111");
    if (!kbli) throw new Error("68111 missing from kbli-data.ts");
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4).toMatchObject({ status: "CHIUSO_BALI", blocked: true });

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText("Bali — closed to new PMA licensing"),
    ).toBeInTheDocument();
    // The national-verification block (unverified generic notice) still
    // renders too — this frame is additive, not a replacement for it.
    expect(
      screen.getByText("PMA eligibility requires verification"),
    ).toBeInTheDocument();
    // Never the verified block's sentence — that would assert an unverified
    // national permission this record cannot back.
    expect(
      screen.queryByText(/valid for a foreign-owned company outside Bali/),
    ).toBeNull();
    // Never the verified block's own heading either — this is a different,
    // Bali-only frame, not a promotion of the unverified national tuple.
    expect(
      screen.queryByText(
        "National procedure — does not apply to a PT PMA in Bali",
      ),
    ).toBeNull();
  });

  it("innocence: a genuinely unlocated, non-sourced-closure code (01192) renders neither Bali frame", () => {
    const kbli = getCode("01192");
    if (!kbli) throw new Error("01192 missing from kbli-data.ts");
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4).toBeUndefined();

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText("PMA eligibility requires verification"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Bali — closed to new PMA licensing")).toBeNull();
  });

  it("innocence: a located, verified Bali-blocked code keeps the ORIGINAL verified frame, not the new one", () => {
    // 55105 is the one CHIUSO_BALI record that was already `located` before
    // this change — the verified block (with its "valid for a foreign-owned
    // company outside Bali" sentence) must still be the one that renders.
    const kbli = getCode("55105");
    if (!kbli) throw new Error("55105 missing from kbli-data.ts");
    expect(kbli.provenance?.pma.status).toBe("located");
    expect(kbli.baliL4).toMatchObject({ status: "CHIUSO_BALI", blocked: true });

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(
        "National procedure — does not apply to a PT PMA in Bali",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Bali — closed to new PMA licensing")).toBeNull();
  });
});
