'use client';

import { useEffect } from 'react';
import { initWebVitals } from '@/lib/web-vitals';

/**
 * Web Vitals Monitor Component
 * Initializes web vitals tracking on mount (currently disabled)
 */
export function WebVitalsMonitor() {
  useEffect(() => {
    // Initialize web vitals monitoring (currently disabled due to Vercel build issues)
    initWebVitals({
      enabled: true,
      debug: process.env.NODE_ENV === 'development',
    });
  }, []);

  return null;
}
