'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Source } from '@/types';

const HOVER_OPEN_DELAY_MS = 250;
const HOVER_CLOSE_DELAY_MS = 150;
const PREVIEW_CHARS = 220;

export interface CitationPopoverProps {
  source: Source;
  children: React.ReactNode;
  /** Disable popover behaviour (e.g. when expander is already open). */
  disabled?: boolean;
}

/**
 * Hover/focus preview around a source title. Renders content lazily and
 * supports keyboard a11y (focus-visible opens, ESC closes). Pure presentation
 * — does NOT affect the surrounding `<CitationCard>` expand/collapse state,
 * so it composes cleanly with the existing click-to-expand UX.
 */
export function CitationPopover({ source, children, disabled }: CitationPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const openTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const popoverId = useId();

  useEffect(() => {
    return () => {
      if (openTimer.current) clearTimeout(openTimer.current);
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen]);

  if (disabled) return <>{children}</>;

  const scheduleOpen = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    openTimer.current = setTimeout(() => setIsOpen(true), HOVER_OPEN_DELAY_MS);
  };

  const scheduleClose = () => {
    if (openTimer.current) {
      clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    closeTimer.current = setTimeout(() => setIsOpen(false), HOVER_CLOSE_DELAY_MS);
  };

  const previewText = (() => {
    const raw = source.content || source.snippet || '';
    if (!raw) return null;
    return raw.length > PREVIEW_CHARS ? `${raw.slice(0, PREVIEW_CHARS).trimEnd()}…` : raw;
  })();

  return (
    <span
      className="relative inline-block"
      onMouseEnter={scheduleOpen}
      onMouseLeave={scheduleClose}
      onFocus={scheduleOpen}
      onBlur={scheduleClose}
      aria-describedby={isOpen ? popoverId : undefined}
    >
      {children}
      <AnimatePresence>
        {isOpen && previewText && (
          <motion.div
            id={popoverId}
            role="tooltip"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.15 }}
            className="absolute z-50 bottom-full left-0 mb-2 w-72 max-w-[80vw] rounded-md border border-[var(--border)] bg-[var(--background-secondary)] p-3 text-xs text-[var(--foreground)] shadow-lg pointer-events-auto"
            data-testid="citation-popover"
          >
            {source.title && <div className="font-semibold mb-1 truncate">{source.title}</div>}
            <div className="text-[var(--foreground-muted)] leading-snug whitespace-pre-line">
              {previewText}
            </div>
            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-[var(--accent)] hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                View source ↗
              </a>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}
