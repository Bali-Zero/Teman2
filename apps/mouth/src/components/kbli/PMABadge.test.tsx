// PMABadge had no test of any kind, which is exactly how it survived #3436.
//
// That PR unified the ownership-cap wording behind `pmaCapShape` and fixed the
// five surfaces its corpus reached: the <title> suffix, the meta description,
// the FAQ answer (visible AND FAQPage JSON-LD), the two LicensingSection
// badges, the detail-page badge and KBLIStructuredData. PMABadge is a SIXTH
// presenter with its own private copy of the rule, referenced by no test — so
// after #3436 shipped and the domain was promoted, /kbli/47111 still published
// `⚠️ Restricted · Max 0%` in the visible pill (measured live 2026-07-29, 2
// occurrences: the HTML and the RSC payload of the same one call-site).
//
// Its private copy (`numeric !== null && numeric < 100`) never considered 0 at
// all, and was "right" at the other two ends only by falling silent: the `<
// 100` bound dropped the 100 case, the `!== null` guard dropped a non-numeric
// cap, and neither printed a qualifier the reader could recover. "Max 0%" is
// not a ceiling anyone can invest under — it is the closed case wearing a
// percentage — and a bare "Restricted" is the same failure with the evidence
// removed.

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PMABadge } from "./PMABadge";

describe("PMABadge — the cap extremes", () => {
  it("GUILT: a 0% ceiling is not a ceiling — this is the string that was live", () => {
    render(<PMABadge status="restricted" maxForeign={0} />);
    expect(screen.queryByText("· Max 0%")).toBeNull();
    expect(screen.getByText("· closed (0%)")).toBeDefined();
  });

  it("GUILT: a 100% ceiling restricts nothing, and must not go silent either", () => {
    // The old bound (`numeric < 100`) did not PRINT anything wrong here — it
    // printed nothing at all, leaving a bare "Restricted" whose qualifier the
    // reader cannot recover. Silence is the other way to be unhelpful.
    render(<PMABadge status="restricted" maxForeign={100} />);
    expect(screen.queryByText("· Max 100%")).toBeNull();
    expect(screen.getByText("· conditions apply")).toBeDefined();
  });

  it("GUILT: a drifted non-numeric cap gets a qualifier, not silence", () => {
    // capSpecial and the "special" value are independent raw fields
    // (pma_cap_special / pma_max_asing); they agree on one record today and
    // nothing structural keeps them in step.
    //
    // Written first as absence-only assertions, this case passed in BOTH
    // worlds — mutation-checked — because the old `numeric !== null` guard
    // skipped the whole branch and printed nothing, while the cure routes it
    // through the classifier's `typeof cap !== "number"` arm to "conditional".
    // Two different behaviours that absence alone cannot tell apart. Asserting
    // the POSITIVE string is what makes this discriminate, and silence on a
    // restricted code is the defect either way.
    render(
      <PMABadge status="restricted" maxForeign="special" capSpecial={false} />,
    );
    expect(screen.queryByText(/special%/)).toBeNull();
    expect(screen.queryByText(/Max /)).toBeNull();
    expect(screen.getByText("· conditions apply")).toBeDefined();
  });

  it("INNOCENCE: a real ceiling still prints as a ceiling", () => {
    render(<PMABadge status="restricted" maxForeign={49} />);
    expect(screen.getByText("· Max 49%")).toBeDefined();
  });

  it("INNOCENCE: an unverified cap keeps its qualifier", () => {
    render(
      <PMABadge status="restricted" maxForeign={49} capVerified={false} />,
    );
    expect(screen.getByText("· ≈49% unverified")).toBeDefined();
  });

  it("INNOCENCE: the special-distribution regime keeps its own wording", () => {
    render(<PMABadge status="restricted" maxForeign="special" capSpecial />);
    expect(screen.getByText("· special conditions")).toBeDefined();
  });

  it("INNOCENCE: the open-status suffixes are untouched", () => {
    const { unmount } = render(<PMABadge status="open" maxForeign={100} />);
    expect(screen.getByText("· 100% Foreign")).toBeDefined();
    unmount();
    render(<PMABadge status="open" maxForeign={100} baliBlocked />);
    expect(screen.getByText("· 100% nat'l · blocked in Bali")).toBeDefined();
  });
});
