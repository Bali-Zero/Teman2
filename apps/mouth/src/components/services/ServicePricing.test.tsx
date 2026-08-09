import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ServicePricing from "./ServicePricing";

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
