import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getSections } from "@/lib/kbli-data";

/**
 * The proof line's "N sectors" figure must never disagree with the sector
 * grid it sits above — both read `sections` (the `codeCount > 0` filter
 * from page.tsx), so this pins the count to that shared source instead of
 * a literal that can drift (regression: the line printed a hardcoded "22"
 * while the grid rendered 21 A–U categories, 2026-09-24).
 */
async function renderPage() {
  const { default: Page } = await import("./page");
  return Page({ searchParams: Promise.resolve({}) });
}

describe("/kbli proof line", () => {
  it("prints the same sector count the sector grid renders", async () => {
    const { container } = render(await renderPage());

    const expectedCount = getSections().filter((s) => s.codeCount > 0).length;

    expect(screen.getByText(`${expectedCount} sectors`)).toBeInTheDocument();

    const renderedCards = container.querySelectorAll(
      'a[href^="/kbli/sectors/"]',
    );
    expect(renderedCards.length).toBe(expectedCount);
  });
});
