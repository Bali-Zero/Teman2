/**
 * Secure Logger for Admin Dashboard
 * Strips logs in production
 */

const isProduction = process.env.NODE_ENV === "production";

/**
 * Development-only log
 */
export function debug(message: string, ...args: unknown[]): void {
  if (!isProduction) {
    // eslint-disable-next-line no-console
    console.log(`[INFO] ${message}`, ...args);
  }
}

/**
 * Development-only warning
 */
export function warn(message: string, ...args: unknown[]): void {
  if (!isProduction) {
    // eslint-disable-next-line no-console
    console.warn(`[WARN] ${message}`, ...args);
  }
}

/**
 * Always log errors
 */
export function error(message: string, ...args: unknown[]): void {
  // eslint-disable-next-line no-console
  console.error(`[ERROR] ${message}`, ...args);
}

/**
 * Create namespaced logger
 */
export function createLogger(namespace: string) {
  return {
    debug: (msg: string, ...args: unknown[]) =>
      debug(`[${namespace}] ${msg}`, ...args),
    warn: (msg: string, ...args: unknown[]) =>
      warn(`[${namespace}] ${msg}`, ...args),
    error: (msg: string, ...args: unknown[]) =>
      error(`[${namespace}] ${msg}`, ...args),
  };
}

/**
 * Aggregated logger object — stable surface for `import { logger } from "@/lib/logger"`.
 * Used by API route handlers under `app/api/**` (kg, legal, postgres, qdrant, rag).
 */
export const logger = {
  debug,
  warn,
  error,
};

/**
 * Strip console in production
 */
export function stripConsoleInProduction(): void {
  if (isProduction && typeof window !== "undefined") {
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    const noop = () => {};
    console.log = noop;
    console.debug = noop;
    console.info = noop;
    console.warn = noop;
    // Keep error but with prefix
    const originalError = console.error;
    console.error = (...args: unknown[]) => {
      originalError("[Dashboard Error]", ...args);
    };
  }
}
