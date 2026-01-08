/**
 * Enhanced Analytics with GA4 integration and enterprise metrics
 * Extends existing analytics with dashboard-specific tracking
 */

import { trackEvent, AnalyticsEvent } from './analytics';

interface DashboardAnalyticsEvent extends AnalyticsEvent {
  category: string;
  action: string;
  label?: string;
  value?: number;
}

interface UserProperties {
  role?: string;
  email?: string;
  isAdmin?: boolean;
}

interface PerformanceMetrics {
  loadTime: number;
  renderTime: number;
  apiCallTime: number;
  errorCount: number;
}

class EnhancedAnalyticsService {
  private isInitialized = false;
  private userId: string | null = null;
  private performanceMetrics: PerformanceMetrics = {
    loadTime: 0,
    renderTime: 0,
    apiCallTime: 0,
    errorCount: 0,
  };

  initialize(userId: string, userProperties: UserProperties) {
    if (typeof window === 'undefined' || !window.gtag) return;

    this.userId = userId;
    this.isInitialized = true;

    // Set user properties in GA4
    window.gtag('config', process.env.NEXT_PUBLIC_GA_ID || '', {
      user_id: userId,
      custom_map: {
        custom_parameter_1: 'role',
        custom_parameter_2: 'admin_status',
      },
    });

    // Set user properties
    window.gtag('set', 'user_properties', {
      role: userProperties.role,
      admin_status: userProperties.isAdmin ? 'admin' : 'user',
    });

    // Track login event
    this.trackEvent('login', 'authentication', userProperties.role);
  }

  trackEvent(action: string, category: string, label?: string, value?: number) {
    if (!this.isInitialized || typeof window === 'undefined' || !window.gtag) return;

    const event: DashboardAnalyticsEvent = {
      event_name: action,
      timestamp: new Date().toISOString(),
      user_id: this.userId || undefined,
      category,
      action,
      label,
      value,
      properties: {
        category,
        action,
        label,
        value,
      },
    };

    // Send to GA4
    window.gtag('event', action, {
      event_category: category,
      event_label: label,
      value: value,
      custom_parameter_1: this.userId,
    });

    // Also send to base analytics
    trackEvent(event.event_name, event.properties);

    // Console for development
    if (process.env.NODE_ENV === 'development') {
      console.log('📊 Analytics Event:', event);
    }
  }

  trackPageView(page: string, title?: string) {
    if (!this.isInitialized || typeof window === 'undefined' || !window.gtag) return;

    window.gtag('config', process.env.NEXT_PUBLIC_GA_ID || '', {
      page_path: page,
      page_title: title,
    });

    // Also track in base analytics
    trackEvent('page_view', { page, title });

    if (process.env.NODE_ENV === 'development') {
      console.log('📊 Page View:', { page, title });
    }
  }

  trackPerformance(metrics: Partial<PerformanceMetrics>) {
    this.performanceMetrics = { ...this.performanceMetrics, ...metrics };

    if (process.env.NODE_ENV === 'development') {
      console.log('📊 Performance Metrics:', this.performanceMetrics);
    }

    // Track performance events
    if (metrics.loadTime) {
      this.trackEvent('dashboard_load', 'performance', undefined, Math.round(metrics.loadTime));
    }

    if (metrics.apiCallTime) {
      this.trackEvent('api_call', 'performance', undefined, Math.round(metrics.apiCallTime));
    }

    if (metrics.errorCount && metrics.errorCount > 0) {
      this.trackEvent('error', 'system', undefined, metrics.errorCount);
    }
  }

  trackUserInteraction(action: string, element: string, context?: string) {
    this.trackEvent(action, 'user_interaction', `${element}${context ? ` - ${context}` : ''}`);
  }

  trackDashboardFeature(feature: string, action: string = 'use') {
    this.trackEvent(`${action}_${feature}`, 'dashboard_feature', feature);
  }

  trackError(error: Error, context?: string) {
    this.performanceMetrics.errorCount += 1;
    
    this.trackEvent('javascript_error', 'error', `${error.name}: ${error.message}`);
    
    if (process.env.NODE_ENV === 'development') {
      console.error('📊 Tracked Error:', error, context);
    }
  }

