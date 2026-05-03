/**
 * Input Validation Utilities for Admin Dashboard
 */

/**
 * Validate UUID format
 */
export function isValidUUID(uuid: string): boolean {
  const uuidRegex =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Safe JSON parse with fallback
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}

/**
 * Validate collection name (for Qdrant)
 */
export function isValidCollectionName(name: string): boolean {
  return /^[a-zA-Z0-9_-]+$/.test(name) && name.length > 0 && name.length <= 255;
}

/**
 * Sanitize file name
 */
export function sanitizeFileName(fileName: string): string {
  return (
    fileName
      .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
      .replace(/\.{2,}/g, "_")
      .replace(/^\.+/, "")
      .trim() || "unnamed"
  );
}

/**
 * Truncate text to max length
 */
export function truncateText(
  text: string,
  maxLength: number,
  suffix = "...",
): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - suffix.length) + suffix;
}
