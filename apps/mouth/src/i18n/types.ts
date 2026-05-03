export type Locale = "en" | "id" | "it" | "ru" | "fr";
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALES: Locale[] = ["en", "id", "it", "ru", "fr"];
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  id: "Bahasa Indonesia",
  it: "Italiano",
  ru: "Русский",
  fr: "Français",
};
