import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Privacy from "./page";

describe("/privacy disclosures", () => {
  it("carries the TD-PSE number, analytics, Vercel, cookies and complaint clauses", () => {
    const text = render(<Privacy />).container.textContent ?? "";
    expect(text).not.toContain("[Pending]");
    expect(text).toContain("029817.01/DJAI.PSE/09/2026");
    for (const clause of [
      "Google Analytics",
      "Vercel",
      "26 months",
      "Cookie Policy",
      "Lodge a complaint",
    ]) {
      expect(text).toContain(clause);
    }
  });
});
