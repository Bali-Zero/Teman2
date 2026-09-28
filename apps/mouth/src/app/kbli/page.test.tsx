import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getSections } from "@/lib/kbli-data";

/**
 * The proof line's "N sectors" figure must never disagree with the sector
 * grid it sits above — both read `sections` (the `codeCount > 0` filter
 * from page.tsx), so this pins the count to that shared source instead of
 * a literal that can drift (regression: the line printed a hardcoded "22"
 * while the grid rendered 21 A–U categories, 2026-09-24).
 *
 * Re-pinned 2026-09-26 (BRIEF-v2 R-7, §3.4): the readings line says
 * "sections" (the brief's wording, KBLI 2025's own unit), and the landing now
 * carries TWO link lists to /kbli/sectors/* — the dial's list and the sector
 * grid. Each is counted inside its own container and both must equal the
 * same computed count, so the guard binds two consumers instead of one.
 */
async function renderPage() {
  const { default: Page } = await import("./page");
  return Page({ searchParams: Promise.resolve({}) });
}

describe("/kbli readings line", () => {
  it("prints the same sector count the sector grid renders", async () => {
    const { container } = render(await renderPage());

    const expectedCount = getSections().filter((s) => s.codeCount > 0).length;

    expect(screen.getByText(`${expectedCount} sections`)).toBeInTheDocument();

    const dialLinks = container.querySelectorAll(
      '[data-kbli-dial-list] a[href^="/kbli/sectors/"]',
    );
    expect(dialLinks.length).toBe(expectedCount);

    const gridCards = container.querySelectorAll(
      '[data-kbli-sector-grid] a[href^="/kbli/sectors/"]',
    );
    expect(gridCards.length).toBe(expectedCount);

    // Nothing else on the page links a sector: two lists, no strays.
    const allLinks = container.querySelectorAll('a[href^="/kbli/sectors/"]');
    expect(allLinks.length).toBe(expectedCount * 2);
  });
});
