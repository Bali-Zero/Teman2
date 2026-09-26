import { CATEGORY_METADATA, type ArticleListItem } from "@/lib/blog/types";
import type { JournalArticle } from "./types";

const slots = [
  "hero_main",
  "hero_2",
  "hero_3",
  "hero_4",
  "hero_5",
  "latest_1",
  "latest_2",
  "latest_3",
  "latest_4",
  "latest_5",
];

/** Keep the existing editorial preferences, then fill absent slots from the live reader. */
export function selectJournalArticles(
  articles: readonly ArticleListItem[],
  layout: Record<string, string>,
  limit = 7,
): JournalArticle[] {
  const bySlug = new Map(articles.map((article) => [article.slug, article]));
  const seen = new Set<string>();
  const ordered = [
    ...slots.map((slot) => bySlug.get(layout[slot])),
    ...articles,
  ];
  return ordered
    .filter((article): article is ArticleListItem => {
      if (
        !article ||
        !Object.prototype.hasOwnProperty.call(
          CATEGORY_METADATA,
          article.category,
        ) ||
        seen.has(article.slug)
      )
        return false;
      seen.add(article.slug);
      return true;
    })
    .slice(0, limit)
    .map((article) => {
      const date = new Date(article.publishedAt);
      const href = "/" + article.category + "/" + article.slug;
      return {
        slug: article.slug,
        title: article.title,
        image: article.coverImage
          ? { src: article.coverImage, alt: article.title }
          : null,
        category: CATEGORY_METADATA[article.category].label,
        date: Number.isNaN(date.getTime())
          ? null
          : {
              iso: date.toISOString(),
              label: new Intl.DateTimeFormat("en-GB", {
                day: "numeric",
                month: "long",
                year: "numeric",
                timeZone: "Asia/Makassar",
              }).format(date),
            },
        sourceUrl: href,
        finalSourceUrl: null,
        localHref: href,
        destinationStatus: "available",
      };
    });
}
