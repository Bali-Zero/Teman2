/**
 * Comprehensive Logging Utility
 * Provides structured logging for Intelligence Center and all frontend components
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR',
}

export interface LogContext {
  component?: string;
  action?: string;
  user?: string;
  itemId?: string;
  itemType?: 'visa' | 'news' | 'all';
  metadata?: Record<string, any>;
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context: LogContext;
  error?: Error;
  stack?: string;
}

class Logger {
  private isDevelopment: boolean;
  private logHistory: LogEntry[] = [];
  private maxHistorySize = 100;

  constructor() {
    this.isDevelopment = process.env.NODE_ENV === 'development';
  }

  private createEntry(
    level: LogLevel,
    message: string,
    context: LogContext = {},
    error?: Error
  ): LogEntry {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
    };

    if (error) {
      entry.error = error;
      entry.stack = error.stack;
    }

    // Add to history (circular buffer)
    this.logHistory.push(entry);
    if (this.logHistory.length > this.maxHistorySize) {
      this.logHistory.shift();
    }

    return entry;
  }

  private formatConsoleOutput(entry: LogEntry): void {
    const { timestamp, level, message, context, error, stack } = entry;
    const time = new Date(timestamp).toLocaleTimeString();
    const emoji = this.getLevelEmoji(level);

    const contextStr = Object.keys(context).length
      ? ` [${Object.entries(context)
          .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
          .join(', ')}]`
      : '';

    const logMessage = `${emoji} ${time} [${level}] ${message}${contextStr}`;

    switch (level) {
      case LogLevel.DEBUG:
        console.debug(logMessage);
        break;
      case LogLevel.INFO:
        console.info(logMessage);
        break;
      case LogLevel.WARN:
        console.warn(logMessage);
        break;
      case LogLevel.ERROR:
        console.error(logMessage);
        if (error) {
          console.error('Error details:', error);
        }
        if (stack) {
          console.error('Stack trace:', stack);
        }
        break;
    }
  }

  private getLevelEmoji(level: LogLevel): string {
    switch (level) {
      case LogLevel.DEBUG:
        return '🔍';
      case LogLevel.INFO:
        return 'ℹ️';
      case LogLevel.WARN:
        return '⚠️';
      case LogLevel.ERROR:
        return '❌';
    }
  }

  debug(message: string, context: LogContext = {}): void {
    if (!this.isDevelopment) return; // Skip debug logs in production
    const entry = this.createEntry(LogLevel.DEBUG, message, context);
    this.formatConsoleOutput(entry);
  }

  info(message: string, context: LogContext = {}): void {
    const entry = this.createEntry(LogLevel.INFO, message, context);
    this.formatConsoleOutput(entry);
  }

  warn(message: string, context: LogContext = {}, error?: Error): void {
    const entry = this.createEntry(LogLevel.WARN, message, context, error);
    this.formatConsoleOutput(entry);
  }

  error(message: string, context: LogContext = {}, error?: Error): void {
    const entry = this.createEntry(LogLevel.ERROR, message, context, error);
    this.formatConsoleOutput(entry);

    // In production, you could send to a logging service here
    if (!this.isDevelopment) {
      this.sendToRemoteLogger(entry);
    }
  }

  private async sendToRemoteLogger(entry: LogEntry): Promise<void> {
    // TODO: Implement remote logging service integration
    // Examples: Sentry, LogRocket, DataDog, etc.
    // For now, just store in localStorage for debugging
    try {
      const logs = localStorage.getItem('error_logs');
      const errorLogs = logs ? JSON.parse(logs) : [];
      errorLogs.push(entry);

      // Keep only last 50 errors
      if (errorLogs.length > 50) {
        errorLogs.shift();
      }

      localStorage.setItem('error_logs', JSON.stringify(errorLogs));
    } catch (e) {
      console.error('Failed to store error log:', e);
    }
  }

  getHistory(): LogEntry[] {
    return [...this.logHistory];
  }

  clearHistory(): void {
    this.logHistory = [];
  }

  // Convenience methods for Intelligence Center specific logging
  apiCall(
    endpoint: string,
    method: string = 'GET',
    context: LogContext = {}
  ): void {
    this.info(`API Call: ${method} ${endpoint}`, {
      ...context,
      action: 'api_call',
      metadata: { endpoint, method },
    });
  }

  apiSuccess(
    endpoint: string,
    responseTime: number,
    context: LogContext = {}
  ): void {
    this.info(`API Success: ${endpoint}`, {
      ...context,
      action: 'api_success',
      metadata: { endpoint, responseTime },
    });
  }

  apiError(
    endpoint: string,
    error: Error,
    context: LogContext = {}
  ): void {
    this.error(`API Error: ${endpoint}`, {
      ...context,
      action: 'api_error',
      metadata: { endpoint },
    }, error);
  }

  userAction(
    action: string,
    itemType?: 'visa' | 'news',
    itemId?: string,
    context: LogContext = {}
  ): void {
    this.info(`User Action: ${action}`, {
      ...context,
      action,
      itemType,
      itemId,
    });
  }

  componentMount(component: string, context: LogContext = {}): void {
    this.debug(`Component Mounted: ${component}`, {
      ...context,
      component,
      action: 'mount',
    });
  }

  componentUnmount(component: string, context: LogContext = {}): void {
    this.debug(`Component Unmounted: ${component}`, {
      ...context,
      component,
      action: 'unmount',
    });
  }
}

// Singleton instance
export const logger = new Logger();

// Export type for external use
export type { Logger };
