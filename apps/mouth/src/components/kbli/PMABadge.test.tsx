// PMABadge had no test of any kind, which is exactly how it survived #3436.
//
// That PR unified the ownership-cap wording behind `pmaCapShape` and fixed the
// five surfaces its corpus reached: `kbli-meta.ts`, `kbli-faq.ts` (visible AND
// FAQPage JSON-LD), the two `LicensingSection` badges, the foreign-ownership
// fact on the detail page, and `KBLIStructuredData`. PMABadge is a SIXTH
// presenter with its own private copy of the rule, referenced by no test — so
// after #3436 shipped and the domain was promoted, /kbli/47111 still published
// `⚠️ Restricted · Max 0%` in the visible pill (measured live 2026-07-29, 2
// occurrences: the HTML and the RSC payload of the same one call-site).
//
// (That "detail-page badge" #3436 did cure is a plain <span> elsewhere in
// page.tsx, NOT this component. Adversarial review caught me repeating the
// conflation — and it is precisely that conflation which let a sixth presenter
// look already-covered.)
//
// Its private copy, `numeric !== null && numeric < 100`, failed at the two ends
// in OPPOSITE ways: cap 0 PASSED the bound, reached the formula and printed
// `Max 0%`; cap 100 and a non-numeric cap were EXCLUDED and printed nothing at
// all. "Max 0%" is not a ceiling anyone can invest under — it is the closed
// case wearing a percentage — and a bare "Restricted" is the same failure with
// the evidence removed. Both are guilty below.

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { PMABadge } from "./PMABadge";

describe("PMABadge — the cap extremes", () => {
  it("GUILT: a 0% ceiling is not a ceiling — this is the string that was live", () => {
    render(<PMABadge status="restricted" maxForeign={0} verdictVerified />);
    expect(screen.queryByText("· Max 0%")).toBeNull();
    expect(screen.getByText("· closed (0%)")).toBeDefined();
  });

  it("GUILT: a 100% ceiling restricts nothing, and must not go silent either", () => {
    // The old bound (`numeric < 100`) did not PRINT anything wrong here — it
    // printed nothing at all, leaving a bare "Restricted" whose qualifier the
    // reader cannot recover. Silence is the other way to be unhelpful.
    render(<PMABadge status="restricted" maxForeign={100} verdictVerified />);
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
      <PMABadge
        status="restricted"
        maxForeign="special"
        verdictVerified
        capSpecial={false}
      />,
    );
    expect(screen.queryByText(/special%/)).toBeNull();
    expect(screen.queryByText(/Max /)).toBeNull();
    expect(screen.getByText("· conditions apply")).toBeDefined();
  });

  it("INNOCENCE: a real ceiling still prints as a ceiling", () => {
    render(<PMABadge status="restricted" maxForeign={49} verdictVerified />);
    expect(screen.getByText("· Max 49%")).toBeDefined();
  });

  it("INNOCENCE: an unverified cap keeps its qualifier", () => {
    render(
      <PMABadge
        status="restricted"
        maxForeign={49}
        verdictVerified
        capVerified={false}
      />,
    );
    expect(screen.getByText("· ≈49% unverified")).toBeDefined();
  });

  it("INNOCENCE: the special-distribution regime keeps its own wording", () => {
    render(
      <PMABadge
        status="restricted"
        maxForeign="special"
        verdictVerified
        capSpecial
      />,
    );
    expect(screen.getByText("· special conditions")).toBeDefined();
  });

  it("GUILT: no production call site may drop the provenance props", () => {
    // Every case above hands `capSpecial`/`capVerified` in by hand, so they
    // exercise a call shape the app did not actually use: KBLICard rendered
    // <PMABadge> without either, silently taking the defaults (false/true) and
    // ASSERTING a cap it was never told was verified. Adversarial review found
    // it; a fixture-driven card test would only have pinned the one call site
    // that existed today, so pin the PROPERTY instead — no call site, present
    // or future, gets to drop provenance.
    const root = path.resolve(__dirname, "..", "..");
    const sources: string[] = [];
    const walk = (dir: string) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        if (e.isDirectory()) walk(p);
        else if (p.endsWith(".tsx") && !p.includes(".test.")) sources.push(p);
      }
    };
    walk(root);

    const callSites: { file: string; text: string }[] = [];
    for (const file of sources) {
      const src = fs.readFileSync(file, "utf-8");
      let i = src.indexOf("<PMABadge");
      while (i !== -1) {
        const end = src.indexOf("/>", i);
        callSites.push({
          file,
          text: src.slice(i, end === -1 ? i + 400 : end),
        });
        i = src.indexOf("<PMABadge", i + 1);
      }
    }

    // A zero-length list would pass every assertion below and prove nothing —
    // the empty set disguises itself as both ALL and NOTHING.
    expect(callSites.length).toBeGreaterThanOrEqual(2);
    for (const { file, text } of callSites) {
      expect(text, `${file} omits capSpecial`).toContain("capSpecial");
      expect(text, `${file} omits capVerified`).toContain("capVerified");
      expect(text, `${file} omits verdictVerified`).toContain(
        "verdictVerified",
      );
    }
  });

  it("INNOCENCE: the open-status suffixes are untouched", () => {
    const { unmount } = render(
      <PMABadge status="open" maxForeign={100} verdictVerified />,
    );
    expect(screen.getByText("· 100% Foreign")).toBeDefined();
    unmount();
    render(
      <PMABadge status="open" maxForeign={100} verdictVerified baliBlocked />,
    );
    expect(screen.getByText("· 100% nat'l · blocked in Bali")).toBeDefined();
  });

  it("GUILT: an unverified legacy value never renders open, closed, or a percentage", () => {
    render(<PMABadge status="open" maxForeign={100} />);
    expect(screen.getByText("PMA unverified")).toBeDefined();
    expect(screen.queryByText("Open")).toBeNull();
    expect(screen.queryByText(/100%/)).toBeNull();
  });
});
