import { describe, it, expect } from "vitest";
import { getFunnelNavItems } from "./funnel-nav";

describe("getFunnelNavItems", () => {
  it("always puts Home first", () => {
    expect(getFunnelNavItems("visa")[0]).toEqual({
      label: "Home",
      href: "https://balizero.com/",
    });
  });

  it("returns exactly 4 items (Home + 3 siblings)", () => {
    for (const f of ["visa", "kbli", "tax", "property"] as const) {
      expect(getFunnelNavItems(f)).toHaveLength(4);
    }
  });

  it("excludes the current funnel from siblings", () => {
    const onVisa = getFunnelNavItems("visa");
    expect(onVisa.some((item) => item.label === "Visa")).toBe(false);
    const onProperty = getFunnelNavItems("property");
    expect(onProperty.some((item) => item.label === "Property")).toBe(false);
  });

  it("every funnel lists Property as a sibling when not self", () => {
    // This is the UX bug the fix addresses — Property was missing from
    // every nav in the pre-fix implementation.
    for (const f of ["visa", "kbli", "tax"] as const) {
      const items = getFunnelNavItems(f);
      const propertyItem = items.find((i) => i.label === "Property");
      expect(propertyItem).toBeDefined();
      expect(propertyItem?.href).toBe("/property/eligibility");
    }
  });

  it("matches expected URLs for each sibling", () => {
    const onVisa = getFunnelNavItems("visa");
    expect(onVisa.find((i) => i.label === "KBLI")?.href).toBe("/kbli");
    expect(onVisa.find((i) => i.label === "Tax")?.href).toBe(
      "https://tax.balizero.com/",
    );
    expect(onVisa.find((i) => i.label === "Property")?.href).toBe(
      "/property/eligibility",
    );
  });
});
