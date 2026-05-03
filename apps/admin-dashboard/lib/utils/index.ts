/**
 * Utils Barrel Export
 */

export { cn } from "./cn";
export {
  escapeHtml,
  sanitizeSqlForDisplay,
  isValidTableName,
  isValidColumnName,
} from "@/lib/security/xss";
export {
  isValidUUID,
  isValidEmail,
  safeJsonParse,
  isValidCollectionName,
  sanitizeFileName,
  truncateText,
} from "@/lib/security/validation";
export {
  debug,
  warn,
  error,
  createLogger,
  stripConsoleInProduction,
} from "@/lib/logger";

// Format utilities
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
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

export function formatDate(date: string | Date): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
