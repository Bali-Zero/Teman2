import type { ArticleCategory } from "./types";

/**
 * Canonical on-site URL of an article: `/<category>/<slug>`.
 *
 * This is the shape the router, the sitemap, the RSS feed and the JSON-LD all
 * use. `/news/<category>/<slug>` is NOT a route — it 404s on production — so
 * never build article hrefs by hand under `/news/`.
 */
export function articleHref(article: {
  category: ArticleCategory | string;
  slug: string;
}): string {
  return `/${article.category}/${article.slug}`;
}
