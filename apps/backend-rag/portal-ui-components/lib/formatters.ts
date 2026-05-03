/**
 * Formatters Utility Library
 * Common formatting functions for portal UI components
 */

import { formatDistanceToNow, format, differenceInDays } from "date-fns";

/**
 * Format currency with locale support
 */
export function formatCurrency(
  amount: number,
  currency: string = "IDR",
): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format date in readable format
 */
export function formatDate(
  dateString: string,
  formatStr: string = "MMM dd, yyyy",
): string {
  return format(new Date(dateString), formatStr);
}

/**
 * Get relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(dateString: string): string {
  return formatDistanceToNow(new Date(dateString), { addSuffix: true });
}

/**
 * Get days until a date (negative if past)
 */
export function getDaysUntil(dateString: string): number {
  return differenceInDays(new Date(dateString), new Date());
}

/**
 * Format visa type for display
 */
export function formatVisaType(visaType: string): string {
  return visaType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Get status badge variant
 */
export function getStatusVariant(
  status: string,
): "success" | "warning" | "error" | "default" {
  const statusMap: Record<string, "success" | "warning" | "error" | "default"> =
    {
      active: "success",
      paid: "success",
      filed: "success",
      completed: "success",
      expiring_soon: "warning",
      pending: "warning",
      upcoming: "warning",
      expired: "error",
      overdue: "error",
      cancelled: "error",
    };

  return statusMap[status.toLowerCase()] || "default";
}

/**
 * Get urgency color based on days until deadline
 */
export function getUrgencyColor(daysUntil: number): "red" | "yellow" | "green" {
  if (daysUntil < 0) return "red";
  if (daysUntil < 7) return "red";
  if (daysUntil < 14) return "yellow";
  return "green";
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}
