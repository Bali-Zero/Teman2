"use client";

import * as React from "react";
import type { Locale } from "./types";
import { DEFAULT_LOCALE, LOCALES } from "./types";
import { LANG_OWNER_ATTR, LANG_OWNER_CONTENT } from "./content-locale";
import en from "./locales/en.json";
import id from "./locales/id.json";
import it from "./locales/it.json";
import ru from "./locales/ru.json";
import fr from "./locales/fr.json";

const messages: Record<Locale, Record<string, unknown>> = {
  en,
  id,
  it,
  ru,
  fr,
};

type TranslationFn = (key: string, params?: Record<string, string>) => string;

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: TranslationFn;
}

const I18nContext = React.createContext<I18nContextValue | null>(null);

function getNestedValue(
  obj: Record<string, unknown>,
  path: string,
): string | undefined {
  const parts = path.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(
  template: string,
  params?: Record<string, string>,
): string {
  if (!params) return template;
  return template.replace(
    /\{\{(\w+)\}\}/g,
    (_, key) => params[key] ?? `{{${key}}}`,
  );
}

/**
 * `<html lang>` has two would-be writers — this provider (UI-chrome locale,
 * from `blog-language`) and a page that knows the language its CONTENT was
 * served in. The attribute describes the content, so the page wins whenever
 * it has claimed ownership; see i18n/content-locale.ts.
 */
function pageOwnsLang(): boolean {
  return (
    document.documentElement.getAttribute(LANG_OWNER_ATTR) ===
    LANG_OWNER_CONTENT
  );
}

export function I18nProvider({
  children,
  initialLocale,
}: {
  children: React.ReactNode;
  /**
   * Pins the provider's locale for a route whose language IS the URL — the
   * localized `/visa/second-home/{it,id}` SSG pages (2026-08-20). State
   * initializes to it directly (no effect needed for the first render, so
   * SSR/SSG output is already in the right language), and the init effect
   * below skips the `?lang=`/saved-preference restore entirely: a visitor's
   * saved "en" preference must never flip a page that is served in Italian
   * back to English. Omitting this prop is byte-identical to prior
   * behavior — pinned by the existing `?lang=`/localStorage tests.
   */
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = React.useState<Locale>(
    initialLocale ?? DEFAULT_LOCALE,
  );

  React.useEffect(() => {
    if (initialLocale) return;

    // `?lang=<locale>` lets a shared link set the UI-chrome language for THIS
    // VISIT only (2026-08-20). Strict whitelist — this is a user-controlled
    // input (searchParams), so it is validated against LOCALES and never
    // written anywhere but React state + `<html lang>` (guarded exactly like
    // the localStorage path below). It takes precedence over a saved
    // preference but is deliberately NOT persisted to localStorage: a link
    // must not overwrite a visitor's explicit saved choice for future visits.
    const urlLang = new URLSearchParams(window.location.search).get("lang");
    if (urlLang && LOCALES.includes(urlLang as Locale)) {
      setLocaleState(urlLang as Locale);
      if (!pageOwnsLang()) document.documentElement.lang = urlLang;
      return;
    }

    const saved = localStorage.getItem("blog-language");
    if (saved && LOCALES.includes(saved as Locale)) {
      setLocaleState(saved as Locale);
      if (!pageOwnsLang()) document.documentElement.lang = saved;
    }
  }, [initialLocale]);

  const setLocale = React.useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem("blog-language", newLocale);
    // The UI locale still changes; `<html lang>` does NOT when a page owns it.
    // Switching the chrome to Italian does not translate an English article
    // body — declaring "it" there would describe a document that is not in it.
    if (!pageOwnsLang()) document.documentElement.lang = newLocale;
  }, []);

  const t: TranslationFn = React.useCallback(
    (key: string, params?: Record<string, string>) => {
      const value =
        getNestedValue(messages[locale], key) ??
        getNestedValue(messages[DEFAULT_LOCALE], key) ??
        key;
      return interpolate(value, params);
    },
    [locale],
  );

  const value = React.useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): I18nContextValue {
  const ctx = React.useContext(I18nContext);
  if (!ctx) throw new Error("useTranslation must be used within I18nProvider");
  return ctx;
}
