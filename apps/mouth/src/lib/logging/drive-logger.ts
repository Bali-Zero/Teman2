/**
 * Structured Logging for Drive/Documents Page
 *
 * Provides comprehensive logging for all drive-related operations including:
 * - User actions (navigation, selection, file operations)
 * - API calls (file listing, prefetch, delete)
 * - State changes (view mode, selection, folder navigation)
 * - Performance metrics (load times, prefetch times, navigation)
 * - Error tracking with full context
 */

import { logger } from '@/lib/logger';

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
  KEYBOARD = 'KEYBOARD',
  PREFETCH = 'PREFETCH',
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
  [key: string]: string | number | boolean | null | undefined | Record<string, unknown> | unknown[];
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

class DriveLogger {
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

    let sessionId = sessionStorage.getItem('drive_session_id');
    if (!sessionId) {
      sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      sessionStorage.setItem('drive_session_id', sessionId);
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
      fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logData),
      }).catch((err) => logger.error('Failed to send log', { metadata: { error: String(err) } }));
    }

    if (this.isDevelopment) {
      const emoji = this.getLogEmoji(logData.category);
      const message = `${emoji} [${logData.category}] ${logData.message}`;

      switch (logData.level) {
        case LogLevel.DEBUG:
          logger.debug(message, { metadata: logData.metadata as Record<string, string | number | boolean | null | undefined> });
          break;
        case LogLevel.INFO:
          logger.info(message, { metadata: logData.metadata as Record<string, string | number | boolean | null | undefined> });
          break;
        case LogLevel.WARN:
          logger.warn(message, { metadata: logData.metadata as Record<string, string | number | boolean | null | undefined> });
          break;
        case LogLevel.ERROR:
          logger.error(message, { metadata: logData.metadata as Record<string, string | number | boolean | null | undefined> });
          break;
      }
    }
  }

  private getLogEmoji(category: LogCategory): string {
    switch (category) {
      case LogCategory.USER_ACTION:
        return '👤';
      case LogCategory.API_CALL:
        return '🌐';
      case LogCategory.STATE_CHANGE:
        return '🔄';
      case LogCategory.PERFORMANCE:
        return '⚡';
      case LogCategory.ERROR:
        return '❌';
      case LogCategory.KEYBOARD:
        return '⌨️';
      case LogCategory.PREFETCH:
        return '🚀';
      default:
        return '📋';
    }
  }

  // ===== USER ACTIONS =====

  logFileSelected(fileId: string, fileName: string, isMultiSelect: boolean) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'File selected', {
      fileId,
      fileName,
      isMultiSelect,
      action: 'file_selected',
    });
    this.sendToLoggingService(logData);
  }

  logFileDeselected(fileId: string, fileName: string) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'File deselected', {
      fileId,
      fileName,
      action: 'file_deselected',
    });
    this.sendToLoggingService(logData);
  }

  logFileOpened(fileId: string, fileName: string, isFolder: boolean) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      isFolder ? 'Folder opened' : 'File opened',
      {
        fileId,
        fileName,
        isFolder,
        action: isFolder ? 'folder_opened' : 'file_opened',
      }
    );
    this.sendToLoggingService(logData);
  }

  logFileDeleted(fileIds: string[], fileNames: string[]) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'Files deleted', {
      fileIds,
      fileNames,
      count: fileIds.length,
      action: 'files_deleted',
    });
    this.sendToLoggingService(logData);
  }

  logFileDownloaded(fileId: string, fileName: string) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'File downloaded', {
      fileId,
      fileName,
      action: 'file_downloaded',
    });
    this.sendToLoggingService(logData);
  }

  logFilePreviewed(fileId: string, fileName: string, mimeType: string) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'File previewed', {
      fileId,
      fileName,
      mimeType,
      action: 'file_previewed',
    });
    this.sendToLoggingService(logData);
  }

  logSelectAll(fileCount: number) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'All files selected', {
      fileCount,
      action: 'select_all',
    });
    this.sendToLoggingService(logData);
  }

  logClearSelection(previousCount: number) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'Selection cleared', {
      previousCount,
      action: 'clear_selection',
    });
    this.sendToLoggingService(logData);
  }

  logViewModeChange(oldMode: 'grid' | 'list', newMode: 'grid' | 'list') {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'View mode changed', {
      oldMode,
      newMode,
      action: 'view_mode_change',
    });
    this.sendToLoggingService(logData);
  }

  logInfoPanelToggle(isOpen: boolean) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      isOpen ? 'Info panel opened' : 'Info panel closed',
      {
        isOpen,
        action: 'info_panel_toggle',
      }
    );
    this.sendToLoggingService(logData);
  }

  logNewButtonClicked() {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'New button clicked', {
      action: 'new_button_clicked',
    });
    this.sendToLoggingService(logData);
  }

  logUploadButtonClicked() {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.USER_ACTION,
      'Upload button clicked',
      {
        action: 'upload_button_clicked',
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== NAVIGATION =====

  logFolderNavigation(folderId: string | null, folderName: string, fromBreadcrumb: boolean) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'Navigated to folder', {
      folderId,
      folderName,
      fromBreadcrumb,
      action: 'folder_navigation',
    });
    this.sendToLoggingService(logData);
  }

  logBreadcrumbClick(folderId: string | null, folderName: string, depth: number) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'Breadcrumb clicked', {
      folderId,
      folderName,
      depth,
      action: 'breadcrumb_click',
    });
    this.sendToLoggingService(logData);
  }

  logSidebarNavigation(view: string) {
    const logData = this.formatLog(LogLevel.INFO, LogCategory.USER_ACTION, 'Sidebar navigation', {
      view,
      action: 'sidebar_navigation',
    });
    this.sendToLoggingService(logData);
  }

  // ===== KEYBOARD =====

  logKeyboardShortcut(
    key: string,
    action: string,
    modifiers: { shift?: boolean; ctrl?: boolean; meta?: boolean }
  ) {
    const logData = this.formatLog(LogLevel.DEBUG, LogCategory.KEYBOARD, 'Keyboard shortcut used', {
      key,
      action,
      modifiers,
    });
    this.sendToLoggingService(logData);
  }

  logKeyboardNavigation(direction: 'up' | 'down' | 'left' | 'right', newIndex: number) {
    const logData = this.formatLog(LogLevel.DEBUG, LogCategory.KEYBOARD, 'Keyboard navigation', {
      direction,
      newIndex,
    });
    this.sendToLoggingService(logData);
  }

  // ===== PREFETCH =====

  logPrefetchStarted(folderId: string) {
    const logData = this.formatLog(LogLevel.DEBUG, LogCategory.PREFETCH, 'Prefetch started', {
      folderId,
      action: 'prefetch_started',
    });
    this.sendToLoggingService(logData);
  }

  logPrefetchCompleted(folderId: string, duration: number, fileCount: number) {
    const logData = this.formatLog(LogLevel.DEBUG, LogCategory.PREFETCH, 'Prefetch completed', {
      folderId,
      duration,
      fileCount,
      action: 'prefetch_completed',
    });
    this.sendToLoggingService(logData);
  }

  logPrefetchSkipped(folderId: string, reason: 'cached' | 'in_progress') {
    const logData = this.formatLog(LogLevel.DEBUG, LogCategory.PREFETCH, 'Prefetch skipped', {
      folderId,
      reason,
      action: 'prefetch_skipped',
    });
    this.sendToLoggingService(logData);
  }

  logPrefetchError(folderId: string, error: Error) {
    const logData = this.formatLog(LogLevel.WARN, LogCategory.PREFETCH, 'Prefetch failed', {
      folderId,
      error: {
        name: error.name,
        message: error.message,
      },
      action: 'prefetch_error',
    });
    this.sendToLoggingService(logData);
  }

  // ===== API CALLS =====

  logApiRequest(endpoint: string, method: string, params?: Record<string, unknown>) {
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

  logFilesLoaded(count: number, folderId: string | null, duration: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.STATE_CHANGE,
      'Files loaded successfully',
      {
        count,
        folderId,
        duration,
        event: 'files_loaded',
      }
    );
    this.sendToLoggingService(logData);
  }

  logFilesLoadFailed(folderId: string | null, error: Error, duration: number) {
    const logData = this.formatLog(
      LogLevel.ERROR,
      LogCategory.STATE_CHANGE,
      'Failed to load files',
      {
        folderId,
        duration,
        error: {
          name: error.name,
          message: error.message,
          stack: error.stack,
        },
        event: 'files_load_failed',
      }
    );
    this.sendToLoggingService(logData);
  }

  logSelectionChange(selectedCount: number, totalFiles: number) {
    const logData = this.formatLog(LogLevel.DEBUG, LogCategory.STATE_CHANGE, 'Selection changed', {
      selectedCount,
      totalFiles,
      event: 'selection_change',
    });
    this.sendToLoggingService(logData);
  }

  // ===== PERFORMANCE =====

  logPageLoad(duration: number) {
    const logData = this.formatLog(
      LogLevel.INFO,
      LogCategory.PERFORMANCE,
      'Documents page loaded',
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

  logNavigationPerformance(folderId: string | null, duration: number, fileCount: number) {
    const logData = this.formatLog(
      LogLevel.DEBUG,
      LogCategory.PERFORMANCE,
      'Folder navigation completed',
      {
        folderId,
        duration,
        fileCount,
        metric: 'navigation_performance',
      }
    );
    this.sendToLoggingService(logData);
  }

  // ===== ERRORS =====

  logError(message: string, error: Error, context?: LogMetadata) {
    const logData = this.formatLog(LogLevel.ERROR, LogCategory.ERROR, message, {
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack,
      },
      ...context,
    });
    this.sendToLoggingService(logData);
  }

  logWarning(message: string, context?: LogMetadata) {
    const logData = this.formatLog(LogLevel.WARN, LogCategory.ERROR, message, context);
    this.sendToLoggingService(logData);
  }

  logComponentError(
    componentName: string,
    error: Error,
    errorInfo?: { componentStack?: string }
  ): void {
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
      logger.debug(`📁 ${message}`, { metadata: metadata as Record<string, string | number | boolean | null | undefined> | undefined });
    }
  }
}

// Export singleton instance
export const driveLogger = new DriveLogger();

// Export convenience methods
export const {
  setUser,
  logFileSelected,
  logFileDeselected,
  logFileOpened,
  logFileDeleted,
  logFileDownloaded,
  logFilePreviewed,
  logSelectAll,
  logClearSelection,
  logViewModeChange,
  logInfoPanelToggle,
  logNewButtonClicked,
  logUploadButtonClicked,
  logFolderNavigation,
  logBreadcrumbClick,
  logSidebarNavigation,
  logKeyboardShortcut,
  logKeyboardNavigation,
  logPrefetchStarted,
  logPrefetchCompleted,
  logPrefetchSkipped,
  logPrefetchError,
  logApiRequest,
  logApiSuccess,
  logApiError,
  logFilesLoaded,
  logFilesLoadFailed,
  logSelectionChange,
  logPageLoad,
  logRenderTime,
  logNavigationPerformance,
  logError,
  logWarning,
  logComponentError,
  startTimer,
  debug,
} = driveLogger;
