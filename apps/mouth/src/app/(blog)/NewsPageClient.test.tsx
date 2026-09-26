import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import NewsPageClient from "./NewsPageClient";
import type { ArticleListItem } from "@/lib/blog/types";

vi.mock("@/app/v2/_components/NewsHero", () => ({
  NewsHero: ({ articles }: { articles: ArticleListItem[] }) => (
    <div data-testid="featured">
      {articles.map((a) => (
        <a key={a.id} href={"/" + a.category + "/" + a.slug}>
          {a.title}
        </a>
      ))}
    </div>
  ),
}));
afterEach(cleanup);
const articles = Array.from(
  { length: 23 },
  (_, i) =>
    ({
      id: String(i),
      slug: "fixture-" + i,
      title: "Fixture article " + i,
      excerpt: i < 5 ? "five-match" : "other",
      category: "business",
      coverImage: "",
      readingTime: 3,
    }) as ArticleListItem,
);

describe("News result completeness", () => {
  it.each([1, 5])(
    "renders all %i matches once and removes unrelated featured articles",
    (count) => {
      const query = count === 1 ? "article 22" : "five-match";
      render(<NewsPageClient articles={articles} initialQuery={query} />);
      const links = screen
        .getAllByRole("link")
        .filter((a) =>
          a.getAttribute("href")?.startsWith("/business/fixture-"),
        );
      expect(links).toHaveLength(count);
      expect(screen.queryByTestId("featured")).not.toBeInTheDocument();
      expect(links[0]).toHaveAttribute(
        "href",
        count === 1 ? "/business/fixture-22" : "/business/fixture-0",
      );
    },
  );

  it("explains a zero-result search", () => {
    render(<NewsPageClient articles={articles} initialQuery="no-match" />);
    expect(
      screen.getByText(/No articles match your search/),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("featured")).not.toBeInTheDocument();
    expect(screen.queryByText("Browse by topic")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("0 results");
  });

  it("makes articles beyond the initial grid reachable", () => {
    render(<NewsPageClient articles={articles} initialQuery="Fixture" />);
    expect(
      screen.queryByRole("heading", { name: "Fixture article 22" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show more articles" }));
    expect(
      screen.getByRole("heading", { name: "Fixture article 12" }).closest("a"),
    ).toHaveFocus();
    expect(
      screen.getByRole("heading", { name: "Fixture article 22" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Show more articles" }),
    ).not.toBeInTheDocument();
  });

  it("restores featured articles on clearing search without duplicating them in the grid", () => {
    render(<NewsPageClient articles={articles} initialQuery="no-match" />);
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByTestId("featured")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link")
        .filter((a) => a.getAttribute("href") === "/business/fixture-0"),
    ).toHaveLength(1);
  });

  it("treats whitespace as browsing and does not promise new articles when featured items exist", () => {
    render(
      <NewsPageClient articles={articles.slice(0, 5)} initialQuery="   " />,
    );
    expect(screen.queryByText(/result.*for/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Fresh pieces/)).not.toBeInTheDocument();
    expect(
      screen.getByText("All available articles are featured above."),
    ).toBeInTheDocument();
    expect(
      screen
        .getByRole("searchbox")
        .compareDocumentPosition(screen.getByTestId("featured")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
