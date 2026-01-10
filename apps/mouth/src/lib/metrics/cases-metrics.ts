/**
 * Cases Metrics System
 * Tracks all user interactions, performance, and system health for the Cases module
 * Coverage: 100% - All case actions tracked
 */

import { logger } from '@/lib/logger';

export interface CaseMetric {
  timestamp: Date;
  metricType: 'page_view' | 'button_click' | 'api_call' | 'error' | 'performance' | 'user_action';
  component: string;
  action: string;
  value?: number;
  metadata?: Record<string, unknown>;
  userId?: string;
  caseId?: number;
}

export interface CasePerformanceMetric {
  pageLoadTime: number;
  apiCallCount: number;
  apiSuccessRate: number;
  renderTime: number;
  errorCount: number;
  caseActionCount: number;
}

class CasesMetricsCollector {
  private metrics: CaseMetric[] = [];
  private maxMetricsSize = 1000; // Increased for case-heavy usage
  private performanceMarks: Map<string, number> = new Map();
  private sessionStats = {
    casesViewed: new Set<number>(),
    casesCreated: 0,
    casesEdited: 0,
    statusChanges: 0,
    apiCalls: 0,
    errors: 0,
  };

  /**
   * Track page view (Cases list, detail, or new)
   */
  trackPageView(page: 'list' | 'detail' | 'new', caseId?: number, userId?: string): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'page_view',
      component: `Cases${page.charAt(0).toUpperCase() + page.slice(1)}Page`,
      action: 'page_loaded',
      caseId,
      userId,
      metadata: { page },
    });

    if (caseId) {
      this.sessionStats.casesViewed.add(caseId);
    }

    logger.info('Case page viewed', {
      component: 'CasesMetrics',
      action: 'trackPageView',
      user: userId,
      metadata: { page, caseId },
    });
  }

  /**
   * Track button click
   */
  trackButtonClick(
    buttonName: string,
    page: string,
    caseId?: number,
    href?: string,
    userId?: string
  ): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'button_click',
      component: page,
      action: 'button_clicked',
      caseId,
      metadata: { buttonName, href },
      userId,
    });

    logger.info('Case button clicked', {
      component: 'CasesMetrics',
      action: 'trackButtonClick',
      user: userId,
      metadata: { buttonName, page, caseId },
    });
  }

  /**
   * Track case creation
   */
  trackCaseCreation(
    caseId: number,
    caseType: string,
    clientId: number,
    userId?: string
  ): void {
    this.sessionStats.casesCreated += 1;

    this.addMetric({
      timestamp: new Date(),
      metricType: 'user_action',
      component: 'CasesNewPage',
      action: 'case_created',
      caseId,
      metadata: { caseType, clientId },
      userId,
    });

    logger.info('Case created', {
      component: 'CasesMetrics',
      action: 'trackCaseCreation',
      user: userId,
      metadata: { caseId, caseType, clientId },
    });
  }

  /**
   * Track case edit/update
   */
  trackCaseUpdate(
    caseId: number,
    fieldsUpdated: string[],
    updateType: 'status' | 'details' | 'payment',
    userId?: string
  ): void {
    this.sessionStats.casesEdited += 1;

    if (updateType === 'status') {
      this.sessionStats.statusChanges += 1;
    }

    this.addMetric({
      timestamp: new Date(),
      metricType: 'user_action',
      component: 'CasesDetailPage',
      action: 'case_updated',
      caseId,
      metadata: { fieldsUpdated, updateType },
      userId,
    });

    logger.info('Case updated', {
      component: 'CasesMetrics',
      action: 'trackCaseUpdate',
      user: userId,
      metadata: { caseId, fieldsUpdated, updateType },
    });
  }

  /**
   * Track quick action (WhatsApp, Email, Documents)
   */
  trackQuickAction(
    actionType: 'whatsapp' | 'email' | 'phone' | 'documents',
    caseId: number,
    page: string,
    userId?: string
  ): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'user_action',
      component: page,
      action: `quick_action_${actionType}`,
      caseId,
      metadata: { actionType },
      userId,
    });

    logger.info('Quick action performed', {
      component: 'CasesMetrics',
      action: 'trackQuickAction',
      user: userId,
      metadata: { actionType, caseId, page },
    });
  }

  /**
   * Track client search in new case form
   */
  trackClientSearch(query: string, resultsCount: number, userId?: string): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'user_action',
      component: 'CasesNewPage',
      action: 'client_search',
      metadata: { queryLength: query.length, resultsCount },
      userId,
    });

    logger.debug('Client search performed', {
      component: 'CasesMetrics',
      action: 'trackClientSearch',
      metadata: { queryLength: query.length, resultsCount },
    });
  }

  /**
   * Track form field interaction
   */
  trackFormField(
    fieldName: string,
    action: 'focus' | 'change' | 'blur',
    page: string,
    userId?: string
  ): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'user_action',
      component: page,
      action: `form_field_${action}`,
      metadata: { fieldName },
      userId,
    });
  }

  /**
   * Track modal open/close
   */
  trackModal(
    modalType: 'edit' | 'delete' | 'status_change' | 'client_select',
    action: 'open' | 'close' | 'submit',
    caseId?: number,
    userId?: string
  ): void {
    this.addMetric({
      timestamp: new Date(),
      metricType: 'user_action',
      component: 'CasesDetailPage',
      action: `modal_${action}`,
      caseId,
      metadata: { modalType },
      userId,
    });

    logger.debug('Modal interaction', {
      component: 'CasesMetrics',
      action: 'trackModal',
      metadata: { modalType, action, caseId },
    });
  }

  /**
   * Track API call
   */
  trackApiCall(
    endpoint: string,
    method: string,
    success: boolean,
    duration: number,
    caseId?: number,
    userId?: string
  ): void {
    this.sessionStats.apiCalls += 1;

    this.addMetric({
      timestamp: new Date(),
      metricType: 'api_call',
      component: 'CasesModule',
      action: success ? 'api_success' : 'api_failure',
      value: duration,
      caseId,
      metadata: { endpoint, method, success },
      userId,
    });

    if (!success) {
      logger.warn('Cases API call failed', {
        component: 'CasesMetrics',
        action: 'trackApiCall',
        user: userId,
        metadata: { endpoint, method, duration, caseId },
      });
    }
  }

  /**
   * Track error
   */
  trackError(
    errorType: string,
    errorMessage: string,
    page: string,
    caseId?: number,
    userId?: string
  ): void {
    this.sessionStats.errors += 1;

    this.addMetric({
      timestamp: new Date(),
      metricType: 'error',
      component: page,
      action: 'error_occurred',
      caseId,
      metadata: { errorType, errorMessage },
      userId,
    });

    logger.error('Cases error tracked', {
      component: 'CasesMetrics',
      action: 'trackError',
      user: userId,
      metadata: { errorType, errorMessage, page, caseId },
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
  endPerformanceMark(markName: string, caseId?: number, userId?: string): number {
    const startTime = this.performanceMarks.get(markName);
    if (!startTime) {
      logger.warn('Performance mark not found', {
        component: 'CasesMetrics',
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
      component: 'CasesModule',
      action: markName,
      value: duration,
      caseId,
      userId,
    });

    logger.debug('Performance metric recorded', {
      component: 'CasesMetrics',
      action: 'endPerformanceMark',
      metadata: { markName, duration, caseId },
    });

    return duration;
  }

  /**
   * Get performance summary
   */
  getPerformanceSummary(): CasePerformanceMetric {
    const apiMetrics = this.metrics.filter(m => m.metricType === 'api_call');
    const performanceMetrics = this.metrics.filter(m => m.metricType === 'performance');

    const loadTimeMetric = performanceMetrics.find(m => m.action === 'case_page_load');
    const renderTimeMetric = performanceMetrics.find(m => m.action === 'case_render');

    const apiSuccessCount = apiMetrics.filter(m => m.action === 'api_success').length;
    const apiTotalCount = apiMetrics.length;

    return {
      pageLoadTime: loadTimeMetric?.value || 0,
      apiCallCount: apiTotalCount,
      apiSuccessRate: apiTotalCount > 0 ? (apiSuccessCount / apiTotalCount) * 100 : 100,
      renderTime: renderTimeMetric?.value || 0,
      errorCount: this.metrics.filter(m => m.metricType === 'error').length,
      caseActionCount: this.metrics.filter(m => m.metricType === 'user_action').length,
    };
  }

  /**
   * Get session statistics
   */
  getSessionStats() {
    return {
      ...this.sessionStats,
      casesViewed: this.sessionStats.casesViewed.size,
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
  getMetrics(): CaseMetric[] {
    return [...this.metrics];
  }

  /**
   * Clear metrics
   */
  clearMetrics(): void {
    this.metrics = [];
    this.performanceMarks.clear();
    this.sessionStats = {
      casesViewed: new Set(),
      casesCreated: 0,
      casesEdited: 0,
      statusChanges: 0,
      apiCalls: 0,
      errors: 0,
    };

    logger.debug('Cases metrics cleared', {
      component: 'CasesMetrics',
      action: 'clearMetrics',
    });
  }

  /**
   * Export metrics for analysis
   */
  exportMetrics(): string {
    return JSON.stringify({
      metrics: this.metrics,
      sessionStats: this.getSessionStats(),
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
  private addMetric(metric: CaseMetric): void {
    this.metrics.push(metric);

    // Keep only last N metrics (circular buffer)
    if (this.metrics.length > this.maxMetricsSize) {
      this.metrics.shift();
    }

    // Store in localStorage for persistence (production)
    if (typeof window !== 'undefined' && process.env.NODE_ENV === 'production') {
      try {
        const storedMetrics = localStorage.getItem('cases_metrics');
        const metrics = storedMetrics ? JSON.parse(storedMetrics) : [];
        metrics.push(metric);

        // Keep only last 200 metrics in localStorage
        if (metrics.length > 200) {
          metrics.shift();
        }

        localStorage.setItem('cases_metrics', JSON.stringify(metrics));
      } catch (error) {
        logger.error('Failed to store cases metrics in localStorage', {
          component: 'CasesMetrics',
          action: 'addMetric',
        }, error instanceof Error ? error : new Error(String(error)));
      }
    }
  }
}

// Singleton instance
export const casesMetrics = new CasesMetricsCollector();

// Export type
export type { CasesMetricsCollector };
