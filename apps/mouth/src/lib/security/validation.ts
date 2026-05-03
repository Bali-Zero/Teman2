/**
 * Input Validation Utilities
 *
 * Safe validation for user inputs
 */

/**
 * Validate email address format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate phone number (basic international format)
 */
export function isValidPhone(phone: string): boolean {
  // Remove common separators
  const clean = phone.replace(/[\s\-\.\(\)\+]/g, "");
  // Check for 7-15 digits
  return /^\d{7,15}$/.test(clean);
}

/**
 * Sanitize file name to prevent path traversal
 */
export function sanitizeFileName(fileName: string): string {
  return (
    fileName
      .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_") // Remove invalid chars
      .replace(/\.{2,}/g, "_") // Prevent ../
      .replace(/^\.+/, "") // Remove leading dots
      .trim() || "unnamed"
  );
}

/**
 * Validate file type against allowed types
 */
export function isAllowedFileType(
  fileName: string,
  allowedTypes: string[],
): boolean {
  const ext = fileName.split(".").pop()?.toLowerCase() || "";
  return allowedTypes.includes(ext);
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
 * Validate URL is safe (no javascript: protocol)
 */
export function isSafeUrl(url: string): boolean {
  if (!url) return false;

  const lower = url.toLowerCase().trim();

  // Block dangerous protocols
  const dangerous = ["javascript:", "data:", "vbscript:", "file:"];
  return !dangerous.some((proto) => lower.startsWith(proto));
}

/**
 * Truncate text to maximum length
 */
export function truncateText(
  text: string,
  maxLength: number,
  suffix = "...",
): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - suffix.length) + suffix;
}

/**
 * Validate UUID format
 */
export function isValidUUID(uuid: string): boolean {
  const uuidRegex =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
}
