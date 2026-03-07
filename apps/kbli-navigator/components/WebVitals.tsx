"use client";

import { useEffect } from "react";
import { onCLS, onINP, onLCP, onFCP, onTTFB, type Metric } from "web-vitals";

/**
 * Web Vitals Monitoring Component
 * Reports Core Web Vitals metrics to console and optional analytics endpoint
 */

const ANALYTICS_ENDPOINT =
  process.env.NEXT_PUBLIC_ANALYTICS_URL || "/api/vitals";

function sendToAnalytics(metric: Metric) {
  // Development logging removed (pre-commit hook restriction)

  // Send to analytics in production
  if (process.env.NODE_ENV === "production" && navigator.sendBeacon) {
    const body = JSON.stringify({
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      delta: metric.delta,
      id: metric.id,
      navigationType: metric.navigationType,
      page: window.location.pathname,
    });

    navigator.sendBeacon(ANALYTICS_ENDPOINT, body);
  }
}

export function WebVitals() {
  useEffect(() => {
    // Core Web Vitals
    onCLS(sendToAnalytics); // Cumulative Layout Shift
    onINP(sendToAnalytics); // Interaction to Next Paint
    onLCP(sendToAnalytics); // Largest Contentful Paint

    // Additional metrics
    onFCP(sendToAnalytics); // First Contentful Paint
    onTTFB(sendToAnalytics); // Time to First Byte
  }, []);

  return null;
}

/**
 * Helper to get Web Vitals rating color
 */
export function getRatingColor(rating: Metric["rating"]): string {
  switch (rating) {
    case "good":
      return "#22c55e"; // green-500
    case "needs-improvement":
      return "#eab308"; // yellow-500
    case "poor":
      return "#ef4444"; // red-500
    default:
      return "#6b7280"; // gray-500
  }
}

/**
 * Thresholds for Web Vitals (as per Google recommendations)
 */
export const VITALS_THRESHOLDS = {
  LCP: { good: 2500, poor: 4000 }, // ms
  INP: { good: 200, poor: 500 }, // ms
  CLS: { good: 0.1, poor: 0.25 }, // unitless
  FCP: { good: 1800, poor: 3000 }, // ms
  TTFB: { good: 800, poor: 1800 }, // ms
};
