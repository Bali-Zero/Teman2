/**
 * Utils Barrel Export
 *
 * Centralized exports for all utilities
 */

// Security
export {
  sanitizeHtml,
  escapeHtml,
  sanitizeUrl,
  getSafeLinkProps,
} from "../security/xss";
export {
  isValidEmail,
  isValidPhone,
  sanitizeFileName,
  isAllowedFileType,
  safeJsonParse,
  isSafeUrl,
  truncateText,
  isValidUUID,
} from "../security/validation";

// Performance
export { debounce, debounceLeading } from "./performance/debounce";
export { throttle, throttleWithTrailing } from "./performance/throttle";
export { memoize, memoizeWithTTL, createMemoize } from "./performance/memoize";

// Console
export {
  debug,
  warn,
  error,
  createLogger,
  stripConsoleInProduction,
} from "./console";

// Common helpers
export function cn(
  ...classes: (string | boolean | undefined | null)[]
): string {
  return classes.filter(Boolean).join(" ");
}

export function formatDate(date: Date | string | number): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + "M";
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + "K";
  }
  return num.toString();
}
