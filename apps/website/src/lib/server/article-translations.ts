import { cache } from "react";
import type { JournalArticleDocument } from "../../content/journal";
import { isJournalCategory } from "../../content/journal-categories";
import { isArticleSlug } from "../article-slug";
import {
  articleFolders,
  decodeAuthoredArticleSource,
  readArticleArchiveFile,
} from "./article-archive";
import { decodePublicArticle } from "./public-editorial";

export { articleFolders } from "./article-archive";

export const articleLocales = {
  en: "English",
  id: "Bahasa Indonesia",
  it: "Italiano",
  fr: "Français",
  ru: "Русский",
} as const;
export type ArticleLocale = keyof typeof articleLocales;
export function isArticleLocale(value: unknown): value is ArticleLocale {
  return typeof value === "string" && Object.hasOwn(articleLocales, value);
}

/** Caller must first verify the base record against the live publishing owner.
 * Only authored YAML + inert MDX is read; no translation generation or execution. */
export function decodeAuthoredTranslation(
  source: string,
  category: string,
  slug: string,
  locale: ArticleLocale,
  now = Date.now(),
): JournalArticleDocument | null {
  if (
    locale === "en" ||
    !isArticleLocale(locale) ||
    !isJournalCategory(category) ||
    !isArticleSlug(slug)
  )
    return null;
  try {
    const authored = decodeAuthoredArticleSource(source, category, slug);
    if (
      !authored ||
      authored.frontmatter.slug !== slug ||
      authored.frontmatter.category === undefined ||
      authored.frontmatter.locale !== locale
    )
      return null;
    const decoded = decodePublicArticle(authored.value, category, slug, now);
    if (!decoded) return null;
    const suffix = `?lang=${locale}`;
    return {
      ...decoded,
      metadata: {
        ...decoded.metadata,
        sourceUrl: decoded.metadata.sourceUrl + suffix,
        localHref: decoded.metadata.localHref + suffix,
      },
    };
  } catch {
    return null;
  }
}

export const loadAuthoredTranslations = cache(
  async (
    category: string,
    slug: string,
  ): Promise<Partial<Record<ArticleLocale, JournalArticleDocument>>> => {
    if (!isJournalCategory(category) || !isArticleSlug(slug)) return {};
    const entries = await Promise.all(
      (Object.keys(articleLocales) as ArticleLocale[])
        .filter((locale) => locale !== "en")
        .map(async (locale) => {
          for (const folder of articleFolders[category]) {
            const file = await readArticleArchiveFile(
              folder,
              `${slug}.${locale}.mdx`,
            );
            if (file.status !== "ready") continue;
            const article = decodeAuthoredTranslation(
              file.source,
              category,
              slug,
              locale,
            );
            if (article) return [locale, article] as const;
          }
          return null;
        }),
    );
    return Object.fromEntries(entries.filter((entry) => entry !== null));
  },
);
