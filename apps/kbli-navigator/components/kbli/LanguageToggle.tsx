'use client';

import { useState, useEffect, createContext, useContext, type ReactNode } from 'react';

type Language = 'en' | 'id';

interface LanguageContextValue {
  lang: Language;
  toggle: () => void;
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: 'en',
  toggle: () => {},
});

export function useLanguage() {
  return useContext(LanguageContext);
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Language>('en');

  useEffect(() => {
    const saved = localStorage.getItem('kbli-lang') as Language | null;
    if (saved === 'en' || saved === 'id') setLang(saved);
  }, []);

  const toggle = () => {
    setLang((prev) => {
      const next = prev === 'en' ? 'id' : 'en';
      localStorage.setItem('kbli-lang', next);
      return next;
    });
  };

  return <LanguageContext.Provider value={{ lang, toggle }}>{children}</LanguageContext.Provider>;
}

export function LanguageToggle() {
  const { lang, toggle } = useLanguage();

  return (
    <button
      type="button"
      onClick={toggle}
      className="flex items-center overflow-hidden rounded-full border border-[var(--border)]
                 bg-[var(--kbli-bg-secondary)] text-xs font-medium"
      aria-label={`Switch to ${lang === 'en' ? 'Indonesian' : 'English'}`}
      aria-pressed={lang === 'id'}
      title={`Current language: ${lang === 'en' ? 'English' : 'Indonesian'}`}
    >
      <span
        className={`px-2.5 py-1 transition-all ${
          lang === 'en'
            ? 'bg-[var(--kbli-accent-muted)] text-[var(--kbli-accent)]'
            : 'text-[var(--foreground-muted)]'
        }`}
        aria-current={lang === 'en' ? 'true' : undefined}
      >
        EN
      </span>
      <span
        className={`px-2.5 py-1 transition-all ${
          lang === 'id'
            ? 'bg-[var(--kbli-accent-muted)] text-[var(--kbli-accent)]'
            : 'text-[var(--foreground-muted)]'
        }`}
        aria-current={lang === 'id' ? 'true' : undefined}
      >
        ID
      </span>
    </button>
  );
}
