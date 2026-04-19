'use client';

import { ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import { DEFAULT_LOCALE, LOCALES, type Locale } from '@/i18n/types';

const LABEL: Record<Locale, (count: number) => string> = {
  en: (n) => (n > 0 ? `${n} new message${n === 1 ? '' : 's'}` : 'Jump to latest'),
  it: (n) => (n > 0 ? `${n} nuov${n === 1 ? 'o messaggio' : 'i messaggi'}` : "Vai all'ultimo"),
  id: (n) => (n > 0 ? `${n} pesan baru` : 'Ke pesan terbaru'),
  fr: (n) =>
    n > 0 ? `${n} nouveau${n === 1 ? '' : 'x'} message${n === 1 ? '' : 's'}` : 'Aller au dernier',
  ru: (n) => (n > 0 ? `${n} новое сообщение${n === 1 ? '' : '(й)'}` : 'К последнему'),
};

function useChatLocale(): Locale {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const saved = window.localStorage.getItem('blog-language');
      if (saved && (LOCALES as readonly string[]).includes(saved)) {
        setLocale(saved as Locale);
      }
    } catch {
      /* ignore */
    }
  }, []);
  return locale;
}

export interface NewMessagesPillProps {
  show: boolean;
  unreadCount: number;
  onClick: () => void;
}

/**
 * Floating pill that surfaces when the user has scrolled away from the bottom.
 * Click jumps to the latest message and clears the unread counter (managed by
 * the parent list component).
 */
export function NewMessagesPill({ show, unreadCount, onClick }: NewMessagesPillProps) {
  const locale = useChatLocale();
  const label = LABEL[locale](unreadCount);

  return (
    <AnimatePresence>
      {show && (
        <motion.button
          type="button"
          onClick={onClick}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.18 }}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--background-secondary)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] shadow-md hover:bg-[var(--background)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
          aria-live="polite"
          data-testid="new-messages-pill"
        >
          <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" />
          <span>{label}</span>
        </motion.button>
      )}
    </AnimatePresence>
  );
}
