export type Locale = "en" | "id" | "it" | "ru" | "fr";
export const DEFAULT_LOCALE: Locale = "en";

/**
 * SUPPORTED — every locale the site can still SERVE. This is the validation
 * set: a saved `blog-language` preference or a `?lang=xx` URL is honored iff
 * it appears here. It must stay a superset of every locale that has content
 * on disk (`{slug}.{locale}.mdx`) or a message bundle in `./locales`.
 *
 * Never shrink this list to hide a language from the picker — dropping a
 * locale here strands the existing translations and 404s links already in
 * the wild. Shrink OFFERED_LOCALES instead.
 */
export const LOCALES: Locale[] = ["en", "id", "it", "ru", "fr"];

/**
 * OFFERED — the subset a language picker may present. Strictly a display
 * decision, and the only list to touch when adding/removing a language from
 * the UI; every consumer that shows a switcher reads THIS, never LOCALES.
 *
 * `ru`/`fr` are supported but not offered (2026-07-29, owner decision): they
 * drifted against the English source between translator runs, so we stopped
 * advertising them while keeping every existing `?lang=ru` / `?lang=fr` URL
 * and saved preference working. Putting them back is this one array — and it
 * is an OWNER decision, not a consequence of the drift closing.
 *
 * "Complete" is no longer a claim made here on faith: as of 2026-09-03 the
 * key-set gap against `en.json` is EMPTY for all four non-English locales and
 * `locale-key-parity.test.ts` fails in both directions (a new gap, and a
 * closed gap left pinned). This comment previously called the fr/ru
 * translations complete while the whole `portal` section — 12 leaf keys —
 * was absent from both files.
 */
export const OFFERED_LOCALES: Locale[] = ["en", "id", "it"];

/**
 * Names and flags are properties of a SUPPORTED locale, not of an offered
 * one — a visitor whose saved preference is `fr` must still see "Français"
 * in the switcher badge instead of a silent fallback to English.
 */
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  id: "Bahasa Indonesia",
  it: "Italiano",
  ru: "Русский",
  fr: "Français",
};

export const LOCALE_FLAGS: Record<Locale, string> = {
  en: "\u{1F1EC}\u{1F1E7}",
  id: "\u{1F1EE}\u{1F1E9}",
  it: "\u{1F1EE}\u{1F1F9}",
  ru: "\u{1F1F7}\u{1F1FA}",
  fr: "\u{1F1EB}\u{1F1F7}",
};
