'use client';

import { useEffect, useCallback, useRef } from 'react';

export interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  action: () => void;
  description: string;
  enabled?: boolean;
}

export interface UseKeyboardShortcutsOptions {
  shortcuts: KeyboardShortcut[];
  enabled?: boolean;
  preventDefault?: boolean;
}

/**
 * Hook for managing keyboard shortcuts throughout the application.
 * Supports modifiers (Ctrl/Cmd, Shift, Alt) and provides a registry
 * of shortcuts that can be displayed in a help modal.
 *
 * @example
 * ```tsx
 * const { shortcuts } = useKeyboardShortcuts({
 *   shortcuts: [
 *     { key: 'k', metaKey: true, action: openSearch, description: 'Open search' },
 *     { key: 'Enter', metaKey: true, action: sendMessage, description: 'Send message' },
 *     { key: 'Escape', action: closeModal, description: 'Close modal' },
 *   ]
 * });
 * ```
 */
export function useKeyboardShortcuts({
  shortcuts,
  enabled = true,
  preventDefault = true,
}: UseKeyboardShortcutsOptions) {
  const shortcutsRef = useRef(shortcuts);

  // Keep shortcuts ref updated
  useEffect(() => {
    shortcutsRef.current = shortcuts;
  }, [shortcuts]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // Skip if user is typing in an input/textarea (unless it's a global shortcut)
      const target = event.target as HTMLElement;
      const isInput =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable;

      for (const shortcut of shortcutsRef.current) {
        // Skip disabled shortcuts
        if (shortcut.enabled === false) continue;

        // Check key match (case-insensitive)
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        if (!keyMatch) continue;

        // Check modifiers
        const ctrlOrMeta = shortcut.ctrlKey || shortcut.metaKey;
        const hasCtrlOrMeta = event.ctrlKey || event.metaKey;

        if (ctrlOrMeta && !hasCtrlOrMeta) continue;
        if (!ctrlOrMeta && hasCtrlOrMeta) continue;

        if (shortcut.shiftKey && !event.shiftKey) continue;
        if (!shortcut.shiftKey && event.shiftKey) continue;

        if (shortcut.altKey && !event.altKey) continue;
        if (!shortcut.altKey && event.altKey) continue;

        // For shortcuts with modifiers, always execute even in inputs
        // For shortcuts without modifiers, skip if in input (unless Escape)
        if (!ctrlOrMeta && !shortcut.shiftKey && !shortcut.altKey) {
          if (isInput && shortcut.key.toLowerCase() !== 'escape') continue;
        }

        // Execute the action
        if (preventDefault) {
          event.preventDefault();
          event.stopPropagation();
        }

        shortcut.action();
        return;
      }
    },
    [enabled, preventDefault]
  );

  useEffect(() => {
    if (!enabled) return;

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [enabled, handleKeyDown]);

  return {
    shortcuts: shortcuts.filter((s) => s.enabled !== false),
  };
}

/**
 * Format a shortcut for display
 * Returns something like "⌘K" or "Ctrl+Enter"
 */
export function formatShortcut(shortcut: KeyboardShortcut): string {
  const parts: string[] = [];
  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  if (shortcut.ctrlKey || shortcut.metaKey) {
    parts.push(isMac ? '⌘' : 'Ctrl');
  }
  if (shortcut.shiftKey) {
    parts.push(isMac ? '⇧' : 'Shift');
  }
  if (shortcut.altKey) {
    parts.push(isMac ? '⌥' : 'Alt');
  }

  // Format the key nicely
  let key = shortcut.key;
  if (key === 'Enter') key = '↵';
  else if (key === 'Escape') key = 'Esc';
  else if (key === 'ArrowUp') key = '↑';
  else if (key === 'ArrowDown') key = '↓';
  else if (key === 'ArrowLeft') key = '←';
  else if (key === 'ArrowRight') key = '→';
  else if (key === ' ') key = 'Space';
  else key = key.toUpperCase();

  parts.push(key);

  return isMac ? parts.join('') : parts.join('+');
}

/**
 * Common shortcuts that can be reused across the app
 */
export const COMMON_SHORTCUTS = {
  SEARCH: { key: 'k', metaKey: true, description: 'Open search' },
  SEND: { key: 'Enter', metaKey: true, description: 'Send message' },
  CLOSE: { key: 'Escape', description: 'Close/Cancel' },
  NEW_CHAT: { key: 'n', metaKey: true, description: 'New conversation' },
  HELP: { key: '?', shiftKey: true, description: 'Show keyboard shortcuts' },
} as const;

export default useKeyboardShortcuts;
