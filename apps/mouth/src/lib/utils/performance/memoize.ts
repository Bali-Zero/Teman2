/**
 * Memoization Utilities
 *
 * Cache function results based on arguments
 */

/**
 * Simple memoize for sync functions
 */
export function memoize<T extends (...args: unknown[]) => unknown>(
  func: T,
  keyGenerator?: (...args: Parameters<T>) => string,
): T {
  const cache = new Map<string, ReturnType<T>>();

  return function (...args: Parameters<T>): ReturnType<T> {
    const key = keyGenerator ? keyGenerator(...args) : JSON.stringify(args);

    if (cache.has(key)) {
      return cache.get(key) as ReturnType<T>;
    }

    const result = func(...args) as ReturnType<T>;
    cache.set(key, result);
    return result;
  } as T;
}

/**
 * Memoize with TTL (time to live)
 */
export function memoizeWithTTL<T extends (...args: unknown[]) => unknown>(
  func: T,
  ttlMs: number,
  keyGenerator?: (...args: Parameters<T>) => string,
): T {
  const cache = new Map<string, { value: ReturnType<T>; expires: number }>();

  return function (...args: Parameters<T>): ReturnType<T> {
    const key = keyGenerator ? keyGenerator(...args) : JSON.stringify(args);

    const cached = cache.get(key);
    const now = Date.now();

    if (cached && cached.expires > now) {
      return cached.value;
    }

    const result = func(...args) as ReturnType<T>;
    cache.set(key, { value: result, expires: now + ttlMs });
    return result;
  } as T;
}

/**
 * Clearable memoize - returns function with clearCache method
 */
export function createMemoize<T extends (...args: unknown[]) => unknown>(
  func: T,
  keyGenerator?: (...args: Parameters<T>) => string,
): T & { clearCache: () => void } {
  const cache = new Map<string, ReturnType<T>>();

  const memoized = function (...args: Parameters<T>): ReturnType<T> {
    const key = keyGenerator ? keyGenerator(...args) : JSON.stringify(args);

    if (cache.has(key)) {
      return cache.get(key) as ReturnType<T>;
    }

    const result = func(...args) as ReturnType<T>;
    cache.set(key, result);
    return result;
  } as T & { clearCache: () => void };

  memoized.clearCache = () => {
    cache.clear();
  };

  return memoized;
}
