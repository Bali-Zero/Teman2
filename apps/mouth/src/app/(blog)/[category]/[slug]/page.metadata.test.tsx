import { beforeEach, describe, expect, it, vi } from "vitest";
import { getArticleByLocale, getArticleBySlug } from "@/lib/blog/articles";
import { CATEGORY_MAP } from "@/lib/blog/categories";
import { generateArticleMetadata } from "@/lib/blog/metadata";
import type { Article, ArticleCategory } from "@/lib/blog/types";
import { generateMetadata } from "./page";
import { generateMetadata as categoryMetadata } from "../layout";

vi.mock("@/lib/blog/articles", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/blog/articles")>()),
  getArticleBySlug: vi.fn(),
  getArticleByLocale: vi.fn(),
}));
vi.mock("./ArticleClient", () => ({ ArticleClient: () => null }));
vi.mock("@/components/blog/MDXContentRSC", () => ({ renderMDXBody: vi.fn() }));
vi.mock("next/navigation", async (importOriginal) =>
  importOriginal<typeof import("next/navigation")>(),
);

const article: Article = {
  id: "synthetic-article",
  slug: "bali-digital-nomad-complete-guide",
  title: "Synthetic article title",
  excerpt: "Synthetic article description.",
  content: "Synthetic article body.",
  coverImage: "/static/og-image.jpg",
  coverImageAlt: "Synthetic cover",
  category: "living",
  tags: [],
  author: {
    id: "synthetic-author",
    name: "Test author",
    avatar: "",
    role: "Test",
    isAI: false,
  },
  createdAt: new Date("2026-01-01T00:00:00Z"),
  updatedAt: new Date("2026-01-01T00:00:00Z"),
  status: "published",
  featured: false,
  trending: false,
  readingTime: 1,
  viewCount: 0,
  shareCount: 0,
  likeCount: 0,
  commentCount: 0,
  aiGenerated: false,
  relatedArticleIds: [],
  locale: "en",
};

const metadata = (category: string, lang?: string, slug = article.slug) =>
  generateMetadata({
    params: Promise.resolve({ category, slug }),
    searchParams: Promise.resolve(lang ? { lang } : {}),
  });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getArticleBySlug).mockResolvedValue(article);
  vi.mocked(getArticleByLocale).mockResolvedValue(article);
});

describe("article metadata category validation", () => {
  // /blog/<real living slug> reproduced the defect: the parent renders its
  // not-found boundary, while the child's fallback lookup finds a real article
  // and overrides the parent's noindex metadata with index + googlebot.
  for (const lang of [undefined, "fr"]) {
    it.each([
      "blog",
      "not-a-category",
      "constructor",
      "toString",
      "hasOwnProperty",
      "valueOf",
      "__proto__",
    ])(
      `rejects /%s/<existing slug> before lookup (lang=${lang ?? "en"})`,
      async (category) => {
        const result = await metadata(category, lang);
        const parent = await categoryMetadata({
          params: Promise.resolve({ category }),
        });
        expect(result).toEqual({ title: parent.title, robots: parent.robots });
        expect(getArticleBySlug).not.toHaveBeenCalled();
        expect(getArticleByLocale).not.toHaveBeenCalled();
      },
    );
  }

  for (const lang of [undefined, "fr"]) {
    it.each<ArticleCategory>([
      "visas",
      "business",
      "taxes",
      "property",
      "living",
      "trends",
    ])(
      `preserves canonical /%s article metadata (lang=${lang ?? "en"})`,
      async (category) => {
        const current = { ...article, category };
        vi.mocked(getArticleBySlug).mockResolvedValue(current);
        vi.mocked(getArticleByLocale).mockResolvedValue(current);
        expect(await metadata(category, lang)).toEqual(
          generateArticleMetadata(current),
        );
        if (lang) {
          expect(getArticleByLocale).toHaveBeenCalledWith(
            category,
            article.slug,
            lang,
          );
          expect(getArticleBySlug).not.toHaveBeenCalled();
        } else {
          expect(getArticleBySlug).toHaveBeenCalledWith(category, article.slug);
          expect(getArticleByLocale).not.toHaveBeenCalled();
        }
      },
    );

    it.each(
      Object.entries(CATEGORY_MAP).filter(
        ([alias, target]) => alias !== target,
      ),
    )(
      `rejects declared alias /%s -> /%s before lookup (lang=${lang ?? "en"})`,
      async (alias) => {
        const result = await metadata(alias, lang);
        const parent = await categoryMetadata({
          params: Promise.resolve({ category: alias }),
        });
        expect(result).toEqual({
          title: "Page not found",
          robots: { index: false, follow: false },
        });
        expect(result).toEqual({ title: parent.title, robots: parent.robots });
        expect(getArticleBySlug).not.toHaveBeenCalled();
        expect(getArticleByLocale).not.toHaveBeenCalled();
      },
    );
  }

  it.each([undefined, "fr"])(
    "preserves article.noIndex (lang=%s)",
    async (lang) => {
      const archived = { ...article, noIndex: true };
      vi.mocked(getArticleBySlug).mockResolvedValue(archived);
      vi.mocked(getArticleByLocale).mockResolvedValue(archived);
      const result = await metadata("living", lang);
      expect(result).toEqual(generateArticleMetadata(archived));
      expect(result.robots).toEqual({ index: false, follow: false });
      if (lang) {
        expect(getArticleByLocale).toHaveBeenCalledWith(
          "living",
          article.slug,
          lang,
        );
        expect(getArticleBySlug).not.toHaveBeenCalled();
      }
    },
  );

  it("retains notFound for a missing article in a canonical category", async () => {
    vi.mocked(getArticleBySlug).mockResolvedValue(null);
    await expect(metadata("living")).rejects.toThrow(
      "NEXT_HTTP_ERROR_FALLBACK;404",
    );
  });

  it("retains the existing static-file rejection before lookup", async () => {
    expect(await metadata("living", undefined, "cover.jpg")).toEqual({
      title: "Not Found",
    });
    expect(getArticleBySlug).not.toHaveBeenCalled();
    expect(getArticleByLocale).not.toHaveBeenCalled();
  });
});
