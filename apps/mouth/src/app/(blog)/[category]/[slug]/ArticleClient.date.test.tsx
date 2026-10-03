import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/dynamic", () => ({
  default: () => () => null,
}));
vi.mock("@/components/blog", () => ({
  CategoryBadge: () => null,
  TableOfContents: () => null,
  FloatingToc: () => null,
  ReadingProgress: () => null,
  ArticleCard: () => null,
  NewsletterSidebar: () => null,
  ArticleEngagement: () => null,
}));
vi.mock("@/components/blog/MDXContent", () => ({ MDXContent: () => null }));
vi.mock("@/components/lead/WhatsAppLeadButton", () => ({
  WhatsAppLeadButton: () => null,
}));
vi.mock("@/lib/api", () => ({ api: { blog: { getArticle: vi.fn() } } }));

import {
  ArticleClient,
  type SerializedArticleForClient,
} from "./ArticleClient";

function article(publishedAt: string | null): SerializedArticleForClient {
  return {
    id: "a1",
    slug: "bali-business-networking",
    title: "Bali business networking",
    excerpt: "excerpt",
    content: "body",
    coverImage: "/cover.jpg",
    coverImageAlt: "cover",
    category: "business",
    tags: [],
    author: { id: "au1", name: "Bali Zero Team", role: "Editorial" },
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    publishedAt,
    status: "published",
    featured: false,
    trending: false,
    readingTime: 4,
    viewCount: 12,
    shareCount: 0,
    likeCount: 0,
    commentCount: 0,
    aiGenerated: false,
    relatedArticleIds: [],
    locale: "en",
  } as unknown as SerializedArticleForClient;
}

// Regression: QA on a physical iQOO (Asia/Makassar) hit React #418 on article
// pages because the date came out "Jan 3, 2026" in the server HTML (UTC) and
// "Jan 4, 2026" in the browser. The byline must be the WITA day on both sides.
// Prove it under a UTC process: `TZ=UTC npx vitest run <this file>`.
describe("ArticleClient byline date", () => {
  it("prints the WITA calendar day for a late-evening UTC publishedAt", () => {
    const html = renderToString(
      <ArticleClient
        category="business"
        slug="bali-business-networking"
        initialArticle={article("2026-01-03T20:00:00Z")}
      />,
    );
    expect(html).toContain("Jan 4, 2026");
    expect(html).not.toContain("Jan 3, 2026");
  });

  it("falls back to createdAt in the same zone when publishedAt is null", () => {
    const a = article(null);
    a.createdAt = "2026-01-03T20:00:00Z";
    const html = renderToString(
      <ArticleClient
        category="business"
        slug="bali-business-networking"
        initialArticle={a}
      />,
    );
    expect(html).toContain("Jan 4, 2026");
  });
});
