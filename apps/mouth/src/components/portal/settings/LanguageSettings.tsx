"use client";

import { useLanguage } from "@/hooks/useLanguage";
import { useMe } from "@/hooks/useMe";
import { Language } from "@/lib/schemas/settings";

const LABELS: Record<Language, string> = {
  it: "Italiano",
  en: "English",
  id: "Bahasa Indonesia",
};

/**
 * Language radiogroup. Reads current language from the profile (BE
 * source-of-truth), writes through `useLanguage.setLanguage` which is
 * cookie-first and then best-effort PATCHes /api/portal/settings.
 *
 * The BE does NOT enforce the `{it,en,id}` enum, so we narrow with
 * `Language.safeParse` and fall back to "en" when the stored value is
 * outside the supported set. *
 * WS3 slice 7 (GARUDA Day Edition): radios accent-[var(--bz-copper)],
 * labels --bz-text-1 (was accent-[#d4845a] + #f0ece4).
 */
export function LanguageSettings() {
  const { data: me } = useMe();
  const { setLanguage } = useLanguage();

  const parsed = Language.safeParse(me?.language ?? "en");
  const current: Language = parsed.success ? parsed.data : "en";

  return (
    <section
      className="space-y-2 max-w-md"
      role="radiogroup"
      aria-label="Language"
    >
      {Language.options.map((lang) => (
        <label key={lang} className="flex items-center gap-3 cursor-pointer">
          <input
            type="radio"
            name="language"
            value={lang}
            defaultChecked={current === lang}
            onChange={() => setLanguage(lang)}
            className="accent-[var(--bz-copper)]"
          />
          <span className="text-sm text-[var(--bz-text-1)]">
            {LABELS[lang]}
          </span>
        </label>
      ))}
    </section>
  );
}
