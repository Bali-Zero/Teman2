import type {
  JournalArticle,
  JournalArticleDocument,
} from "../../content/journal";
import {
  isJournalCategory,
  journalCategories,
} from "../../content/journal-categories";
import type { EditorialFeed } from "../editorial-feed";
import { cache } from "react";
import { isArticleSlug } from "../article-slug";
import { retainedImage } from "../retained-assets";
import { readAuthoredEnglishArticle } from "./article-archive";
import {
  EditorialHttpError,
  readEditorialJson as readJson,
  loadPublicCatalog,
  selectCatalog,
} from "./public-catalog";

// Read-only compatibility adapter to the currently published Bali Zero catalog.
// Magazine publication/withdrawal contracts remain separate and are not armed here.
const origin = "https://balizero.com";
// These are the legacy API's hardcoded demo fallbacks, not published records.
const demoSlugs = new Set([
  "golden-visa-revolution",
  "oss-2-complete-guide",
  "tax-deadlines-2026",
  "test-article",
]);
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown, max: number): value is string =>
  typeof value === "string" && value.trim().length > 0 && value.length <= max;

export type JournalQuery = Readonly<{
  category?: string;
  q?: string;
  page?: number;
  limit?: number;
}>;
export type JournalFeed = EditorialFeed &
  Readonly<{
    total?: number;
    hasMore?: boolean;
    page?: number;
    catalogSize?: number;
    featuredCount?: number;
  }>;
export type PublicArticleResult =
  | Readonly<{ status: "ready"; article: JournalArticleDocument }>
  | Readonly<{ status: "missing" | "unavailable" }>;

export function decodePublicArticle(
  value: unknown,
  category: string,
  slug: string,
  now = Date.now(),
): JournalArticleDocument | null {
  if (
    !isJournalCategory(category) ||
    !isArticleSlug(slug) ||
    demoSlugs.has(slug) ||
    !isRecord(value)
  )
    return null;
  if (
    value.category !== category ||
    value.slug !== slug ||
    value.status !== "published" ||
    (value.noIndex !== undefined && value.noIndex !== false) ||
    !text(value.title, 500) ||
    !text(value.content, 200_000) ||
    !text(value.publishedAt, 40)
  )
    return null;
  const published = new Date(value.publishedAt);
  if (
    !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z)?$/.test(
      value.publishedAt,
    ) ||
    !Number.isFinite(published.getTime()) ||
    published.toISOString().slice(0, 10) !== value.publishedAt.slice(0, 10) ||
    published.getTime() > now
  )
    return null;
  const image = retainedImage(value.coverImage);
  const metadata: JournalArticle = {
    slug,
    title: value.title,
    category: journalCategories.find((item) => item.slug === category)!.label,
    sourceUrl: `${origin}/${category}/${slug}`,
    finalSourceUrl: null,
    localHref: `/${category}/${slug}`,
    verificationStatus: "pending",
    image: image
      ? {
          ...image,
          alt: text(value.coverImageAlt, 500)
            ? value.coverImageAlt
            : value.title,
        }
      : null,
    date: {
      iso: published.toISOString(),
      label: new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      }).format(published),
    },
    summary: text(value.excerpt, 4000) ? value.excerpt : undefined,
    featured: value.featured === true,
    reading: {
      ...(isRecord(value.author) && text(value.author.name, 200)
        ? {
            author: {
              name: value.author.name,
              ...(text(value.author.role, 200)
                ? { role: value.author.role }
                : {}),
            },
          }
        : {}),
      ...(text(value.reviewedBy, 200) ? { reviewedBy: value.reviewedBy } : {}),
      ...(typeof value.readingTime === "number" &&
      Number.isSafeInteger(value.readingTime) &&
      value.readingTime > 0 &&
      value.readingTime <= 300
        ? { minutes: value.readingTime }
        : {}),
      ...(typeof value.aiGenerated === "boolean"
        ? { aiGenerated: value.aiGenerated }
        : {}),
      ...(text(value.aiDisclaimer, 2000)
        ? { disclosure: value.aiDisclaimer }
        : {}),
      ...(text(value.updatedAt, 40) &&
      /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z)?$/.test(
        value.updatedAt,
      ) &&
      Number.isFinite(Date.parse(value.updatedAt)) &&
      Date.parse(value.updatedAt) <= now &&
      Date.parse(value.updatedAt) >= published.getTime() &&
      new Date(value.updatedAt).toISOString().slice(0, 10) ===
        value.updatedAt.slice(0, 10)
        ? {
            updated: {
              iso: new Date(value.updatedAt).toISOString(),
              label: new Intl.DateTimeFormat("en-GB", {
                day: "numeric",
                month: "long",
                year: "numeric",
                timeZone: "UTC",
              }).format(new Date(value.updatedAt)),
            },
          }
        : {}),
    },
  };
  return {
    metadata,
    standfirst: metadata.summary ?? "",
    markdown: value.content,
    sections: [],
    indexing: "excluded",
  };
}

