import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Journal } from "./Journal";
import { ArticleDestination } from "./journal/ArticleDestination";
import type { JournalArticle } from "./journal/types";
afterEach(cleanup);
const articles: JournalArticle[] = [1, 2].map((i) => ({
  title: "Synthetic story " + i,
  slug: "story-" + i,
  category: "Business",
  date: null,
  image: null,
  sourceUrl: "/business/story-" + i,
  finalSourceUrl: null,
  destinationStatus: "available",
}));
describe("R19 Journal presentation", () => {
  it("moves between real supplied stories using buttons and arrow keys", () => {
    render(<Journal articles={articles} />);
    expect(
      screen.getByRole("link", { name: "Synthetic story 1" }),
    ).toBeDefined();
    fireEvent.click(
      screen.getByRole("button", { name: "Next editorial story" }),
    );
    expect(
      screen.getByRole("link", { name: "Synthetic story 2" }),
    ).toBeDefined();
    fireEvent.keyDown(screen.getByLabelText("Featured editorial stories"), {
      key: "ArrowLeft",
    });
    expect(
      screen.getByRole("link", { name: "Synthetic story 1" }),
    ).toBeDefined();
  });
  it("renders an unavailable destination without a clickable link", () => {
    render(
      <ArticleDestination
        article={{ ...articles[0], destinationStatus: "unavailable" }}
      >
        Synthetic story
      </ArticleDestination>,
    );
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("Synthetic story")).toBeDefined();
  });
  it("distinguishes unavailable from empty and hides stale supplied stories", () => {
    render(<Journal articles={articles} status="unavailable" />);
    expect(screen.getByRole("status").textContent).toContain(
      "temporarily unavailable",
    );
    expect(
      screen.queryByRole("link", { name: "Synthetic story 1" }),
    ).toBeNull();
  });
});
