'use client';

import { useEffect } from 'react';
import { initWebVitals } from '@/lib/web-vitals';
import { Metric } from 'web-vitals';

/**
 * Web Vitals Monitor Component
 * Initializes web vitals tracking on mount
 */
export function WebVitalsMonitor() {
  useEffect(() => {
    // Initialize web vitals monitoring
    initWebVitals({
      enabled: true,
      debug: process.env.NODE_ENV === 'development',
      sendToAnalytics: (metric: Metric) => {
        // Send to analytics service (e.g., Sentry, Google Analytics, etc.)
        // Example: Sentry
        // if (typeof window !== 'undefined' && window.Sentry) {
        //   window.Sentry.metrics.distribution('web_vitals', metric.value, {
        //     tags: {
        //       metric_name: metric.name,
        //       rating: metric.rating,
        //     },
        //   });
        // }

        // Log to console in development
        if (process.env.NODE_ENV === 'development') {
          const emoji = metric.rating === 'good' ? '✅' : metric.rating === 'needs-improvement' ? '⚠️' : '❌';
          console.log(`${emoji} [Web Vitals] ${metric.name}: ${metric.value.toFixed(2)}ms (${metric.rating})`);
        }

        // Track INP specifically (most important for interactivity)
        if (metric.name === 'INP' && metric.rating === 'poor') {
          console.warn(`⚠️ [Performance] Poor INP detected: ${metric.value.toFixed(2)}ms. Consider optimizing interactions.`);
        }
      },
    });
  }, []);

  return null; // This component doesn't render anything
}
