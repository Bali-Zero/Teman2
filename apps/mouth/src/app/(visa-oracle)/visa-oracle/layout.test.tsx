/**
 * Regression for #3732 (2026-08-07): a metadata rewrite silently dropped
 * `robots: { index: false, follow: false }` from this layout — present since
 * #2617 (2026-07-18) — with no test to catch it. The engine runs in SHADOW
 * (verdicts are not authoritative) and DPIA §8 is unsigned, so the route
 * must stay out of search indexes until Zero ratifies it (conditions: DPIA
 * §8 signed, seq-13 active with its two doctrine gaps cured, a
 * SHADOW→ENFORCE decision or accuracy gate passed, E30 prices defined).
 * Restored 2026-08-23 (Legge 5).
 *
 * This unit test pins the exported `metadata` object only — it cannot prove
 * what actually ships in the response (a page-level override, a route move,
 * or a Next merge-semantics change would all be invisible here). The served
 * <head> is asserted separately in e2e/visa-oracle-v2.spec.ts.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import VisaOracleLayout, { metadata } from "./layout";

describe("visa-oracle layout metadata: SHADOW engine stays out of search indexes", () => {
  it("guilt: robots directive is present and blocks both index and follow", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });

  it("innocence: title and description are untouched", () => {
    expect(metadata.title).toBe("Visa Oracle");
    expect(metadata.description).toBe(
      "Bilingual decision support for Indonesian visa pathways, backed by deterministic evaluation and dated sources.",
    );
  });

  it("innocence: children still render through the layout", () => {
    render(<VisaOracleLayout>oracle child</VisaOracleLayout>);
    expect(screen.getByText("oracle child")).toBeInTheDocument();
  });
});
