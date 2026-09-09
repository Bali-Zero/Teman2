import { readFile, realpath, stat } from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { cache } from "react";
import type { JournalArticleDocument } from "../../content/journal";
import { isJournalCategory } from "../../content/journal-categories";
import { isArticleSlug } from "../article-slug";
import { decodePublicArticle } from "./public-editorial";

export const articleLocales = { en: "English", id: "Bahasa Indonesia", it: "Italiano", fr: "Français", ru: "Русский" } as const;
export type ArticleLocale = keyof typeof articleLocales;
export function isArticleLocale(value: unknown): value is ArticleLocale {
  return typeof value === "string" && Object.hasOwn(articleLocales, value);
}

// Exact reading order from Mouth's getArticleByLocale. Originals stay in the
// publisher's content tree and are included in the server output trace.
export const articleFolders: Record<string, readonly string[]> = {
  visas: ["immigration"], business: ["business", "business_regulations", "news"],
  taxes: ["tax-legal", "tax"], property: ["property"],
  living: ["lifestyle", "digital-nomad", "bali_news"], trends: ["emerging_trends", "tech", "social_media"],
};
const categoryAliases: Record<string, string> = { immigration: "visas", business_regulations: "business", news: "business", "tax-legal": "taxes", tax: "taxes", lifestyle: "living", "digital-nomad": "living", bali_news: "living", emerging_trends: "trends", tech: "trends", social_media: "trends" };
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const iso = (value: unknown): unknown => value instanceof Date ? value.toISOString() : value;

/** Caller must first verify the base record against the live publishing owner.
 * Only authored YAML + inert MDX is read; no translation generation or execution. */
export function decodeAuthoredTranslation(source: string, category: string, slug: string, locale: ArticleLocale, now = Date.now()): JournalArticleDocument | null {
  if (locale === "en" || !isArticleLocale(locale) || !isJournalCategory(category) || !isArticleSlug(slug) || source.length > 250_000 || !/^---\r?\n/.test(source)) return null;
  try {
    const { data, content } = matter(source);
    if (!record(data) || data.slug !== slug || data.locale !== locale || (categoryAliases[String(data.category)] ?? data.category) !== category) return null;
    const image = record(data.image) ? data.image : {};
    const decoded = decodePublicArticle({
      ...data, category, content, status: data.status ?? "published",
      publishedAt: iso(data.publishedAt), updatedAt: iso(data.updatedAt),
      coverImage: data.coverImage ?? image.src, coverImageAlt: data.coverImageAlt ?? image.alt,
    }, category, slug, now);
    if (!decoded) return null;
    const suffix = `?lang=${locale}`;
    return { ...decoded, metadata: { ...decoded.metadata, sourceUrl: decoded.metadata.sourceUrl + suffix, localHref: decoded.metadata.localHref + suffix } };
  } catch { return null; }
}

export const loadAuthoredTranslations = cache(async (category: string, slug: string): Promise<Partial<Record<ArticleLocale, JournalArticleDocument>>> => {
  if (!isJournalCategory(category) || !isArticleSlug(slug)) return {};
  const root = path.resolve(process.cwd(), "../mouth/src/content/articles");
  let canonicalRoot: string;
  try { canonicalRoot = await realpath(root); } catch { return {}; }
  const entries = await Promise.all((Object.keys(articleLocales) as ArticleLocale[]).filter((locale) => locale !== "en").map(async (locale) => {
    for (const folder of articleFolders[category]) {
      try {
        const file = await realpath(path.join(root, folder, `${slug}.${locale}.mdx`));
        if (!file.startsWith(canonicalRoot + path.sep)) continue;
        const info = await stat(file);
        if (!info.isFile() || info.size > 250_000) continue;
        const article = decodeAuthoredTranslation(await readFile(file, "utf8"), category, slug, locale);
        if (article) return [locale, article] as const;
      } catch { /* Absent or invalid editions never masquerade as translations. */ }
    }
    return null;
  }));
  return Object.fromEntries(entries.filter((entry) => entry !== null));
});
