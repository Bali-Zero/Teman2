/**
 * Folder → public-category mapping, and the article's one public slug.
 *
 * WHY THIS FILE EXISTS. `articles.ts` owned both facts, module-privately, and
 * `articles.ts` imports `next/cache` — so the build-time AI-export generator
 * (`scripts/generate-llms-full.ts`, a plain node script run by `next build`)
 * could not reach them and re-derived the URL from the raw filename instead:
 *
 *     `https://balizero.com/${folderName}/${file.replace(".mdx","").replace(".id","")}`
 *
 * Both halves of that expression were wrong, and both shipped:
 *
 *  1. **Folder name is not the public category.** 13 content folders collapse
 *     onto 7 served categories. `business_regulations/` is served at
 *     `/business/`, `immigration/` at `/visas/`, `tax-legal/` at `/taxes/`.
 *     Measured on the published artifact 2026-08-11: of ~2,340 URLs only
 *     `business/` (598) and `property/` (118) named a category the site
 *     actually routes; the rest rendered "Article not found".
 *  2. **Only `.id` was stripped.** `foo.it.mdx` became `/…/foo.it`,
 *     `foo.fr.mdx` became `/…/foo.fr`, `foo.ru.mdx` became `/…/foo.ru`. There
 *     is exactly one public page per article — the base slug — so every
 *     translated variant pointed at a URL that does not exist. Only `.id` was
 *     handled because llms-id.txt was the export it was written for.
 *
 * So the two files whose entire job is to hand crawlers a citable URL were
 * handing out mostly dead ones. Keeping the mapping HERE, dependency-free
 * (types only), lets both the Next runtime and the build script read the same
 * table instead of two drifting copies.
 */

import type { ArticleCategory } from "./types";

/**
 * Map folder/frontmatter categories to valid ArticleCategory.
 * Handles legacy naming and folder-structure differences.
 */
export const CATEGORY_MAP: Record<string, ArticleCategory> = {
  // Canonical categories
  visas: "visas",
  business: "business",
  taxes: "taxes",
  property: "property",
  living: "living",
  trends: "trends",
  // Backward compat (old category names)
  immigration: "visas",
  lifestyle: "living",
  tech: "trends",
  bali_news: "living",
  // Folder mappings (14 folders → 7 categories)
  tax: "taxes",
  "tax-legal": "taxes",
  "digital-nomad": "living",
  "bali-news": "living",
  business_regulations: "business",
  emerging_trends: "trends",
  social_media: "trends",
  news: "business",
  // Backend compatibility
  general: "business",
  legal: "taxes",
};

export function normalizeCategory(rawCategory: string): ArticleCategory {
  return CATEGORY_MAP[rawCategory] || "living";
}

/**
 * Locale suffixes that exist as translated `.mdx` variants. None of them has a
 * public page of its own — verified against the live sitemap 2026-08-11, which
 * carries zero `.it`/`.id`/`.fr`/`.ru` URLs and no `/it/`-style prefix.
 */
export const LOCALE_SUFFIXES = Object.freeze(["id", "it", "fr", "ru"] as const);
const LOCALE_SET = new Set<string>(LOCALE_SUFFIXES);

/**
 * The one public slug for an article file, whatever language it is written in.
 *
 *   `foo.mdx` → `foo` · `foo.it.mdx` → `foo` · `foo.id.mdx` → `foo`
 *
 * Only a KNOWN locale is stripped, never any trailing `.xx`: a slug that
 * genuinely ended in a two-letter segment would otherwise be truncated into a
 * different article. (No such slug exists today — all 796 base files are
 * dot-free — but the export must not become the thing that creates one.)
 */
export function publicSlug(fileName: string): string {
  const base = fileName.replace(/\.mdx$/, "");
  const match = base.match(/^(.+)\.([a-z]{2})$/);
  return match && LOCALE_SET.has(match[2]) ? match[1] : base;
}

/** The public URL of an article, from its content folder and file name. */
export function articleUrl(
  folderCategory: string,
  fileName: string,
  baseUrl = "https://balizero.com",
): string {
  return `${baseUrl}/${normalizeCategory(folderCategory)}/${publicSlug(fileName)}`;
}
