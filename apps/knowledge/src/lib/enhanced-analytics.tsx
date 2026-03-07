export function useEnhancedAnalytics() {
  return {
    trackPageView: (_path: string, _title?: string) => {},
    trackUserInteraction: (
      _type: string,
      _target: string,
      _value?: string,
    ) => {},
    trackPerformance: (_metrics: Record<string, number>) => {},
    trackEvent: (
      _event: string,
      _category?: string,
      _label?: string,
      _value?: number,
    ) => {},
  };
}
