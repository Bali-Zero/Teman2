"use client";

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
  return (
    <div
      className="oracle-toggle-group"
      role="group"
      aria-label={translate(language, "language.toggle.aria")}
    >
      <button
        type="button"
        aria-pressed={language === "en"}
        onClick={() => onChange("en")}
      >
        {translate(language, "language.option.en")}
      </button>
      <button
        type="button"
        aria-pressed={language === "id"}
        onClick={() => onChange("id")}
      >
        {translate(language, "language.option.id")}
      </button>
    </div>
  );
}
