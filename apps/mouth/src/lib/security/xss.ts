/**
 * XSS Prevention Utilities
 *
 * Provides safe HTML sanitization and content handling
 */

import DOMPurify from "dompurify";

/**
 * Sanitize HTML content to prevent XSS attacks
 * Use this instead of dangerouslySetInnerHTML
 */
export function sanitizeHtml(dirty: string): string {
  if (typeof window === "undefined") {
    // Server-side: return escaped text
    return escapeHtml(dirty);
  }

  // Client-side: use DOMPurify
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [
      "b",
      "i",
      "em",
      "strong",
      "a",
      "p",
      "br",
      "ul",
      "ol",
      "li",
      "code",
      "pre",
    ],
    ALLOWED_ATTR: ["href", "target", "rel"],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Escape HTML entities to prevent XSS
 * Safe for both server and client
 */
export function escapeHtml(text: string): string {
  const div =
    typeof window !== "undefined" ? document.createElement("div") : null;
  if (div) {
    div.textContent = text;
    return div.innerHTML;
  }

  // Server-side fallback
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Validate and sanitize URL to prevent javascript: injection
 */
export function sanitizeUrl(url: string): string {
  if (!url) return "";

  const sanitized = url.trim().toLowerCase();

  // Block javascript: and data: protocols
  if (
    sanitized.startsWith("javascript:") ||
    sanitized.startsWith("data:") ||
    sanitized.startsWith("vbscript:")
  ) {
    return "";
  }

  return url;
}

/**
 * Safe link props generator
 * Adds security attributes to external links
 */
export function getSafeLinkProps(href: string, isExternal?: boolean) {
  const isExternalUrl =
    isExternal ?? (href.startsWith("http") && !href.includes("balizero.com"));

  return {
    href: sanitizeUrl(href),
    target: isExternalUrl ? "_blank" : undefined,
    rel: isExternalUrl ? "noopener noreferrer nofollow" : undefined,
  };
}
