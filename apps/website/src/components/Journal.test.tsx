import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Journal } from "./Journal";
import { getPublicJournalArticles } from "../content/journal";

describe("Journal publishing input", () => {
  it("keeps navigation without inventing a feature when no records arrive", () => {
    render(<Journal articles={[]} indexHref="https://balizero.com/news" />);
    expect(screen.getByRole("status")).toHaveTextContent("No stories have been published");
    expect(screen.getByRole("link", { name: /Explore the Journal/ })).toHaveAttribute("href", "https://balizero.com/news");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("handles a feed shrinking after carousel navigation", async () => {
    const user = userEvent.setup();
    const records = getPublicJournalArticles();
    const { rerender } = render(<Journal articles={records} />);
    await user.click(screen.getByRole("button", { name: "Next editorial story" }));
    expect(screen.getByText("02 / 02")).toBeVisible();
    rerender(<Journal articles={records.slice(0, 1)} />);
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(records[0].title);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    rerender(<Journal articles={[]} />);
    expect(screen.getByRole("status")).toBeVisible();
  });
});
