/**
 * Dashboard Metrics System
 * Tracks all user interactions, performance, and system health
 * Coverage: 100% - All dashboard actions tracked
 */

import { logger } from '@/lib/logger';

export interface DashboardMetric {
  timestamp: Date;
  metricType: 'page_view' | 'button_click' | 'api_call' | 'error' | 'performance';
  component: string;
  action: string;
  value?: number;
  metadata?: Record<string, unknown>;
  userId?: string;
}

export interface PerformanceMetric {
  loadTime: number;
  apiCallCount: number;
  apiSuccessRate: number;
  renderTime: number;
  memoryUsage?: number;
}

class DashboardMetricsCollector {
  private metrics: DashboardMetric[] = [];
  private maxMetricsSize = 500;
  private performanceMarks: Map<string, number> = new Map();

  /**
   * Track page view
   */
  trackPageView(userId?: string): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'page_view',
      component: 'DashboardPage',
      action: 'page_loaded',
      userId,
    });

    logger.info('Dashboard page viewed', {
      component: 'DashboardMetrics',
      action: 'trackPageView',
      user: userId,
    });
  }

  /**
   * Track button click
   */
  trackButtonClick(buttonName: string, href?: string, userId?: string): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'button_click',
      component: 'DashboardPage',
      action: 'button_clicked',
      metadata: { buttonName, href },
      userId,
    });

    logger.info('Dashboard button clicked', {
      component: 'DashboardMetrics',
      action: 'trackButtonClick',
      user: userId,
      metadata: { buttonName, href },
    });
  }

  /**
   * Track API call
   */
  trackApiCall(
    endpoint: string,
    success: boolean,
    duration: number,
    userId?: string
  ): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'api_call',
      component: 'DashboardPage',
      action: success ? 'api_success' : 'api_failure',
      value: duration,
      metadata: { endpoint, success },
      userId,
    });

    if (!success) {
      logger.warn('Dashboard API call failed', {
        component: 'DashboardMetrics',
        action: 'trackApiCall',
        user: userId,
        metadata: { endpoint, duration },
      });
    }
  }

  /**
   * Track error
   */
  trackError(errorType: string, errorMessage: string, userId?: string): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'error',
      component: 'DashboardPage',
      action: 'error_occurred',
      metadata: { errorType, errorMessage },
      userId,
    });

    logger.error('Dashboard error tracked', {
      component: 'DashboardMetrics',
      action: 'trackError',
      user: userId,
      metadata: { errorType, errorMessage },
    });
  }

  /**
   * Start performance measurement
   */
  startPerformanceMark(markName: string): void {
    this.performanceMarks.set(markName, performance.now());
  }

  /**
   * End performance measurement and track
   */
  endPerformanceMark(markName: string, userId?: string): number {
    const startTime = this.performanceMarks.get(markName);
    if (!startTime) {
      logger.warn('Performance mark not found', {
        component: 'DashboardMetrics',
        action: 'endPerformanceMark',
        metadata: { markName },
      });
      return 0;
    }

    const duration = performance.now() - startTime;
    this.performanceMarks.delete(markName);

    this.addMetric({
      timestamp: new Date(),
      metricType: 'performance',
      component: 'DashboardPage',
      action: markName,
      value: duration,
      userId,
    });

    logger.debug('Performance metric recorded', {
      component: 'DashboardMetrics',
      action: 'endPerformanceMark',
      metadata: { markName, duration },
    });

    return duration;
  }

  /**
   * Get performance summary
   */
  getPerformanceSummary(): PerformanceMetric {
    const apiMetrics = this.metrics.filter(m => m.metricType === 'api_call');
    const performanceMetrics = this.metrics.filter(m => m.metricType === 'performance');

    const loadTimeMetric = performanceMetrics.find(m => m.action === 'dashboard_load');
    const renderTimeMetric = performanceMetrics.find(m => m.action === 'dashboard_render');

    const apiSuccessCount = apiMetrics.filter(m => m.action === 'api_success').length;
    const apiTotalCount = apiMetrics.length;

    return {
      loadTime: loadTimeMetric?.value || 0,
      apiCallCount: apiTotalCount,
      apiSuccessRate: apiTotalCount > 0 ? (apiSuccessCount / apiTotalCount) * 100 : 100,
      renderTime: renderTimeMetric?.value || 0,
      memoryUsage: this.getMemoryUsage(),
    };
  }

  /**
   * Get button click statistics
   */
  getButtonClickStats(): Record<string, number> {
    const buttonClicks = this.metrics.filter(m => m.metricType === 'button_click');
    const stats: Record<string, number> = {};

    buttonClicks.forEach(metric => {
      const buttonName = metric.metadata?.buttonName as string;
      if (buttonName) {
        stats[buttonName] = (stats[buttonName] || 0) + 1;
      }
    });

    return stats;
  }

  /**
   * Get error statistics
   */
  getErrorStats(): Record<string, number> {
    const errors = this.metrics.filter(m => m.metricType === 'error');
    const stats: Record<string, number> = {};

    errors.forEach(metric => {
      const errorType = metric.metadata?.errorType as string;
      if (errorType) {
        stats[errorType] = (stats[errorType] || 0) + 1;
      }
    });

    return stats;
  }

  /**
   * Get all metrics
   */
  getMetrics(): DashboardMetric[] {
    return [...this.metrics];
  }

  /**
   * Clear metrics
   */
  clearMetrics(): void {
    this.metrics = [];
    this.performanceMarks.clear();
    logger.debug('Dashboard metrics cleared', {
      component: 'DashboardMetrics',
      action: 'clearMetrics',
    });
  }

  /**
   * Export metrics for analysis
   */
  exportMetrics(): string {
    return JSON.stringify({
      metrics: this.metrics,
      summary: {
        performance: this.getPerformanceSummary(),
        buttonClicks: this.getButtonClickStats(),
        errors: this.getErrorStats(),
      },
      exportedAt: new Date().toISOString(),
    }, null, 2);
  }

  /**
   * Private: Add metric to collection
   */
  private addMetric(metric: DashboardMetric): void {
    this.metrics.push(metric);

    // Keep only last N metrics (circular buffer)
    if (this.metrics.length > this.maxMetricsSize) {
      this.metrics.shift();
    }

    // Store in localStorage for persistence (production)
    if (typeof window !== 'undefined' && process.env.NODE_ENV === 'production') {
      try {
        const storedMetrics = localStorage.getItem('dashboard_metrics');
        const metrics = storedMetrics ? JSON.parse(storedMetrics) : [];
        metrics.push(metric);

        // Keep only last 100 metrics in localStorage
        if (metrics.length > 100) {
          metrics.shift();
        }

        localStorage.setItem('dashboard_metrics', JSON.stringify(metrics));
      } catch (error) {
        logger.error('Failed to store metrics in localStorage', {
          component: 'DashboardMetrics',
          action: 'addMetric',
        }, error instanceof Error ? error : new Error(String(error)));
      }
    }
  }

  /**
   * Private: Get memory usage
   */
  private getMemoryUsage(): number | undefined {
    if (typeof window !== 'undefined' && 'memory' in performance) {
      const memory = (performance as any).memory;
      return memory?.usedJSHeapSize || undefined;
    }
    return undefined;
  }
}

// Singleton instance
export const dashboardMetrics = new DashboardMetricsCollector();

// Export type
export type { DashboardMetricsCollector };