  trackApiCall(endpoint: string, method: string, duration: number, success: boolean) {
    this.trackEvent(
      success ? 'api_success' : 'api_error',
      'api_call',
      `${method} ${endpoint}`,
      Math.round(duration)
    );
  }

  // A/B Testing tracking
  trackExperiment(experimentName: string, variant: string) {
    this.trackEvent('experiment_view', 'ab_test', `${experimentName}_${variant}`);
  }

  trackConversion(goal: string, value?: number) {
    this.trackEvent('conversion', 'ab_test', goal, value);
  }

  // Dashboard specific tracking
  trackDashboardLoad(startTime: number) {
    const loadTime = performance.now() - startTime;
    this.trackPerformance({ loadTime });
    this.trackEvent('dashboard_loaded', 'dashboard', undefined, Math.round(loadTime));
  }

  trackWidgetInteraction(widgetName: string, action: string) {
    this.trackEvent(`widget_${action}`, 'dashboard', widgetName);
  }

  trackEmailAction(action: 'delete' | 'read' | 'send' | 'reply', count: number = 1) {
    this.trackEvent(`email_${action}`, 'email', undefined, count);
  }

  trackCaseAction(action: 'view' | 'edit' | 'create' | 'delete', caseType?: string) {
    this.trackEvent(`case_${action}`, 'crm', caseType);
  }

  // Get metrics for reporting
  getMetrics(): PerformanceMetrics {
    return { ...this.performanceMetrics };
  }

  resetMetrics() {
    this.performanceMetrics = {
      loadTime: 0,
      renderTime: 0,
      apiCallTime: 0,
      errorCount: 0,
    };
  }
}

// Singleton instance
export const enhancedAnalytics = new EnhancedAnalyticsService();

// React hook for enhanced analytics
export function useEnhancedAnalytics() {
  return {
    trackEvent: enhancedAnalytics.trackEvent.bind(enhancedAnalytics),
    trackPageView: enhancedAnalytics.trackPageView.bind(enhancedAnalytics),
    trackUserInteraction: enhancedAnalytics.trackUserInteraction.bind(enhancedAnalytics),
    trackDashboardFeature: enhancedAnalytics.trackDashboardFeature.bind(enhancedAnalytics),
    trackError: enhancedAnalytics.trackError.bind(enhancedAnalytics),
    trackEmailAction: enhancedAnalytics.trackEmailAction.bind(enhancedAnalytics),
    trackCaseAction: enhancedAnalytics.trackCaseAction.bind(enhancedAnalytics),
    trackPerformance: enhancedAnalytics.trackPerformance.bind(enhancedAnalytics),
    trackExperiment: enhancedAnalytics.trackExperiment.bind(enhancedAnalytics),
    trackConversion: enhancedAnalytics.trackConversion.bind(enhancedAnalytics),
    trackDashboardLoad: enhancedAnalytics.trackDashboardLoad.bind(enhancedAnalytics),
    trackWidgetInteraction: enhancedAnalytics.trackWidgetInteraction.bind(enhancedAnalytics),
  };
}

// Higher-order component for automatic tracking
import React from 'react';

export function withEnhancedAnalytics<P extends object>(
  Component: React.ComponentType<P>,
  options: {
    trackPageView?: boolean;
    trackPerformance?: boolean;
    componentName?: string;
  } = {}
) {
  const WrappedComponent = (props: P) => {
    const startTime = React.useRef(performance.now());
    const { trackPageView, trackPerformance } = useEnhancedAnalytics();

    React.useEffect(() => {
      if (options.trackPageView !== false) {
        const componentName = options.componentName || Component.displayName || Component.name;
        trackPageView(`/${componentName.toLowerCase()}`, componentName);
      }

      if (options.trackPerformance !== false) {
        const loadTime = performance.now() - startTime.current;
        trackPerformance({ loadTime });
      }
    }, []);

    return <Component {...props} />;
  };

  WrappedComponent.displayName = `withEnhancedAnalytics(${Component.displayName || Component.name})`;
  return WrappedComponent;
}

// Type declarations for gtag
declare global {
  interface Window {
    gtag: (
      command: 'config' | 'event' | 'set',
      targetId: string | Record<string, any>,
      config?: Record<string, any>
    ) => void;
  }
}
