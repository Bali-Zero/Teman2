/**
 * XSS Prevention Utilities for Admin Dashboard
 */

/**
 * Escape HTML entities to prevent XSS
 */
export function escapeHtml(text: string): string {
  const div =
    typeof window !== "undefined" ? document.createElement("div") : null;
  if (div) {
    div.textContent = text;
    return div.innerHTML;
  }

  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Sanitize SQL query for display (not for execution!)
 */
export function sanitizeSqlForDisplay(query: string): string {
  // Remove potential HTML/script tags
  return query
    .replace(
      /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
      "[SCRIPT REMOVED]",
    )
    .replace(/<[^>]+>/g, "");
}

/**
 * Validate table name (alphanumeric and underscores only)
 */
export function isValidTableName(name: string): boolean {
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name);
}

/**
 * Validate column name
 */
export function isValidColumnName(name: string): boolean {
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name);
}
