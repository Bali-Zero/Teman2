/**
 * Comprehensive Logging Utility with Sentry Integration
 * Provides structured logging for Intelligence Center and all frontend components
 * Sends errors and warnings to Sentry in production
 */

import * as Sentry from "@sentry/nextjs";
import { debug, warn, error as logError } from "@/lib/utils/console";
import type { Metadata } from "./types/common";

export enum LogLevel {
  DEBUG = "DEBUG",
  INFO = "INFO",
  WARN = "WARN",
  ERROR = "ERROR",
}

export interface LogContext {
  component?: string;
  action?: string;
  user?: string;
  itemId?: string;
  itemType?: "visa" | "news" | "all";
  code?: number | string;
  reason?: string;
  note?: string;
  metadata?: Metadata;
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
    this.isDevelopment = process.env.NODE_ENV === "development";
  }

  private createEntry(
    level: LogLevel,
    message: string,
    context: LogContext = {},
    error?: Error,
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
    const time = new Date(timestamp).toLocaleTimeString("en-US");
    const emoji = this.getLevelEmoji(level);

    const contextStr = Object.keys(context).length
      ? ` [${Object.entries(context)
          .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
          .join(", ")}]`
      : "";

    const logMessage = `${emoji} ${time} [${level}] ${message}${contextStr}`;

    switch (level) {
      case LogLevel.DEBUG:
        debug(logMessage);
        break;
      case LogLevel.INFO:
        // eslint-disable-next-line no-console
        console.info(logMessage);
        break;
      case LogLevel.WARN:
        warn(logMessage);
        break;
      case LogLevel.ERROR:
        logError(logMessage);
        if (error) {
          logError("Error details:", error);
        }
        if (stack) {
          logError("Stack trace:", stack);
        }
        break;
    }
  }

  private getLevelEmoji(level: LogLevel): string {
    switch (level) {
      case LogLevel.DEBUG:
        return "🔍";
      case LogLevel.INFO:
        return "ℹ️";
      case LogLevel.WARN:
        return "⚠️";
      case LogLevel.ERROR:
        return "❌";
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

    // Send warnings to Sentry in production
    if (!this.isDevelopment) {
      this.sendToSentry(entry);
    }
  }

  error(message: string, context: LogContext = {}, error?: Error): void {
    const entry = this.createEntry(LogLevel.ERROR, message, context, error);
    this.formatConsoleOutput(entry);

    // Send errors to Sentry in production
    if (!this.isDevelopment) {
      this.sendToSentry(entry);
      this.sendToRemoteLogger(entry); // Still keep local storage for backup
    }
  }

  /**
   * Send log entry to Sentry (production only)
   */
  private sendToSentry(entry: LogEntry): void {
    try {
      // Set context for Sentry
      if (entry.context && Object.keys(entry.context).length > 0) {
        Sentry.setContext("log_context", {
          component: entry.context.component,
          action: entry.context.action,
          user: entry.context.user,
          itemId: entry.context.itemId,
          itemType: entry.context.itemType,
          code: entry.context.code,
          reason: entry.context.reason,
          note: entry.context.note,
          metadata: entry.context.metadata,
        });
      }

      // Send to Sentry based on level
      if (entry.level === LogLevel.ERROR && entry.error) {
        // For errors with exception object, use captureException
        Sentry.captureException(entry.error, {
          extra: {
            message: entry.message,
            context: entry.context,
            timestamp: entry.timestamp,
          },
          tags: {
            component: entry.context.component || "unknown",
            action: entry.context.action || "unknown",
          },
        });
      } else if (
        entry.level === LogLevel.ERROR ||
        entry.level === LogLevel.WARN
      ) {
        // For errors/warnings without exception, use captureMessage
        Sentry.captureMessage(entry.message, {
          level: entry.level === LogLevel.ERROR ? "error" : "warning",
          extra: {
            context: entry.context,
            timestamp: entry.timestamp,
            stack: entry.stack,
          },
          tags: {
            component: entry.context.component || "unknown",
            action: entry.context.action || "unknown",
          },
        });
      }
    } catch (sentryError) {
      // Don't let Sentry errors break the application
      console.error("Failed to send to Sentry:", sentryError);
    }
  }

  /**
   * Store error logs in localStorage as backup (production only)
   */
  private async sendToRemoteLogger(entry: LogEntry): Promise<void> {
    try {
      if (typeof window === "undefined") return; // Skip on server-side

      const logs = localStorage.getItem("error_logs");
      const errorLogs = logs ? JSON.parse(logs) : [];
      errorLogs.push({
        timestamp: entry.timestamp,
        level: entry.level,
        message: entry.message,
        context: entry.context,
        error: entry.error ? entry.error.message : undefined,
        stack: entry.stack,
      });

      // Keep only last 50 errors
      if (errorLogs.length > 50) {
        errorLogs.shift();
      }

      localStorage.setItem("error_logs", JSON.stringify(errorLogs));
    } catch (e) {
      console.error("Failed to store error log:", e);
    }
  }

  getHistory(): LogEntry[] {
    return [...this.logHistory];
  }

  clearHistory(): void {
    this.logHistory = [];
  }

  /**
   * Set user context for Sentry (call on login)
   */
  setUser(userId: string, email?: string, username?: string): void {
    if (!this.isDevelopment) {
      Sentry.setUser({
        id: userId,
        email,
        username,
      });
    }
  }

  /**
   * Clear user context from Sentry (call on logout)
   */
  clearUser(): void {
    if (!this.isDevelopment) {
      Sentry.setUser(null);
    }
  }

  /**
   * Get stored error logs from localStorage
   */
  getStoredLogs(): unknown[] {
    if (typeof window === "undefined") return [];
    try {
      const logs = localStorage.getItem("error_logs");
      return logs ? JSON.parse(logs) : [];
    } catch {
      return [];
    }
  }

  /**
   * Clear stored error logs from localStorage
   */
  clearStoredLogs(): void {
    if (typeof window === "undefined") return;
    try {
      localStorage.removeItem("error_logs");
    } catch {
      // Ignore
    }
  }

  // Convenience methods for Intelligence Center specific logging
  apiCall(
    endpoint: string,
    method: string = "GET",
    context: LogContext = {},
  ): void {
    this.info(`API Call: ${method} ${endpoint}`, {
      ...context,
      action: "api_call",
      metadata: { endpoint, method },
    });
  }

  apiSuccess(
    endpoint: string,
    responseTime: number,
    context: LogContext = {},
  ): void {
    this.info(`API Success: ${endpoint}`, {
      ...context,
      action: "api_success",
      metadata: { endpoint, responseTime },
    });
  }

  apiError(endpoint: string, error: Error, context: LogContext = {}): void {
    this.error(
      `API Error: ${endpoint}`,
      {
        ...context,
        action: "api_error",
        metadata: { endpoint },
      },
      error,
    );
  }

  userAction(
    action: string,
    itemType?: "visa" | "news",
    itemId?: string,
    context: LogContext = {},
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
      action: "mount",
    });
  }

  componentUnmount(component: string, context: LogContext = {}): void {
    this.debug(`Component Unmounted: ${component}`, {
      ...context,
      component,
      action: "unmount",
    });
  }
}

// Singleton instance
export const logger = new Logger();

// Export type for external use
export type { Logger };
