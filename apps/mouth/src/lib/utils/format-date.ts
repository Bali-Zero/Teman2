/**
 * Shared date formatting utilities for the entire portal and workspace.
 * Single source of truth — replaces 20+ inline toLocaleDateString() calls.
 *
 * Standard locale: en-GB (day month year — matches Bali Zero house style).
 */

/** Full date: "25 Mar 2026" */
export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return "—";
  }
}

/** Short date without year: "25 Mar" */
export function formatDateShort(dateStr: string | undefined | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      timeZone: "UTC",
    });
  } catch {
    return "—";
  }
}

/** Long date: "25 March 2026" */
export function formatDateLong(dateStr: string | undefined | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return "—";
  }
}

/** Relative "time ago" for timeline entries: "2h ago", "3d ago", "Just now" */
export function formatTimeAgo(dateStr: string | undefined | null): string {
  if (!dateStr) return "—";
  try {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diffMs = now - then;
    if (diffMs < 0) return "upcoming";
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return formatDate(dateStr);
  } catch {
    return "—";
  }
}

/**
 * Long day span as years + months: "1y", "9y 2mo". Below a year it stays
 * months-only ("11mo"), the wording the workspace already used.
 *
 * Expiry chips used to stop at months, so a passport valid ~9 more years
 * rendered "111mo". Years count whole 365-day blocks; the remainder keeps the
 * 30-day month the chips always used, capped at 11 so "12mo" never appears.
 */
export function formatLongSpan(days: number): string {
  const whole = Math.max(0, Math.floor(days));
  const years = Math.floor(whole / 365);
  if (years === 0) return `${Math.floor(whole / 30)}mo`;
  const months = Math.min(11, Math.floor((whole % 365) / 30));
  return months === 0 ? `${years}y` : `${years}y ${months}mo`;
}
