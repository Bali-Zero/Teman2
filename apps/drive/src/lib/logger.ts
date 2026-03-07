/* eslint-disable no-console */
export enum LogLevel {
  DEBUG = "DEBUG",
  INFO = "INFO",
  WARN = "WARN",
  ERROR = "ERROR",
}

export interface LogContext {
  component?: string;
  action?: string;
  metadata?: Record<string, string | number | boolean | null | undefined>;
}

class Logger {
  private isDevelopment = process.env.NODE_ENV === "development";

  debug(message: string, context: LogContext = {}): void {
    if (!this.isDevelopment) return;
    console.debug(`🔍 [DEBUG] ${message}`, context);
  }

  info(message: string, context: LogContext = {}): void {
    console.info(`ℹ️ [INFO] ${message}`, context);
  }

  warn(message: string, context: LogContext = {}, error?: Error): void {
    console.warn(`⚠️ [WARN] ${message}`, context, error);
  }

  error(message: string, context: LogContext = {}, error?: Error): void {
    console.error(`❌ [ERROR] ${message}`, context, error);
  }
}

export const logger = new Logger();
export type { Logger };
