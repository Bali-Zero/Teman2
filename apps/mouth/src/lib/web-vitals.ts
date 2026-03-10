"use client";

import { logger } from "@/lib/logger";

/**
 * Web Vitals Monitoring
 * Tracks Core Web Vitals: LCP, CLS, INP, TTFB, FCP
 * Sends to GA4 via gtag if available, and logs for debugging.
 */

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

function sendToGA4(metric: Metric): void {
  if (typeof window === "undefined") return;
  const win = window as typeof window & {
    gtag?: (...args: unknown[]) => void;
  };
  if (typeof win.gtag !== "function") return;

  win.gtag("event", metric.name, {
    event_category: "Web Vitals",
    event_label: metric.id,
    value: Math.round(
      metric.name === "CLS" ? metric.value * 1000 : metric.value,
    ),
    non_interaction: true,
    metric_rating: metric.rating,
  });
}

/**
 * Initialize Web Vitals monitoring.
 * Uses dynamic import to avoid SSR issues and bundle bloat on non-supporting browsers.
 */
export function initWebVitals(options: WebVitalsOptions = {}): void {
  const { enabled = true, debug = false, sendToAnalytics } = options;

  if (!enabled || typeof window === "undefined") return;

  import("web-vitals")
    .then(({ onCLS, onINP, onLCP, onTTFB, onFCP }) => {
      const handle = (metric: Metric): void => {
        if (debug) {
          logger.info(
            `[Web Vitals] ${metric.name}: ${formatMetricValue(metric.value, metric.name)} (${metric.rating})`,
            { component: "WebVitals", action: "metric" },
          );
        }
        sendToGA4(metric);
        sendToAnalytics?.(metric);
      };

      onCLS(handle as Parameters<typeof onCLS>[0]);
      onINP(handle as Parameters<typeof onINP>[0]);
      onLCP(handle as Parameters<typeof onLCP>[0]);
      onTTFB(handle as Parameters<typeof onTTFB>[0]);
      onFCP(handle as Parameters<typeof onFCP>[0]);
    })
    .catch((err) => {
      logger.error(
        "[Web Vitals] Failed to load web-vitals package",
        {},
        err instanceof Error ? err : new Error(String(err)),
      );
    });
}

export const INP_THRESHOLDS = {
  good: 200,
  needsImprovement: 500,
  poor: 500,
} as const;

export function formatMetricValue(value: number, name: string): string {
  if (name === "CLS") return value.toFixed(3);
  return `${Math.round(value)}ms`;
}

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
