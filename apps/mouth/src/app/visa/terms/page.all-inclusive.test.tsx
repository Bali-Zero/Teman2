import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TermsPage from "./page";

// Zero's ruling 2026-10-15 (Q7, standing rule R1 2026-07-17): the price shown
// is ONE all-inclusive amount. The Service Pricing section must not tell the
// visitor that government fees are billed separately.
function pricingSectionText(container: HTMLElement): string {
  const section = Array.from(container.querySelectorAll("section")).find((s) =>
    /Service Pricing/.test(s.querySelector("h2")?.textContent ?? ""),
  );
  expect(section).toBeDefined();
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

describe("/visa/terms Service Pricing section", () => {
  it("says the price is all-inclusive of government fees and the service", () => {
    const { container } = render(<TermsPage />);
    expect(pricingSectionText(container)).toMatch(
      /all-inclusive: government fees and the Bali Zero service are included/,
    );
  });

  it("no longer says government fees are separate", () => {
    const { container } = render(<TermsPage />);
    const text = pricingSectionText(container);
    expect(text).not.toMatch(/government fees are separate/i);
    expect(text).not.toMatch(/service fees/i);
  });
});
