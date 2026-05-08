import { beforeEach, describe, expect, it, vi } from "vitest";

import sitemap from "./sitemap";
import { getAllArticles, getAvailableLocales, getNoIndexSlugs } from "@/lib/blog/articles";
import type { ArticleListItem } from "@/lib/blog/types";
import { getAllCodes, getSections } from "@/lib/kbli-data.server";
import { logger } from "@/lib/logger";

vi.mock("@/lib/blog/articles", () => ({
  getAllArticles: vi.fn(),
  getAvailableLocales: vi.fn(),
  getNoIndexSlugs: vi.fn(),
}));

vi.mock("@/lib/kbli-data.server", () => ({
  getAllCodes: vi.fn(),
  getSections: vi.fn(),
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
  },
}));

const mockedGetAllArticles = vi.mocked(getAllArticles);
const mockedGetNoIndexSlugs = vi.mocked(getNoIndexSlugs);
const mockedGetAvailableLocales = vi.mocked(getAvailableLocales);
const mockedGetAllCodes = vi.mocked(getAllCodes);
const mockedGetSections = vi.mocked(getSections);
const mockedLogger = vi.mocked(logger);

function article(overrides: Partial<ArticleListItem>): ArticleListItem {
  return {
    id: overrides.slug ?? "article",
    slug: "article",
    title: "Article",
    excerpt: "Article excerpt",
    coverImage: "/cover.jpg",
    category: "business",
    author: {
      id: "zantara",
      name: "Zantara",
      avatar: "/avatar.jpg",
      role: "AI",
      isAI: true,
    },
    publishedAt: new Date("2026-01-01"),
    readingTime: 4,
    viewCount: 0,
    featured: false,
    trending: false,
    aiGenerated: false,
    ...overrides,
  };
}

describe("sitemap metadata route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetAllArticles.mockResolvedValue({
      articles: [
        article({
          slug: "investor-kitas-guide",
          category: "visas",
          publishedAt: new Date("2026-01-15"),
          featured: true,
          aiGenerated: false,
        }),
        article({
          slug: "draft-hidden-article",
          category: "business",
          publishedAt: new Date("2026-02-01"),
          featured: false,
          aiGenerated: true,
        }),
      ],
      total: 2,
    });
    mockedGetNoIndexSlugs.mockResolvedValue(new Set(["draft-hidden-article"]));
    mockedGetAvailableLocales.mockReturnValue(["en", "id"]);
    mockedGetAllCodes.mockReturnValue([
      { code: "62019" },
      { code: "68111" },
    ] as ReturnType<typeof getAllCodes>);
    mockedGetSections.mockReturnValue([
      { id: "g", codeCount: 12 },
      { id: "z", codeCount: 0 },
    ] as ReturnType<typeof getSections>);
  });

  it("builds static, article, KBLI code, visa, and sector URLs", async () => {
    const routes = await sitemap();
    const urls = routes.map((route) => route.url);

    expect(urls).toEqual(
      expect.arrayContaining([
        "https://balizero.com",
        "https://balizero.com/services/visa",
        "https://balizero.com/visas",
        "https://balizero.com/visas/investor-kitas-guide",
        "https://balizero.com/kbli/62019",
        "https://balizero.com/kbli/68111",
        "https://balizero.com/visa/match",
        "https://balizero.com/kbli/sectors",
        "https://balizero.com/kbli/sectors/g",
      ]),
    );
    expect(urls).not.toContain("https://balizero.com/business/draft-hidden-article");
    expect(urls).not.toContain("https://balizero.com/kbli/sectors/z");

    const articleRoute = routes.find(
      (route) => route.url === "https://balizero.com/visas/investor-kitas-guide",
    );
    expect(articleRoute).toMatchObject({
      changeFrequency: "weekly",
      priority: 0.9,
      alternates: {
        languages: {
          en: "https://balizero.com/visas/investor-kitas-guide",
          id: "https://balizero.com/visas/investor-kitas-guide?lang=id",
        },
      },
    });
  });

  it("keeps deterministic static routes when optional content loaders fail", async () => {
    mockedGetAllArticles.mockRejectedValue(new Error("articles unavailable"));
    mockedGetAllCodes.mockImplementation(() => {
      throw new Error("kbli unavailable");
    });
    mockedGetSections.mockImplementation(() => {
      throw new Error("sections unavailable");
    });

    const routes = await sitemap();
    const urls = routes.map((route) => route.url);

    expect(urls).toEqual(
      expect.arrayContaining([
        "https://balizero.com",
        "https://balizero.com/services/company",
        "https://balizero.com/visa/privacy",
        "https://balizero.com/kbli/sectors",
      ]),
    );
    expect(mockedLogger.error).toHaveBeenCalledTimes(3);
    expect(mockedLogger.error).toHaveBeenCalledWith(
      "[SITEMAP] Failed to load articles",
      {},
      expect.any(Error),
    );
    expect(mockedLogger.error).toHaveBeenCalledWith(
      "[SITEMAP] Failed to load KBLI codes",
      {},
      expect.any(Error),
    );
    expect(mockedLogger.error).toHaveBeenCalledWith(
      "[SITEMAP] Failed to load KBLI sectors",
      {},
      expect.any(Error),
    );
  });
});
