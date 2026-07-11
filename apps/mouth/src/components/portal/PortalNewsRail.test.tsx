import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { PortalNewsRail, relevantCategories } from "./PortalNewsRail";
import type { ArticleListItem } from "@/lib/blog/types";

function article(
  id: string,
  category: ArticleListItem["category"],
  title: string,
): ArticleListItem {
  return {
    id,
    slug: `slug-${id}`,
    title,
    excerpt: "",
    coverImage: "/x.jpg",
    category,
    author: { id: "a", name: "Z", avatar: "", role: "", isAI: true },
    publishedAt: new Date("2026-01-01"),
    readingTime: 4,
    viewCount: 0,
    featured: false,
    trending: false,
    aiGenerated: true,
  };
}

describe("relevantCategories — practice → article-category mapping", () => {
  it("maps visa/kitas practices to the visas category", () => {
    expect(relevantCategories(["visa_extension"])).toContain("visas");
    expect(relevantCategories(["KITAS_renewal"])).toContain("visas");
  });

  it("maps company/PMA to business", () => {
    expect(relevantCategories(["pt_pma_setup"])).toContain("business");
  });

  it("maps tax/lkpm to taxes and property to property", () => {
    expect(relevantCategories(["tax_retainer", "lkpm_q1"])).toContain("taxes");
    expect(relevantCategories(["property_lease"])).toContain("property");
  });

  it("returns empty for unknown / no practices", () => {
    expect(relevantCategories([])).toEqual([]);
    expect(relevantCategories(undefined)).toEqual([]);
    expect(relevantCategories(["something_unmapped"])).toEqual([]);
  });

  it("dedupes when several practices map to the same category", () => {
    const cats = relevantCategories(["visa_a", "kitas_b", "immigration_c"]);
    expect(cats.filter((c) => c === "visas")).toHaveLength(1);
  });
});

describe("PortalNewsRail — rendering", () => {
  const articles = [
    article("1", "visas", "New KITAS rule 2026"),
    article("2", "business", "PT PMA capital change"),
    article("3", "property", "Leasehold zoning update"),
    article("4", "taxes", "SPT deadline moved"),
  ];

  it("prioritises articles relevant to the client's practices", () => {
    render(<PortalNewsRail articles={articles} practiceKinds={["visa"]} />);
    // The visa article should render with a "Relevant to your visas" hint
    expect(screen.getByText("New KITAS rule 2026")).toBeTruthy();
    expect(screen.getByText(/Relevant to your visas/)).toBeTruthy();
  });

  it("still shows a backfilled rail when no practice matches (never empty)", () => {
    render(<PortalNewsRail articles={articles} practiceKinds={[]} limit={2} />);
    // backfill by recency → shows reading-time hint instead of relevance
    expect(screen.getByText("The Bali Zero Dispatch")).toBeTruthy();
    expect(screen.getAllByText(/min read/).length).toBeGreaterThan(0);
  });

  it("links to marketing articles outside the portal domain without Next prefetch", () => {
    render(<PortalNewsRail articles={articles} practiceKinds={["visa"]} />);
    const articleLink = screen.getByRole("link", {
      name: /New KITAS rule 2026/i,
    });
    expect(articleLink.getAttribute("href")).toBe(
      "https://balizero.com/visas/slug-1",
    );
    expect(articleLink.getAttribute("target")).toBe("_blank");

    const newsLink = screen.getByRole("link", { name: /More from Bali Zero/i });
    expect(newsLink.getAttribute("href")).toBe("https://balizero.com/news");
  });

  it("renders nothing when there are no articles", () => {
    const { container } = render(
      <PortalNewsRail articles={[]} practiceKinds={["visa"]} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
