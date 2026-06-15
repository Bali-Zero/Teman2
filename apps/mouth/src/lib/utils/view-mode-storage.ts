/**
 * View-mode persistence (P2.2).
 *
 * List pages (clients, process) reset their list/kanban/table toggle on every
 * navigation because the choice lived only in component state. These helpers
 * persist it via safeStorage (SSR-safe: returns the fallback on the server,
 * memory-fallback in Safari Private Browsing).
 */
import { safeStorage } from "./storage";

export const CLIENTS_VIEW_MODE_KEY = "kita:clients:viewMode";
export const PROCESS_VIEW_MODE_KEY = "kita:process:viewMode";

export function loadViewMode<T extends string>(
  key: string,
  validModes: readonly T[],
  fallback: T,
): T {
  const stored = safeStorage.getItem(key);
  return stored !== null && (validModes as readonly string[]).includes(stored)
    ? (stored as T)
    : fallback;
}

export function saveViewMode(key: string, mode: string): void {
  safeStorage.setItem(key, mode);
}
