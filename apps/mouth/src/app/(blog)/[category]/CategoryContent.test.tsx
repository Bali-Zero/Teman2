import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock("@/components/blog", () => ({
  ArticleGrid: () => null,
  ArticleGridSkeleton: () => null,
  CategoryNav: () => null,
  NewsletterSidebar: () => null,
}));

import CategoryContent from "./CategoryContent";
import type { ArticleCategory, ArticleListItem } from "@/lib/blog/types";

function item(
  n: number,
  category: ArticleCategory,
  slug: string,
): ArticleListItem {
  return {
    id: `id-${n}`,
    slug,
    title: `Article ${n}`,
    excerpt: "e",
    coverImage: "/c.jpg",
    category,
    author: { id: "a", name: "Team", role: "Editorial" },
    publishedAt: new Date("2026-01-04T00:00:00Z"),
    readingTime: 3,
    viewCount: 1200 + n,
    featured: false,
    trending: false,
    aiGenerated: false,
  } as unknown as ArticleListItem;
}

const CATEGORIES: ArticleCategory[] = [
  "visas",
  "business",
  "taxes",
  "living",
  "trends",
];

// Regression: the "Popular in <category>" sidebar linked to
// /news/<category>/<slug>, which is a 404 on production; the canonical
// article URL is /<category>/<slug> (measured live: /business/<slug> 200,
// /news/business/<slug> 404). 15 links across 5 category pages were dead.
describe("CategoryContent popular links", () => {
  it.each(CATEGORIES)(
    "links %s articles to the canonical /<category>/<slug> URL",
    (category) => {
      const articles = [
        item(1, category, "first-slug"),
        item(2, category, "second-slug"),
        item(3, category, "third-slug"),
        item(4, category, "fourth-slug"),
      ];
      render(<CategoryContent articles={articles} category={category} />);

      const popular = screen
        .getByText(/^Popular in /)
        .closest("div") as HTMLElement;
      const hrefs = within(popular)
        .getAllByRole("link")
        .map((a) => a.getAttribute("href"));

      expect(hrefs).toEqual([
        `/${category}/first-slug`,
        `/${category}/second-slug`,
        `/${category}/third-slug`,
      ]);
      for (const href of hrefs) {
        expect(href).not.toMatch(/^\/news\/[a-z]+\//);
      }
    },
  );
});
