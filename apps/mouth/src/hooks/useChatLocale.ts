"use client";

import { useEffect, useState } from "react";
import { DEFAULT_LOCALE, LOCALES, type Locale } from "@/i18n/types";

/**
 * Read the persisted locale without depending on `<I18nProvider>`, since the
 * `/chat` route is not currently wrapped in it. Falls back to DEFAULT_LOCALE
 * during SSR.
 */
export function useChatLocale(override?: Locale): Locale {
  const [locale, setLocale] = useState<Locale>(override ?? DEFAULT_LOCALE);

  useEffect(() => {
    if (override) return;
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem("blog-language");
      if (saved && (LOCALES as readonly string[]).includes(saved)) {
        setLocale(saved as Locale);
      }
    } catch {
      /* ignore storage errors */
    }
  }, [override]);

  return locale;
}
