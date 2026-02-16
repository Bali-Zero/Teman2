"use client";

import { logger } from "@/lib/logger";
/**
 * Web Vitals Monitoring
 * Tracks Core Web Vitals (LCP, CLS, INP, TTFB) and sends to analytics
 */

// Web Vitals monitoring disabled temporarily due to Vercel build issues
// Status: Tracked in backlog - Re-enable when dependency resolution is fixed

// Define Metric type locally
interface Metric {
  name: "CLS" | "INP" | "LCP" | "TTFB" | "FCP" | "FID";
  value: number;
  rating: "good" | "needs-improvement" | "poor";
  delta: number;
  id: string;
  navigationType: string;
}

interface WebVitalsOptions {
  enabled?: boolean;
  debug?: boolean;
  sendToAnalytics?: (metric: Metric) => void;
}

/**
 * Initialize Web Vitals monitoring (currently disabled)
 */
export function initWebVitals(_options: WebVitalsOptions = {}) {
  // Disabled - web-vitals package has resolution issues on Vercel
  // Will be re-enabled when fixed
  if (process.env.NODE_ENV === "development") {
    logger.debug("[Web Vitals] Monitoring temporarily disabled", {
      component: "AUTO",
      action: "log",
    });
  }
}

/**
 * Get INP threshold recommendations
 */
export const INP_THRESHOLDS = {
  good: 200, // < 200ms
  needsImprovement: 500, // 200-500ms
  poor: 500, // > 500ms
} as const;

/**
 * Format metric value for display
 */
export function formatMetricValue(value: number, name: string): string {
  if (name === "CLS") {
    return value.toFixed(3);
  }
  return `${Math.round(value)}ms`;
}

/**
 * Get metric rating color
 */
export function getMetricRatingColor(
  rating: "good" | "needs-improvement" | "poor",
): string {
  switch (rating) {
    case "good":
      return "text-green-500";
    case "needs-improvement":
      return "text-yellow-500";
    case "poor":
      return "text-red-500";
    default:
      return "text-gray-500";
  }
}
