/**
 * Structured Logging for Cases Page
 *
 * Provides comprehensive logging for all case-related operations including:
 * - User actions (clicks, searches, filters)
 * - API calls (requests, responses, errors)
 * - State changes (status updates, view mode changes)
 * - Performance metrics (load times, render times)
 * - Error tracking with full context
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR',
}

export enum LogCategory {
  USER_ACTION = 'USER_ACTION',
  API_CALL = 'API_CALL',
  STATE_CHANGE = 'STATE_CHANGE',
  PERFORMANCE = 'PERFORMANCE',
  ERROR = 'ERROR',
}

interface LogContext {
  userId?: string;
  userEmail?: string;
  sessionId?: string;
  pageUrl?: string;
  userAgent?: string;
  timestamp: string;
  category: LogCategory;
  level: LogLevel;
}

interface LogMetadata {
  [key: string]: any;
}

interface LogData {
  level: LogLevel;
  category: LogCategory;
  message: string;
  metadata: LogMetadata;
  timestamp: string;
  userId?: string;
  userEmail?: string;
  sessionId?: string;
  pageUrl?: string;
  userAgent?: string;
}

class CasesLogger {
  private context: Partial<LogContext> = {};
  private isProduction = process.env.NODE_ENV === 'production';
  private isDevelopment = process.env.NODE_ENV === 'development';

  constructor() {
    this.initializeContext();
  }

  private initializeContext() {
    if (typeof window !== 'undefined') {
      this.context = {
        pageUrl: window.location.href,
        userAgent: window.navigator.userAgent,
        sessionId: this.getOrCreateSessionId(),
      };
    }
  }

  private getOrCreateSessionId(): string {
    if (typeof window === 'undefined') return '';

    let sessionId = sessionStorage.getItem('cases_session_id');
    if (!sessionId) {
      sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      sessionStorage.setItem('cases_session_id', sessionId);
    }
    return sessionId;
  }

  setUser(userId: string, userEmail: string) {
    this.context.userId = userId;
    this.context.userEmail = userEmail;
  }

  private formatLog(
    level: LogLevel,
    category: LogCategory,
    message: string,
    metadata?: LogMetadata
  ): LogData {
    return {
      ...this.context,
      timestamp: new Date().toISOString(),
      level,
      category,
      message,
      metadata: metadata || {},
    };
  }

  private sendToLoggingService(logData: LogData) {
    if (this.isProduction) {
      // Send to external logging service (e.g., Sentry, LogRocket, etc.)
      // Example: Sentry.captureMessage(JSON.stringify(logData));

      // For now, send to our backend
      fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logData),
      }).catch(err => console.error('Failed to send log:', err));
    }

    if (this.isDevelopment) {
      // Pretty print in development
      console.log(`[${logData.level}] [${logData.category}]`, logData.message, logData.metadata || '');
    }
  }

  // ===== USER ACTIONS =====

  logSearch(query: string, resultCount: number, duration: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User performed search',
      {
        query,
        resultCount,
        duration,
        action: 'search',
      }
    );
    this.sendToLoggingService(logData);
  }

  logFilterApplied(filterType: string, filterValue: string, resultCount: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User applied filter',
      {
        filterType,
        filterValue,
        resultCount,
        action: 'filter_applied',
      }
    );
    this.sendToLoggingService(logData);
  }

  logFilterRemoved(filterType: string) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User removed filter',
      {
        filterType,
        action: 'filter_removed',
      }
    );
    this.sendToLoggingService(logData);
  }

  logViewModeChange(oldMode: string, newMode: string) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User changed view mode',
      {
        oldMode,
        newMode,
        action: 'view_mode_change',
      }
    );
    this.sendToLoggingService(logData);
  }

  logSortApplied(field: string, order: string) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User applied sort',
      {
        field,
        order,
        action: 'sort_applied',
      }
    );
    this.sendToLoggingService(logData);
  }

  logCaseClicked(caseId: number, caseType: string) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User clicked on case',
      {
        caseId,
        caseType,
        action: 'case_clicked',
      }
    );
    this.sendToLoggingService(logData);
  }

  logNewCaseButtonClicked() {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User clicked "+ New Case" button',
      {
        action: 'new_case_clicked',
      }
    );
    this.sendToLoggingService(logData);
  }

  logPaginationChange(page: number, itemsPerPage: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'User changed page',
      {
        page,
        itemsPerPage,
        action: 'pagination_change',
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== API CALLS =====

  logApiRequest(endpoint: string, method: string, params?: any) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.API_CALL,
      `API request: ${method} ${endpoint}`,
      {
        endpoint,
        method,
        params,
        requestType: 'outgoing',
      }
    );
    this.sendToLoggingService(logData);
  }

  logApiSuccess(endpoint: string, method: string, duration: number, resultSize?: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.API_CALL,
      `API success: ${method} ${endpoint}`,
      {
        endpoint,
        method,
        duration,
        resultSize,
        status: 'success',
      }
    );
    this.sendToLoggingService(logData);
  }

  logApiError(endpoint: string, method: string, error: Error, duration: number) {
    const logData = this.formatLog(
      LogLevel.ERROR,
      LogCategory.API_CALL,
      `API error: ${method} ${endpoint}`,
      {
        endpoint,
        method,
        duration,
        error: {
          name: error.name,
          message: error.message,
          stack: error.stack,
        },
        status: 'error',
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== STATE CHANGES =====

  logCaseStatusChange(
    caseId: number,
    oldStatus: string,
    newStatus: string,
    success: boolean,
    error?: Error
  ) {
    const logData = this.formatLog(
      success ? LogLevel.INFO : LogLevel.ERROR,
      LogCategory.STATE_CHANGE,
      `Case status ${success ? 'changed' : 'change failed'}`,
      {
        caseId,
        oldStatus,
        newStatus,
        success,
        error: error ? {
          name: error.name,
          message: error.message,
        } : undefined,
      }
    );
    this.sendToLoggingService(logData);
  }

  logCasesLoaded(count: number, duration: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.STATE_CHANGE,
      'Cases loaded successfully',
      {
        count,
        duration,
        event: 'cases_loaded',
      }
    );
    this.sendToLoggingService(logData);
  }

  logCasesLoadFailed(error: Error, duration: number) {
    const logData = this.formatLog(
      LogLevel.ERROR,
      LogCategory.STATE_CHANGE,
      'Failed to load cases',
      {
        duration,
        error: {
          name: error.name,
          message: error.message,
          stack: error.stack,
        },
        event: 'cases_load_failed',
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== PERFORMANCE =====

  logPageLoad(duration: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.PERFORMANCE,
      'Page loaded',
      {
        duration,
        metric: 'page_load',
      }
    );
    this.sendToLoggingService(logData);
  }

  logRenderTime(componentName: string, duration: number) {
    const logData = this.formatLog(
      LogLevel.DEBUG,
      LogCategory.PERFORMANCE,
      `Component rendered: ${componentName}`,
      {
        componentName,
        duration,
        metric: 'render_time',
      }
    );
    this.sendToLoggingService(logData);
  }

  logFilterPerformance(filterCount: number, resultCount: number, duration: number) {
    const logData = this.formatLog(
      LogLevel.DEBUG,
      LogCategory.PERFORMANCE,
      'Filter operation completed',
      {
        filterCount,
        resultCount,
        duration,
        metric: 'filter_performance',
      }
    );
    this.sendToLoggingService(logData);
  }

  logSearchPerformance(query: string, resultCount: number, duration: number) {
    const logData = this.formatLog(
      LogLevel.DEBUG,
      LogCategory.PERFORMANCE,
      'Search operation completed',
      {
        query,
        resultCount,
        duration,
        metric: 'search_performance',
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== ERRORS =====

  logError(message: string, error: Error, context?: LogMetadata) {
    const logData = this.formatLog(
      LogLevel.ERROR,
      LogCategory.ERROR,
      message,
      {
        error: {
          name: error.name,
          message: error.message,
          stack: error.stack,
        },
        ...context,
      }
    );
    this.sendToLoggingService(logData);
  }

  logWarning(message: string, context?: LogMetadata) {
    const logData = this.formatLog(
      LogLevel.WARN,
      LogCategory.ERROR,
      message,
      context
    );
    this.sendToLoggingService(logData);
  }

  logComponentError(componentName: string, error: Error, errorInfo?: any) {
    const logData = this.formatLog(
      LogLevel.ERROR,
      LogCategory.ERROR,
      `Component error in ${componentName}`,
      {
        componentName,
        error: {
          name: error.name,
          message: error.message,
          stack: error.stack,
        },
        errorInfo,
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== UTILITY METHODS =====

  startTimer(): () => number {
    const start = performance.now();
    return () => Math.round(performance.now() - start);
  }

  debug(message: string, metadata?: LogMetadata) {
    if (this.isDevelopment) {
      const logData = this.formatLog(LogLevel.DEBUG, LogCategory.USER_ACTION, message, metadata);
      console.log(`[DEBUG]`, message, metadata || '');
    }
  }
}

// Export singleton instance
export const casesLogger = new CasesLogger();

// Export convenience methods
export const {
  setUser,
  logSearch,
  logFilterApplied,
  logFilterRemoved,
  logViewModeChange,
  logSortApplied,
  logCaseClicked,
  logNewCaseButtonClicked,
  logPaginationChange,
  logApiRequest,
  logApiSuccess,
  logApiError,
  logCaseStatusChange,
  logCasesLoaded,
  logCasesLoadFailed,
  logPageLoad,
  logRenderTime,
  logFilterPerformance,
  logSearchPerformance,
  logError,
  logWarning,
  logComponentError,
  startTimer,
  debug,
} = casesLogger;
