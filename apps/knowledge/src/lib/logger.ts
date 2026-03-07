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
  metadata?: Record<string, unknown>;
}

class Logger {
  private isDevelopment = process.env.NODE_ENV === "development";

  debug(message: string, _context: LogContext = {}): void {
    if (this.isDevelopment) console.debug(`[DEBUG] ${message}`);
  }

  info(message: string, _context: LogContext = {}): void {
    if (this.isDevelopment) console.info(`[INFO] ${message}`);
  }

  warn(message: string, _context: LogContext = {}, _error?: Error): void {
    console.warn(`[WARN] ${message}`);
  }

  error(message: string, _context: LogContext = {}, _error?: Error): void {
    console.error(`[ERROR] ${message}`);
  }

  componentMount(component: string, context: LogContext = {}): void {
    this.debug(`Component Mounted: ${component}`, context);
  }

  componentUnmount(component: string, context: LogContext = {}): void {
    this.debug(`Component Unmounted: ${component}`, context);
  }

  userAction(
    action: string,
    _itemType?: string,
    _itemId?: string,
    context: LogContext = {},
  ): void {
    this.info(`User Action: ${action}`, context);
  }
}

export const logger = new Logger();
