"use client";

import { useEffect, useRef } from "react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

export interface LanguageToggleProps {
  language: Language;
  onChange: (language: Language) => void;
}

/**
 * EN/ID, co-first-class (design doc §3). Answers are stored as keys, so a
 * mid-funnel switch is instant with no lost history — `flow.ts`'s
 * SET_LANGUAGE action never touches facts.
 */
export function LanguageToggle({ language, onChange }: LanguageToggleProps) {
  const previousDocumentLanguage = useRef<string | null>(null);

  useEffect(() => {
    previousDocumentLanguage.current = document.documentElement.lang;
    return () => {
      if (previousDocumentLanguage.current !== null) {
        document.documentElement.lang = previousDocumentLanguage.current;
      }
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const changeLanguage = (nextLanguage: Language) => {
    // Update the accessibility tree synchronously with the interaction. The
    // flow callback then re-renders copy without ever translating fact keys.
    document.documentElement.lang = nextLanguage;
    onChange(nextLanguage);
  };

  return (
    <div
      className="oracle-toggle-group"
      role="group"
      aria-label={translate(language, "language.toggle.aria")}
    >
      <button
        type="button"
        aria-pressed={language === "en"}
        aria-label={translate(language, "language.option.en.aria")}
        onClick={() => changeLanguage("en")}
      >
        {translate(language, "language.option.en")}
      </button>
      <button
        type="button"
        aria-pressed={language === "id"}
        aria-label={translate(language, "language.option.id.aria")}
        onClick={() => changeLanguage("id")}
      >
        {translate(language, "language.option.id")}
      </button>
    </div>
  );
}
