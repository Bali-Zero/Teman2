import { DEFAULT_LOCALE, LOCALES, type Locale } from "./types";

/**
 * Who owns `document.documentElement.lang`.
 *
 * The attribute describes the language of the document's MAIN CONTENT. On an
 * article route that content is the MDX body, and the SERVER picks it: it
 * honours `?lang=xx` only when a `{slug}.{locale}.mdx` exists and otherwise
 * falls back to English (`getArticleByLocale`, articles.ts). The I18nProvider
 * knows something different — the UI-chrome locale, restored from the
 * `blog-language` preference — and the two disagree routinely: a reader who
 * picked "it" from the switcher gets Italian chrome around an English article.
 *
 * Before this marker both wrote the same field with no rule, so whichever ran
 * last won and the document could claim a language its body was not in. The
 * rule: when a page KNOWS its content language, it says so by taking
 * ownership, and the provider yields.
 */
export const LANG_OWNER_ATTR = "data-lang-owner";
export const LANG_OWNER_CONTENT = "content";

/**
 * The locale the server actually SERVED, which is not the locale that was
 * asked for: an unknown code, or a known one with no translation on disk,
 * both come back as English. Mirrors `getArticleByLocale`'s fallback — pass
 * it the same `getAvailableLocales(category, slug)` list the resolver walks.
 */
export function resolveContentLocale(
  requested: string | undefined | null,
  available: readonly string[],
): Locale {
  if (!requested) return DEFAULT_LOCALE;
  if (!(LOCALES as readonly string[]).includes(requested))
    return DEFAULT_LOCALE;
  if (!available.includes(requested)) return DEFAULT_LOCALE;
  return requested as Locale;
}

/*
 * DELIBERATELY NOT HERE: a pre-paint inline script that would stamp the
 * language into the very first parse of the document. It was written, then
 * dropped — it needs `dangerouslySetInnerHTML` on a string whose input traces
 * back to `searchParams.lang`, and its behaviour inside an RSC page (React 19
 * hoists some <script> tags) was never verified empirically. The correctness
 * fix does not depend on it: ContentLangSync already makes the right value
 * win. What the script would have bought is only EARLINESS — parse-time
 * instead of hydration-time — which is not worth an unverified construct on a
 * security-sensitive surface.
 *
 * The residual it would NOT have fixed either way: the server-rendered HTML
 * still carries the root layout's `lang="en"` attribute, because `<html>`
 * lives in the root layout and reading the request there (`headers()`) would
 * opt the ENTIRE site out of static rendering. A crawler that does not run JS
 * still sees `en`. The real cure is path-based locale routing (`/fr/...`),
 * which also fixes hreflang and the sitemap — tracked in PENDING-ARMS.
 */
