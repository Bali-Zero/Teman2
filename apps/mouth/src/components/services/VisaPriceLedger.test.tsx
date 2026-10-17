import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import ServicePricing from "./ServicePricing";
import { SERVICES_DATA } from "@/data/services_data";
import { buildVisaLedger } from "@/data/visa-price-ledger";
import { getExactSnapshotPrice } from "@/lib/pricing-snapshot";

const visa = { ...SERVICES_DATA.visa };
const PACKAGES = SERVICES_DATA.visa.packages;

describe("the visa price list renders as a chaptered ledger", () => {
  it("keeps one price element per catalogue row, each carrying its exact figure", () => {
    render(<ServicePricing service={visa} slug="visa" />);
    const cards = screen.getAllByTestId("public-service-price-card");
    expect(cards).toHaveLength(PACKAGES.length);
    for (const card of cards) {
      const category = card.getAttribute("data-pricing-category");
      const key = card.getAttribute("data-pricing-key");
      expect(category).toBeTruthy();
      expect(key).toBeTruthy();
      const price = getExactSnapshotPrice(category as string, key as string);
      expect(price).not.toBeNull();
      expect(card.textContent).toContain(price as string);
      expect(
        within(card).getByRole("button", { name: /^More Details/ }),
      ).toBeInTheDocument();
    }
  });

  it("indexes the chapters and renders them in the ledger's order", () => {
    render(<ServicePricing service={visa} slug="visa" />);
    const ledger = buildVisaLedger(PACKAGES);
    const [index] = screen.getAllByRole("navigation", {
      name: "Price list chapters",
    });
    const links = within(index).getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual(
      ledger.chapters.map((chapter) => `#chapter-${chapter.id}`),
    );
    const headings = screen.getAllByRole("heading", { level: 3 });
    expect(headings.map((heading) => heading.textContent)).toEqual(
      ledger.chapters.map((chapter) => chapter.title),
    );
    const first = screen.getAllByTestId("public-service-price-card")[0];
    expect(first.getAttribute("data-pricing-key")).toBe(
      PACKAGES[0].livePriceKey,
    );
  });

  it("opens the shared details dialog from a matrix cell", async () => {
    const user = userEvent.setup();
    render(<ServicePricing service={visa} slug="visa" />);
    const table = screen.getByRole("region", { name: "Work" });
    const cell = within(table)
      .getAllByTestId("public-service-price-card")
      .find(
        (el) =>
          el.getAttribute("data-pricing-key") === "Working KITAS (Offshore)",
      );
    expect(cell).toBeDefined();
    const trigger = within(cell as HTMLElement).getByRole("button", {
      name: "More Details: Working KITAS (Offshore)",
    });
    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", {
      name: "Working KITAS (Offshore)",
    });
    expect(dialog).toBeVisible();
    expect(within(dialog).getByText("All-inclusive pricing")).toBeVisible();
  });

  it("leaves the card grid in place for the other service slugs", () => {
    render(<ServicePricing service={SERVICES_DATA.company} slug="company" />);
    expect(screen.queryByTestId("visa-price-ledger")).toBeNull();
    expect(screen.getAllByTestId("public-service-price-card")).toHaveLength(
      SERVICES_DATA.company.packages.length,
    );
  });
});
