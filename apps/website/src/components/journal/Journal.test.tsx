import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  developmentOnlyArticleFixture,
  type JournalArticle,
} from "../../content/journal";
import { ArticleTemplate } from "./ArticleTemplate";
import { JournalIndex } from "./JournalIndex";

const verifiedArticle: JournalArticle = {
  title: "Verified editorial record",
  slug: "verified-editorial-record",
  image: { src: "/assets/kbli.jpg", alt: "Verified story cover" },
  category: "Business",
  date: { iso: "2026-09-04", label: "4 September 2026" },
  sourceUrl: "https://balizero.com/business/verified-editorial-record",
  finalSourceUrl:
    "https://balizero.com/business/verified-editorial-record",
  verificationStatus: "verified",
};

describe("JournalIndex", () => {
  it("keeps verified metadata and the source destination in one card", () => {
    render(<JournalIndex articles={[verifiedArticle]} />);

    const card = screen.getByRole("article");
    expect(within(card).getByRole("heading", { level: 3 })).toHaveTextContent(
      verifiedArticle.title,
    );
    expect(within(card).getByRole("img")).toHaveAttribute(
      "src",
      verifiedArticle.image.src,
    );
    expect(within(card).getByText(verifiedArticle.category!)).toBeVisible();
    expect(within(card).getByText(verifiedArticle.date!.label)).toHaveAttribute(
      "datetime",
      verifiedArticle.date!.iso,
    );
    expect(within(card).getByRole("link")).toHaveAttribute(
      "href",
      verifiedArticle.finalSourceUrl,
    );
    expect(screen.getByRole("link", { name: "Services" })).toHaveAttribute(
      "href",
      "/services",
    );
    expect(
      screen.getByRole("heading", { level: 2, name: "Selected stories" }),
    ).toBeInTheDocument();
  });

  it("shows an explicit state instead of unverified or dummy cards", () => {
    render(<JournalIndex articles={[]} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "No verified stories are available yet.",
    );
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });
});

describe("ArticleTemplate", () => {
  it("marks its development fixture as excluded from indexing", () => {
    const { container } = render(
      <ArticleTemplate article={developmentOnlyArticleFixture} />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Development fixture — not published or indexed",
    );
    expect(container.querySelector("article")).toHaveAttribute(
      "data-indexing",
      "excluded",
    );
    expect(screen.getByRole("link", { name: /original source/i })).toHaveAttribute(
      "href",
      "https://example.invalid/development-fixture",
    );
  });
});
