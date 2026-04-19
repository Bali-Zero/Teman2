import { describe, it, expect } from "vitest";
import { buildWhatsAppLink } from "./whatsapp-utm";

describe("buildWhatsAppLink", () => {
  it("builds link with default greeting and UTM for home", () => {
    const link = buildWhatsAppLink("home");
    expect(link).toContain("https://wa.me/628213107363");
    expect(link).toContain("utm_source=balizero_web");
    expect(link).toContain("utm_medium=whatsapp_cta");
    expect(link).toContain("utm_campaign=home");
  });

  it("encodes funnel-specific greeting and campaign for visa", () => {
    const link = buildWhatsAppLink("visa");
    expect(link).toContain("utm_campaign=visa");
    expect(link).toMatch(/text=.*visa/i);
  });

  it("encodes special characters in custom greeting", () => {
    const link = buildWhatsAppLink(
      "kbli",
      "Custom: question with spaces & symbols",
    );
    // URLSearchParams encodes : as %3A, space as +, & as %26
    expect(link).toMatch(/Custom%3A/);
    expect(link).toMatch(/%26/);
  });

  it("falls back to home if funnel unknown", () => {
    const link = buildWhatsAppLink("nonexistent_funnel");
    expect(link).toContain("utm_campaign=home");
  });

  it("uses correct UTM for all 4 known funnels", () => {
    for (const funnel of ["visa", "kbli", "tax", "property"] as const) {
      const link = buildWhatsAppLink(funnel);
      expect(link).toContain(`utm_campaign=${funnel}`);
    }
  });
});
