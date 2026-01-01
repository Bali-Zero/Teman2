'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Keyboard } from 'lucide-react';
import { KeyboardShortcut, formatShortcut } from '@/hooks/useKeyboardShortcuts';
import { cn } from '@/lib/utils';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
  shortcuts: KeyboardShortcut[];
  title?: string;
}

/**
 * Modal component to display available keyboard shortcuts
 */
export function KeyboardShortcutsModal({
  isOpen,
  onClose,
  shortcuts,
  title = 'Keyboard Shortcuts',
}: KeyboardShortcutsModalProps) {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Group shortcuts by category (based on key type)
  const groupedShortcuts = shortcuts.reduce(
    (acc, shortcut) => {
      const hasModifier = shortcut.ctrlKey || shortcut.metaKey || shortcut.altKey;
      const category = hasModifier ? 'Commands' : 'Navigation';
      if (!acc[category]) acc[category] = [];
      acc[category].push(shortcut);
      return acc;
    },
    {} as Record<string, KeyboardShortcut[]>
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[var(--z-modal)] bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className={cn(
              'fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
              'z-[var(--z-modal)] w-full max-w-md',
              'bg-[var(--background-elevated)] border border-[var(--border)]',
              'rounded-xl shadow-2xl overflow-hidden'
            )}
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-title"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[var(--accent-subtle)]">
                  <Keyboard className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <h2 id="shortcuts-title" className="text-lg font-semibold text-[var(--foreground)]">
                  {title}
                </h2>
              </div>
              <button
                onClick={onClose}
                className={cn(
                  'p-2 rounded-lg transition-colors',
                  'text-[var(--foreground-muted)] hover:text-[var(--foreground)]',
                  'hover:bg-[var(--background-hover)] focus-ring'
                )}
                aria-label="Close shortcuts modal"
              >
                <X size={18} />
              </button>
            </div>

            {/* Content */}
            <div className="px-6 py-4 max-h-[60vh] overflow-auto">
              {Object.entries(groupedShortcuts).map(([category, categoryShortcuts]) => (
                <div key={category} className="mb-6 last:mb-0">
                  <h3 className="text-xs font-medium text-[var(--foreground-muted)] uppercase tracking-wider mb-3">
                    {category}
                  </h3>
                  <div className="space-y-2">
                    {categoryShortcuts.map((shortcut, index) => (
                      <ShortcutRow key={index} shortcut={shortcut} />
                    ))}
                  </div>
                </div>
              ))}

              {shortcuts.length === 0 && (
                <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
                  No keyboard shortcuts available
                </p>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-[var(--border)] bg-[var(--background-secondary)]">
              <p className="text-xs text-[var(--foreground-muted)] text-center">
                Press <kbd className="kbd">?</kbd> to toggle this help
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

/**
 * Individual shortcut row
 */
function ShortcutRow({ shortcut }: { shortcut: KeyboardShortcut }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-[var(--background-hover)] transition-colors">
      <span className="text-sm text-[var(--foreground)]">{shortcut.description}</span>
      <kbd className="kbd">{formatShortcut(shortcut)}</kbd>
    </div>
  );
}

/**
 * Floating button to open keyboard shortcuts modal
 */
export function KeyboardShortcutsButton({
  onClick,
  className,
}: {
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'p-2 rounded-lg transition-colors',
        'text-[var(--foreground-muted)] hover:text-[var(--foreground)]',
        'hover:bg-[var(--background-hover)] focus-ring',
        className
      )}
      aria-label="Show keyboard shortcuts"
      title="Keyboard shortcuts (?)"
    >
      <Keyboard size={18} />
    </button>
  );
}

export default KeyboardShortcutsModal;
