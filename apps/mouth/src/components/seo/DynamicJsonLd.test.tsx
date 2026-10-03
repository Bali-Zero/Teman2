import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/services/tax" }));

import { DynamicJsonLd } from "./DynamicJsonLd";

/**
 * The /services/tax page's ProfessionalService Offer list. A mutant that
 * reverts the tier-floor branch to a plain `price` (instead of
 * priceSpecification.minPrice) must fail HERE — services_data.tax-pricing
 * .test.ts never renders this component, so it can't see the mutant
 * (2026-09-29, #7600 gate F2c).
 */
function serviceOffers(): Record<string, unknown>[] {
  const script = document.getElementById("json-ld-professionalservice-0");
  expect(script, "ProfessionalService JSON-LD script not found").not.toBeNull();
  const schema = JSON.parse(script!.textContent ?? "{}") as {
    offers?: Record<string, unknown>[];
  };
  expect(schema.offers).toBeDefined();
  return schema.offers as Record<string, unknown>[];
}

describe("DynamicJsonLd on /services/tax", () => {
  it('Monthly Tax Report is a priceSpecification.minPrice Offer, never a plain "price"', async () => {
    render(<DynamicJsonLd />);
    await waitFor(() =>
      expect(
        document.getElementById("json-ld-professionalservice-0"),
      ).not.toBeNull(),
    );

    const monthly = serviceOffers().find(
      (offer) => offer.name === "Monthly Tax Report",
    );
    expect(monthly).toBeDefined();
    expect(monthly).not.toHaveProperty("price");
    expect(monthly?.priceSpecification).toEqual({
      "@type": "UnitPriceSpecification",
      minPrice: 1_800_000,
      priceCurrency: "IDR",
      unitText: "MONTH",
    });
  });

  it('an exact-SKU package (NPWP Personal + Coretax) keeps a plain "price", not priceSpecification', async () => {
    render(<DynamicJsonLd />);
    await waitFor(() =>
      expect(
        document.getElementById("json-ld-professionalservice-0"),
      ).not.toBeNull(),
    );

    const npwp = serviceOffers().find(
      (offer) => offer.name === "NPWP Personal + Coretax",
    );
    expect(npwp).toBeDefined();
    expect(npwp).not.toHaveProperty("priceSpecification");
    expect(npwp?.price).toBe("1000000");
    expect(npwp?.priceCurrency).toBe("IDR");
  });

  it("Contact-only packages (SPT Annual Company (Operational)) emit no Offer at all", async () => {
    render(<DynamicJsonLd />);
    await waitFor(() =>
      expect(
        document.getElementById("json-ld-professionalservice-0"),
      ).not.toBeNull(),
    );

    const names = serviceOffers().map((offer) => offer.name);
    expect(names).not.toContain("SPT Annual Company (Operational)");
  });
});
