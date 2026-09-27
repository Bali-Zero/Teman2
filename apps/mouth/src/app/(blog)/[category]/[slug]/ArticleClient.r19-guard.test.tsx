// R19 skin guard: fails if the article chrome (hero, meta, cover fallback,
// tags, author card, WhatsApp CTA, loading skeleton) still paints pre-R19
// literal colours instead of the R19 tokens. Deliberately out of scope:
// the deep MDX/prose renderer (MDXContent.tsx, MDXContentRSC.tsx, and the
// ReactMarkdown fallback inside this file) — mocked to `null` below, and
// CategoryBadge (owned by the category lane, PR #7568) — also mocked.
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

const FORBIDDEN: RegExp[] = [
  /\btext-white\b/,
  /\bbg-white\//,
  /\bborder-white\//,
  /rgba\(255,\s*255,\s*255/,
  /\bfont-black\b/,
  /\bfont-extrabold\b/,
  /bg-gradient-to-\w+\s+from-\[#/,
  /\b(?:sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-(?:400|500|600)\b/,
  /\b(?:bg|text|border|from|via|to|ring)-\[(?:#|rgba?\()/,
];

function assertNoForbiddenClasses(html: string) {
  for (const re of FORBIDDEN) {
    expect(html).not.toMatch(re);
  }
}

function article(
  overrides: Partial<SerializedArticleForClient> = {},
): SerializedArticleForClient {
  return {
    id: "a1",
    slug: "pt-pma-guide",
    title: "PT PMA guide",
    excerpt: "excerpt",
    content: "body",
    coverImage: "",
    coverImageAlt: "cover alt",
    category: "business",
    tags: ["pt-pma", "kbli"],
    author: {
      id: "au1",
      name: "Bali Zero Team",
      role: "Editorial",
      bio: "bio",
    },
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    publishedAt: "2026-01-01T00:00:00Z",
    status: "published",
    featured: false,
    trending: false,
    readingTime: 4,
    viewCount: 12,
    shareCount: 0,
    likeCount: 0,
    commentCount: 0,
    aiGenerated: true,
    reviewedBy: "Zero",
    relatedArticleIds: [],
    locale: "en",
    ...overrides,
  } as unknown as SerializedArticleForClient;
}

describe("ArticleClient R19 skin guard", () => {
  it("the loaded article chrome has no pre-R19 literal colour classes", () => {
    const html = renderToString(
      <ArticleClient
        category="business"
        slug="pt-pma-guide"
        initialArticle={article()}
      />,
    );
    assertNoForbiddenClasses(html);
  });

  it("the loading skeleton has no pre-R19 literal colour classes", () => {
    const html = renderToString(
      <ArticleClient category="business" slug="pt-pma-guide" />,
    );
    assertNoForbiddenClasses(html);
  });
});
