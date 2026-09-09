import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JournalIndex } from "./JournalIndex";
describe("recoverable Journal search", () => {
  it("preserves query and category across pages and resets pagination when changing topic", () => {
    render(
      <JournalIndex
        articles={[]}
        status="empty"
        query={{ q: "property lease", category: "property", page: 2 }}
        hasMore
      />,
    );
    expect(screen.getByRole("searchbox")).toHaveValue("property lease");
    expect(screen.getByRole("link", { name: "Next →" })).toHaveAttribute(
      "href",
      "/news?q=property+lease&category=property&page=3#latest-stories-title",
    );
    expect(screen.getByRole("link", { name: "← Previous" })).toHaveAttribute(
      "href",
      "/news?q=property+lease&category=property#latest-stories-title",
    );
    expect(
      within(
        screen.getByRole("navigation", { name: "Journal topics" }),
      ).getByRole("link", { name: "Taxes" }),
    ).toHaveAttribute(
      "href",
      "/news?q=property+lease&category=taxes#latest-stories-title",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "There are no stories on page 2",
    );
  });
  it("distinguishes unavailable from empty and retries the exact selection", () => {
    render(
      <JournalIndex
        articles={[]}
        status="unavailable"
        query={{ q: "lease", category: "property", page: 3 }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "temporarily unavailable",
    );
    expect(
      screen.getByRole("link", { name: "Try this search again" }),
    ).toHaveAttribute(
      "href",
      "/news?q=lease&category=property&page=3#latest-stories-title",
    );
    expect(screen.queryByText(/No stories match/)).not.toBeInTheDocument();
  });
  it("keeps tools separate from article filters", () => {
    render(<JournalIndex articles={[]} status="empty" />);
    const tools = screen.getByRole("navigation", { name: "Bali Zero tools" });
    expect(
      within(tools).getByRole("link", { name: /Visa Oracle/ }),
    ).toHaveAttribute("href", "/visa-oracle");
    expect(
      within(tools).getByRole("link", { name: /KBLI Navigator/ }),
    ).toHaveAttribute("href", "/kbli");
  });
});