export const loadPublicArticleResult = cache(
  async (category: string, slug: string): Promise<PublicArticleResult> => {
    if (
      !isJournalCategory(category) ||
      !isArticleSlug(slug) ||
      demoSlugs.has(slug)
    )
      return { status: "missing" };
    const local = await readAuthoredEnglishArticle(category, slug);
    if (local.status === "rejected") return { status: "missing" };
    if (local.status === "ready") {
      const article = decodePublicArticle(local.article.value, category, slug);
      return article ? { status: "ready", article } : { status: "missing" };
    }
    try {
      const article = decodePublicArticle(
        await readJson(`/api/blog/articles/${category}/${slug}`, true),
        category,
        slug,
      );
      return article ? { status: "ready", article } : { status: "missing" };
    } catch (error) {
      return {
        status:
          error instanceof EditorialHttpError &&
          (error.status === 404 || error.status === 410)
            ? "missing"
            : "unavailable",
      };
    }
  },
);

export async function loadPublicArticle(
  category: string,
  slug: string,
): Promise<JournalArticleDocument | null> {
  const result = await loadPublicArticleResult(category, slug);
  return result.status === "ready" ? result.article : null;
}

export async function loadPublicJournalFeed(
  query: JournalQuery = {},
): Promise<JournalFeed> {
  const limit = Number.isFinite(query.limit)
    ? Math.min(12, Math.max(1, Math.floor(query.limit!)))
    : 6;
  const page = Number.isFinite(query.page)
    ? Math.max(1, Math.min(1000, Math.floor(query.page!)))
    : 1;
  try {
    const catalog = await loadPublicCatalog();
    const rows = selectCatalog(catalog, {
      category: query.category,
      q: query.q?.trim().slice(0, 120),
    });
    const accepted: JournalArticle[] = [];
    let scanned = 0,
      rejected = 0;
    // Count only confirmed published records for pagination. Read one extra to
    // prove Next exists, refilling holes left by withdrawals/invalid records.
    while (scanned < rows.length && accepted.length <= page * limit) {
      const batch = rows.slice(scanned, scanned + 4);
      const results = await Promise.all(
        batch.map((row) => loadPublicArticleResult(row.category, row.slug)),
      );
      for (const result of results) {
        if (result.status === "unavailable")
          throw new Error("Publication authority unavailable");
        if (result.status === "ready") accepted.push(result.article.metadata);
        else rejected++;
      }
      scanned += batch.length;
    }
    const articles = accepted.slice((page - 1) * limit, page * limit);
    return {
      status: articles.length ? "ready" : "empty",
      articles,
      rejected,
      provenance: "publisher",
      page,
      hasMore: accepted.length > page * limit,
      catalogSize: catalog.length,
      ...(scanned === rows.length ? { total: accepted.length } : {}),
    };
  } catch {
    return { status: "unavailable", articles: [], rejected: 0, page };
  }
}
