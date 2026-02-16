/**
 * Console Utilities
 *
 * Safe logging that strips in production
 */

const isProduction = process.env.NODE_ENV === "production";

/**
 * Safe console log - stripped in production
 */
export function debug(...args: unknown[]): void {
  if (!isProduction) {
    // eslint-disable-next-line no-console
    console.log("[DEBUG]", ...args);
  }
}

/**
 * Safe console warn - stripped in production
 */
export function warn(...args: unknown[]): void {
  if (!isProduction) {
    // eslint-disable-next-line no-console
    console.warn("[WARN]", ...args);
  }
}

/**
 * Safe console error - always shown but with prefix
 */
export function error(...args: unknown[]): void {
  // eslint-disable-next-line no-console
  console.error("[ERROR]", ...args);
}

/**
 * Create a namespaced logger
 */
export function createLogger(namespace: string) {
  return {
    debug: (...args: unknown[]) => {
      if (!isProduction) {
        // eslint-disable-next-line no-console
        console.log(`[${namespace}]`, ...args);
      }
    },
    warn: (...args: unknown[]) => {
      if (!isProduction) {
        // eslint-disable-next-line no-console
        console.warn(`[${namespace}]`, ...args);
      }
    },
    error: (...args: unknown[]) => {
      // eslint-disable-next-line no-console
      console.error(`[${namespace}]`, ...args);
    },
  };
}

/**
 * Strip all console methods in production
 * Call this in app initialization
 */
export function stripConsoleInProduction(): void {
  if (isProduction && typeof window !== "undefined") {
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    const noop = () => {};

    // Preserve error but remove others
    const originalError = console.error;

    console.log = noop;
    console.warn = noop;
    console.debug = noop;
    console.info = noop;

    // Keep error but prefix it
    console.error = (...args: unknown[]) => {
      originalError("[App Error]", ...args);
    };
  }
}
