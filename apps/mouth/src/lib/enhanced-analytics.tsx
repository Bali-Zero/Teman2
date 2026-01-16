/**
 * Enhanced Analytics Hook (Stub)
 *
 * This is a stub implementation to prevent build errors.
 * Analytics tracking is handled by other systems.
 */

export function useEnhancedAnalytics() {
  return {
    trackPageView: (_path: string, _title?: string) => {
      // No-op: Analytics tracking handled elsewhere
    },
    trackUserInteraction: (_type: string, _target: string, _context?: string) => {
      // No-op: Analytics tracking handled elsewhere
    },
    trackPerformance: (_metrics: Record<string, number>) => {
      // No-op: Analytics tracking handled elsewhere
    },
    trackEvent: (_eventName: string, _category: string, _label?: string) => {
      // No-op: Analytics tracking handled elsewhere
    },
  };
}
