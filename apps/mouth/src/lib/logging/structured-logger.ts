/**
 * Structured Logger for client-side logging
 */

export enum LogCategory {
  MEMORY = 'memory',
  CHAT = 'chat',
  AUTH = 'auth',
  API = 'api',
  UI = 'ui',
  WEBSOCKET = 'websocket',
  GENERAL = 'general',
}

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  [key: string]: unknown;
}

const isDev = process.env.NODE_ENV === 'development';

function formatLog(level: LogLevel, category: LogCategory, message: string, context?: LogContext): string {
  const timestamp = new Date().toISOString();
  const contextStr = context ? ` ${JSON.stringify(context)}` : '';
  return `[${timestamp}] [${level.toUpperCase()}] [${category}] ${message}${contextStr}`;
}

export function logDebug(category: LogCategory, message: string, context?: LogContext): void {
  if (isDev) {
    console.debug(formatLog('debug', category, message, context));
  }
}

export function logInfo(category: LogCategory, message: string, context?: LogContext): void {
  if (isDev) {
    console.info(formatLog('info', category, message, context));
  }
}

export function logWarn(category: LogCategory, message: string, context?: LogContext): void {
  console.warn(formatLog('warn', category, message, context));
}

export function logError(category: LogCategory, message: string, context?: LogContext): void {
  console.error(formatLog('error', category, message, context));
}
