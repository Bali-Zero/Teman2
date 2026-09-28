import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ServicePricing from "./ServicePricing";
import { SERVICES_DATA } from "@/data/services_data";

const service = {
  name: "Visa & Immigration",
  slug: "visa",
  tagline: "Visa services",
  description: "Visa services",
  bgColor: "bg-sky-500",
  iconColor: "text-sky-500",
  timeline: "Varies",
  documentsRequired: "Varies",
  validity: "Varies",
  packages: [
    {
      name: "C1 Tourism",
      description: "Tourist visa",
      price: "Contact",
      features: ["60 days"],
      popular: false,
      livePriceKey: "C1 Tourism",
      livePriceCategory: "single_entry_visas",
    },
  ],
  included: [],
  requirements: { documents: [], eligibility: [] },
  faqs: [],
};

describe("ServicePricing details dialog", () => {
  it("moves and traps focus, exposes an accessible close, and restores focus", async () => {
    const user = userEvent.setup();
    render(<ServicePricing service={service} slug="visa" />);

    const trigger = screen.getByRole("button", { name: "More Details" });
    trigger.focus();
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");

    const dialog = await screen.findByRole("dialog", { name: "C1 Tourism" });
    expect(dialog).toBeVisible();
    expect(dialog).toContainElement(
      document.activeElement as HTMLElement | null,
    );
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeVisible();

    await user.tab({ shift: true });
    expect(dialog).toContainElement(
      document.activeElement as HTMLElement | null,
    );

    await user.keyboard("{Escape}");
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});

describe("ServicePricing renders a tier-floor package's catalogue minimum", () => {
  // The REAL Monthly Tax Report package, not a hand-typed fixture — a
  // mutant that drops the "from " prefix (or the /month unit) in
  // usePackagePrice() must fail THIS render, not just a data-layer
  // assertion in services_data.tax-pricing.test.ts (2026-09-29, #7600 gate).
  const monthlyPkg = SERVICES_DATA.tax.packages.find(
    (p) => p.name === "Monthly Tax Report",
  )!;
  const taxService = { ...SERVICES_DATA.tax, packages: [monthlyPkg] };

  it('shows "from 1.800.000 IDR/month", never a bare figure', () => {
    render(<ServicePricing service={taxService} slug="tax" />);
    const card = screen.getByTestId("public-service-price-card");
    expect(within(card).getByText("from 1.800.000 IDR/month")).toBeVisible();
    expect(within(card).queryByText("Contact for quote")).toBeNull();
  });
});
