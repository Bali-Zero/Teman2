// A Bali APPLIED closure (CHIUSO_BALI, sourced to a public press release) is
// self-sufficient evidence — disclosed even when the NATIONAL PMA verdict is
// not yet located (added 2026-09-16, W-J B1 disclose). This frame must never
// reuse the verified block's "valid for a foreign-owned company outside
// Bali" sentence, which would assert an unverified national permission.
//
// A real render, using a REAL code from the live artifact via kbli-data.ts
// (68111, Residential Property Development — the business-problem example the mandate
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

  it("innocence: a genuinely unlocated, non-sourced-closure code (62900) renders neither Bali frame", () => {
    // 01192 was this test's example until naso PR-5 (residual lot 2) located
    // it. 62900 carries the same ATTENZIONE_FASCIA_BALI status and stays
    // declared_gap (withheld by that lot's legacy_pma_prose leg).
    const kbli = getCode("62900");
    if (!kbli) throw new Error("62900 missing from kbli-data.ts");
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

  // Review F1: a SCOPED closure (the hotel rows) or a MEDIUM-confidence one
  // (a 2025 code that merges several KBLI-2020 activities, only some on
  // Bali's list) must not read as a bare, whole-code, certain bar.
  describe("review F1 — the closure's own scope/conservative-reading caveat", () => {
    it("55101 (Five-Star Hotel, scoped: building area under 6,000 m²) names the scope in the header AND the sentence", () => {
      const kbli = getCode("55101");
      if (!kbli) throw new Error("55101 missing from kbli-data.ts");
      expect(kbli.provenance?.pma.status).toBe("declared_gap");
      expect(kbli.baliL4?.confidence).toBe("HIGH");
      expect(kbli.baliL4?.closure?.scopeQualifier).toBe(
        "building area under 6,000 m²",
      );

      const { container } = render(
        <LicensingSection kbli={kbli} gold={null} />,
      );

      expect(
        screen.getByText(
          "Bali — closed to new PMA licensing for building area under 6,000 m²",
        ),
      ).toBeInTheDocument();
      expect(container.textContent).toContain(
        "for building area under 6,000 m²",
      );
      // Never the unqualified conservative-reading caveat — this record IS
      // HIGH confidence, its qualifier is the scope, not the caveat.
      expect(container.textContent).not.toContain("conservative reading:");
    });

    it("47211 (MEDIUM confidence, unscoped) carries the conservative-reading caveat, not a bare closure", () => {
      const kbli = getCode("47211");
      if (!kbli) throw new Error("47211 missing from kbli-data.ts");
      expect(kbli.provenance?.pma.status).toBe("declared_gap");
      expect(kbli.baliL4?.confidence).toBe("MEDIUM");
      expect(kbli.baliL4?.closure?.scopeQualifier).toBeFalsy();

      const { container } = render(
        <LicensingSection kbli={kbli} gold={null} />,
      );

      // Header carries no scope text (there is none), but — review r2 m3 —
      // the conservative-reading caveat now appears in the heading itself,
      // not only in the body sentence below.
      expect(
        screen.getByText(
          "Bali — closed to new PMA licensing (conservative reading)",
        ),
      ).toBeInTheDocument();
      expect(container.textContent).toContain(
        "conservative reading: this 2025 code also covers activities not on Bali's list",
      );
    });
  });
});
