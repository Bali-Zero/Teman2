import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { HandoffWaLink } from "../HandoffWaLink";

describe("HandoffWaLink", () => {
  it("generates a wa.me URL with encoded quiz summary", () => {
    render(
      <HandoffWaLink
        phone="+6285156005858"
        nationality="ITA"
        purpose="investor"
        durationMonths={12}
        budgetBand="under_50m"
        reason="Investor routes all have minimum capital requirements."
      />
    );
    const link = screen.getByRole("link", { name: /whatsapp/i });
    const href = link.getAttribute("href")!;
    expect(href.startsWith("https://wa.me/6285156005858?text=")).toBe(true);
    const decoded = decodeURIComponent(href.split("?text=")[1]);
    expect(decoded).toContain("ITA");
    expect(decoded).toContain("investor");
    expect(decoded).toContain("12 months");
    expect(decoded).toContain("under_50m");
    expect(decoded).toContain("minimum capital");
  });

  it("normalises leading + in phone", () => {
    render(
      <HandoffWaLink
        phone="+6285156005858"
        nationality="USA" purpose="other" durationMonths={6}
        budgetBand="50m_500m" reason="..."
      />
    );
    const href = screen.getByRole("link").getAttribute("href")!;
    expect(href).toContain("wa.me/6285156005858");
    expect(href).not.toContain("wa.me/+");
  });
});
