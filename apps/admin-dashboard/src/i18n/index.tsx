"use client";

import * as React from "react";
import type { Locale } from "./types";
import { DEFAULT_LOCALE, LOCALES } from "./types";
import en from "./locales/en.json";
import it from "./locales/it.json";

const messages: Record<Locale, Record<string, unknown>> = {
  en,
  it,
};

type TranslationFn = (key: string, params?: Record<string, string>) => string;
type TranslationArrayFn = (key: string) => string[];

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: TranslationFn;
  tArray: TranslationArrayFn;
}

const I18nContext = React.createContext<I18nContextValue | null>(null);

function getNestedValue(
  obj: Record<string, unknown>,
  path: string,
): unknown {
  const parts = path.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function getStringValue(
  obj: Record<string, unknown>,
  path: string,
): string | undefined {
  const value = getNestedValue(obj, path);
  return typeof value === "string" ? value : undefined;
}

function getArrayValue(
  obj: Record<string, unknown>,
  path: string,
): string[] | undefined {
  const value = getNestedValue(obj, path);
  if (Array.isArray(value) && value.every((v) => typeof v === "string")) {
    return value as string[];
  }
  return undefined;
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

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = React.useState<Locale>(DEFAULT_LOCALE);

  React.useEffect(() => {
    const saved = localStorage.getItem("admin-language");
    if (saved && LOCALES.includes(saved as Locale)) {
      setLocaleState(saved as Locale);
      document.documentElement.lang = saved;
    }
  }, []);

  const setLocale = React.useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem("admin-language", newLocale);
    document.documentElement.lang = newLocale;
  }, []);

  const t: TranslationFn = React.useCallback(
    (key: string, params?: Record<string, string>) => {
      const value =
        getStringValue(messages[locale], key) ??
        getStringValue(messages[DEFAULT_LOCALE], key) ??
        key;
      return interpolate(value, params);
    },
    [locale],
  );

  const tArray: TranslationArrayFn = React.useCallback(
    (key: string) => {
      return (
        getArrayValue(messages[locale], key) ??
        getArrayValue(messages[DEFAULT_LOCALE], key) ??
        []
      );
    },
    [locale],
  );

  const value = React.useMemo(
    () => ({ locale, setLocale, t, tArray }),
    [locale, setLocale, t, tArray],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): I18nContextValue {
  const ctx = React.useContext(I18nContext);
  if (!ctx) throw new Error("useTranslation must be used within I18nProvider");
  return ctx;
}
