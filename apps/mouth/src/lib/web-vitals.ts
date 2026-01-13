/**
 * Web Vitals Monitoring
 * Tracks Core Web Vitals (LCP, CLS, INP, TTFB) and sends to analytics
 */

'use client';

import { onCLS, onINP, onLCP, onTTFB, Metric } from 'web-vitals';

interface WebVitalsOptions {
  enabled?: boolean;
  debug?: boolean;
  sendToAnalytics?: (metric: Metric) => void;
}

let isInitialized = false;

/**
 * Initialize Web Vitals monitoring
 */
export function initWebVitals({
  enabled = process.env.NODE_ENV === 'production',
  debug = false,
  sendToAnalytics,
}: WebVitalsOptions = {}) {
  if (isInitialized || !enabled) return;
  isInitialized = true;

  const logMetric = (metric: Metric) => {
    if (debug) {
      console.log(`[Web Vitals] ${metric.name}:`, {
        value: metric.value,
        rating: metric.rating,
        delta: metric.delta,
        id: metric.id,
      });
    }

    // Send to custom analytics if provided
    if (sendToAnalytics) {
      sendToAnalytics(metric);
    }

    // Send to console for development
    if (debug || process.env.NODE_ENV === 'development') {
      const emoji = metric.rating === 'good' ? '✅' : metric.rating === 'needs-improvement' ? '⚠️' : '❌';
      console.log(`${emoji} [Web Vitals] ${metric.name}: ${metric.value.toFixed(2)}ms (${metric.rating})`);
    }
  };

  // Core Web Vitals
  onCLS(logMetric); // Cumulative Layout Shift
  onINP(logMetric); // Interaction to Next Paint
  onLCP(logMetric); // Largest Contentful Paint
  onTTFB(logMetric); // Time to First Byte

  // Log initialization
  if (debug) {
    console.log('[Web Vitals] Monitoring initialized');
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
  if (name === 'CLS') {
    return value.toFixed(3);
  }
  return `${Math.round(value)}ms`;
}

/**
 * Get metric rating color
 */
export function getMetricRatingColor(rating: 'good' | 'needs-improvement' | 'poor'): string {
  switch (rating) {
    case 'good':
      return 'text-green-500';
    case 'needs-improvement':
      return 'text-yellow-500';
    case 'poor':
      return 'text-red-500';
    default:
      return 'text-gray-500';
  }
}
