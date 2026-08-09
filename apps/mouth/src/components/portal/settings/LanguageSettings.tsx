"use client";

import { useState } from "react";
import { usePortalPreferences } from "@/hooks/usePortal";
import { writeLanguageCookie } from "@/hooks/useLanguage";
import { Language } from "@/lib/schemas/settings";

const LABELS: Record<Language, string> = {
  it: "Italiano",
  en: "English",
  id: "Bahasa Indonesia",
};

/**
 * Language radiogroup backed by the same `client_preferences` row for both
 * reads and writes. The shared cross-subdomain cookie is updated only after
 * the backend confirms the change, so the control never claims that an
 * unpersisted selection was saved.
 */
export function LanguageSettings() {
  const {
    data: preferences,
    error,
    isLoading,
    isUpdating,
    updatePreferences,
  } = usePortalPreferences();
  const [pendingLanguage, setPendingLanguage] = useState<Language | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">(
    "idle",
  );

  if (isLoading) {
    return <p className="text-sm text-[var(--bz-text-2)]">Loading…</p>;
  }

  if (error || !preferences) {
    return (
      <p role="alert" className="text-sm text-[var(--state-danger)]">
        Unable to load language preference.
      </p>
    );
  }

  const parsed = Language.safeParse(preferences.language);
  const storedLanguage: Language = parsed.success ? parsed.data : "en";
  const current = pendingLanguage ?? storedLanguage;

  const selectLanguage = (language: Language): void => {
    if (isUpdating || language === current) return;

    setPendingLanguage(language);
    setSaveState("idle");
    updatePreferences(
      { language },
      {
        onSuccess: () => {
          writeLanguageCookie(language);
          setPendingLanguage(null);
          setSaveState("saved");
        },
        onError: () => {
          setPendingLanguage(null);
          setSaveState("error");
        },
      },
    );
  };

  return (
    <section className="space-y-3 max-w-md">
      <div role="radiogroup" aria-label="Language" className="space-y-2">
        {Language.options.map((lang) => (
          <label key={lang} className="flex items-center gap-3 cursor-pointer">
            <input
              type="radio"
              name="language"
              value={lang}
              checked={current === lang}
              disabled={isUpdating}
              onChange={() => selectLanguage(lang)}
              className="accent-[var(--bz-copper-text)] disabled:cursor-wait"
            />
            <span className="text-sm text-[var(--bz-text-1)]">
              {LABELS[lang]}
            </span>
          </label>
        ))}
      </div>

      <p
        aria-live="polite"
        className={`text-xs ${
          saveState === "error"
            ? "text-[var(--state-danger)]"
            : "text-[var(--bz-text-3)]"
        }`}
      >
        {isUpdating
          ? "Saving…"
          : saveState === "saved"
            ? "Language preference saved."
            : saveState === "error"
              ? "Unable to save language preference. Please try again."
              : "Your language choice is shared across Bali Zero portals."}
      </p>
    </section>
  );
}
