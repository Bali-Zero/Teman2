import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { CTAHandoff } from "./CTAHandoff";

describe("CTAHandoff", () => {
  it("renders three tiers in order: PDF, Zantara, WA", () => {
    const { getAllByRole } = render(
      <CTAHandoff
        source="visa-oracle"
        sessionId="abc"
        pdfHref="/api/report.pdf"
        onZantaraClick={() => {}}
      />,
    );
    const links = getAllByRole("link");
    expect(links[0].getAttribute("href")).toBe("/api/report.pdf");
    expect(links[1].getAttribute("href")).toMatch(/wa\.me\/628213107363/);
  });

  it("falls back to WA-only when pdf/Zantara missing", () => {
    const { getAllByRole } = render(
      <CTAHandoff source="kbli" sessionId="xyz" />,
    );
    const links = getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toMatch(/wa\.me/);
  });
});
