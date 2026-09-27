/**
 * R19 group-B / surface-2 guard (CLAUDE.md Builder Contract, R19 restyle,
 * 2026-09-28): renders CategoryNav, ArticleGrid/ArticleCard and
 * CategoryContent's own hero + sidebar markup, then fails if any element's
 * className carries a pre-R19 literal-color / gradient / hardcoded-dark
 * utility. It must be RED against origin/main's versions of these 4 files
 * and GREEN after the restyle (see the lane report for the red tail).
 *
 * NewsletterSidebar (`components/blog/NewsletterForm.tsx`) is a DIFFERENT
 * lane's file, deliberately left pre-R19 (purple/fuchsia) — it is stubbed
 * out here so it can't fail a guard it was never meant to satisfy.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock("@/components/blog/NewsletterForm", async () => {
  const actual = await vi.importActual<
    typeof import("@/components/blog/NewsletterForm")
  >("@/components/blog/NewsletterForm");
  return { ...actual, NewsletterSidebar: () => null };
});

import { CategoryNav } from "./CategoryNav";
import { ArticleGrid } from "./ArticleGrid";
import { R19HomeProvider } from "@/components/r19/R19Presentation";
import CategoryContent from "@/app/(blog)/[category]/CategoryContent";
import type { ArticleCategory, ArticleListItem } from "@/lib/blog/types";

const FORBIDDEN = [
  // literal hex color in a className (a var() fallback lives in inline
  // style, never in a class string, so any hex here is a real offender)
  /#[0-9a-fA-F]{3,8}/,
  /bg-gradient-/,
  /linear-gradient/,
  /(^|\s)(bg|text|border|from|via|to)-(sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d+/,
  /(^|\s)text-white(\/\d+)?(\s|$)/,
  /(^|\s)bg-black(\/\d+)?(\s|$)/,
  /(^|\s)border-white(\/\d*)?(\s|$)/,
  /(^|\s)bg-white(\/\d+)?(\s|$)/,
  /font-black/,
  /font-extrabold/,
];

function forbiddenHitsIn(container: HTMLElement): string[] {
  const hits: string[] = [];
  container.querySelectorAll("[class]").forEach((el) => {
    const cls = el.getAttribute("class") || "";
    for (const re of FORBIDDEN) {
      if (re.test(cls)) hits.push(`${el.tagName}.${cls} -> ${re}`);
    }
  });
  return hits;
}

function article(
  n: number,
  overrides: Partial<ArticleListItem> = {},
): ArticleListItem {
  return {
    id: `id-${n}`,
    slug: `slug-${n}`,
    title: `Article ${n}`,
    excerpt: "excerpt",
    coverImage: "/c.jpg",
    category: "visas" as ArticleCategory,
    author: { id: "a", name: "Team", role: "Editorial" },
    publishedAt: new Date("2026-01-04T00:00:00Z"),
    readingTime: 3,
    viewCount: 1200 + n,
    featured: n === 1,
    trending: n === 2,
    aiGenerated: n === 3,
    ...overrides,
  } as unknown as ArticleListItem;
}

describe("R19 group-B surface-2 guard: no pre-R19 classes", () => {
  it("CategoryNav (R19 route context)", () => {
    const { container } = render(
      <R19HomeProvider>
        <CategoryNav activeCategory="visas" />
      </R19HomeProvider>,
    );
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("ArticleGrid + ArticleCard (featured, trending, ai-generated)", () => {
    const { container } = render(
      <ArticleGrid
        articles={[article(1), article(2), article(3), article(4)]}
        variant="grid"
        columns={2}
        showFeatured
      />,
    );
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("CategoryContent hero + popular sidebar (NewsletterSidebar stubbed, not this lane's file)", () => {
    const { container } = render(
      <R19HomeProvider>
        <CategoryContent
          articles={[article(1), article(2), article(3), article(4)]}
          category="visas"
        />
      </R19HomeProvider>,
    );
    // eyebrow renders (distinct from CategoryNav's "Visas" pill label)
    expect(
      screen.getByText("Visas", { selector: "div.uppercase" }),
    ).toBeInTheDocument();
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("popular sidebar keeps the canonical /<category>/<slug> links (behavior unchanged)", () => {
    render(
      <R19HomeProvider>
        <CategoryContent
          articles={[article(1), article(2), article(3), article(4)]}
          category="visas"
        />
      </R19HomeProvider>,
    );
    const popular = screen
      .getByText(/^Popular in /)
      .closest("div") as HTMLElement;
    const hrefs = within(popular)
      .getAllByRole("link")
      .map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["/visas/slug-1", "/visas/slug-2", "/visas/slug-3"]);
  });
});
