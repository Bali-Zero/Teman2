"use client";
import { createContext, useContext, type ReactNode } from "react";
import en from "./messages/en.json";
import it from "./messages/it.json";
import id from "./messages/id.json";
export type Locale = "en" | "it" | "id";
export const OFFERED_LOCALES: Locale[] = ["en", "it", "id"];
const LocaleContext = createContext<Locale>("en");
const dictionaries = { en, it, id };
export function SecondHomeLanguage({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  return (
    <LocaleContext.Provider value={locale}>
      <div lang={locale}>{children}</div>
    </LocaleContext.Provider>
  );
}
export function useTranslation() {
  const locale = useContext(LocaleContext);
  return {
    locale,
    setLocale: (_locale: Locale) => {},
    t: (key: string, params?: Record<string, string | number>): string => {
      const lookup = (dictionary: unknown): unknown =>
        key
          .split(".")
          .reduce<unknown>(
            (value, segment) =>
              value && typeof value === "object"
                ? (value as Record<string, unknown>)[segment]
                : undefined,
            dictionary,
          );
      const value = lookup(dictionaries[locale]) ?? lookup(en);
      if (typeof value !== "string") return key;
      return value.replace(/\{\{?(\w+)\}?\}/g, (match, name: string) =>
        params?.[name] === undefined ? match : String(params[name]),
      );
    },
  };
}
