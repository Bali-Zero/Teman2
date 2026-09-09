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
      verifiedArticle.image!.src,
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
      "No stories have been published in this edition yet.",
    );
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });
});

describe("ArticleTemplate", () => {
  it("gives sections unique targets after all Markdown heading levels", () => {
    const { container } = render(<ArticleTemplate article={{ metadata: verifiedArticle, indexing: "public", standfirst: "Published introduction", sections: [{ heading: "Same", paragraphs: ["Section text"] }, { heading: "Deep", paragraphs: ["Deep section text"] }], markdown: '## Same\n\n## Same\n\n## Same 2\n\n#### Deep\n\n##### Deep\n\n###### Deep' }} />);
    const ids = [...container.querySelectorAll("h1[id],h2[id],h3[id],h4[id],h5[id],h6[id]")].filter((heading) => !heading.closest("footer")).map((heading) => heading.id);
    expect(ids).toEqual(["same", "same-2", "same-2-2", "deep", "deep-2", "deep-3", "same-3", "deep-4"]);
    expect(new Set(ids).size).toBe(ids.length);
    const contents = screen.getByRole("navigation", { name: "Article contents" });
    for (const link of within(contents).getAllByRole("link").filter((link) => link.textContent !== "Back to top ↑")) {
      expect(container.querySelectorAll(`[id="${link.getAttribute("href")!.slice(1)}"]`)).toHaveLength(1);
    }
  });

  it("keeps authored contextual help once while retaining sharing", () => {
    render(<ArticleTemplate article={{ metadata: verifiedArticle, indexing: "public", standfirst: "Published introduction", sections: [], markdown: '<InfoCard><AskZantara questions={["Published question?"]} /></InfoCard>' }} />);
    expect(screen.getAllByRole("region", { name: "A question about this article?" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Published question?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy article link" })).toBeInTheDocument();
  });

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
    expect(screen.queryByRole("link", { name: /published edition/i })).toBeNull();
  });
});
