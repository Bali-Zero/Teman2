import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Zero's ruling 2026-10-15 (Q11): the footer "Golden Visa" link leads to the
// Golden Visa guide article, not to the generic /services/visa page.
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("v2 Footer Golden Visa link", () => {
  it("points the link labelled Golden Visa at the guide article", async () => {
    const { Footer } = await import("./Footer");
    const { container } = render(<Footer />);
    const links = Array.from(container.querySelectorAll("a")).filter(
      (a) => a.textContent?.trim() === "Golden Visa",
    );
    expect(links.length).toBeGreaterThan(0);
    for (const a of links) {
      expect(a.getAttribute("href")).toBe(
        "/visas/golden-visa-indonesia-complete-guide",
      );
    }
  });
});
