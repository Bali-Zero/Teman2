import { useState, useLayoutEffect } from "react";

/**
 * Shared hook to detect the current locale for the chat micro-frontend.
 * Reads from localStorage "blog-language" with "en" as default.
 */
export function useChatLocale(override?: string) {
  const [locale, setLocale] = useState(override || "en");

  useLayoutEffect(() => {
    if (override) setLocale(override);
    else setLocale(localStorage.getItem("blog-language") || "en");
  }, [override]);

  return locale;
}
