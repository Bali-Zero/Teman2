/**
 * Safe fetch wrapper with error handling, timeout, and typed responses.
 *
 * Use this for server-side fetch calls (API routes, server components)
 * where ApiClientBase is not available. For client-side calls,
 * prefer ApiClientBase.request() which includes auth token management.
 *
 * @example
 * const { data, error } = await safeFetch<MyType>("/api/channels/health");
 * if (error) { console.error(error); return; }
 * // data is typed as MyType
 */

import { logger } from '@/lib/logger';

export interface SafeFetchResult<T> {
  data: T | null;
  error: string | null;
  status: number;
}

interface SafeFetchOptions extends RequestInit {
  timeoutMs?: number;
}

export async function safeFetch<T>(
  url: string,
  options: SafeFetchOptions = {}
): Promise<SafeFetchResult<T>> {
  const { timeoutMs = 30000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorBody = await response.text().catch(() => '');
      let errorMessage: string;
      try {
        const parsed = JSON.parse(errorBody);
        errorMessage = parsed.detail || parsed.message || `HTTP ${response.status}`;
      } catch {
        errorMessage = errorBody || `HTTP ${response.status} ${response.statusText}`;
      }

      logger.warn(`safeFetch error: ${response.status} ${url}`, {
        component: 'safeFetch',
        action: 'http_error',
        metadata: { url, status: response.status, error: errorMessage },
      });

      return { data: null, error: errorMessage, status: response.status };
    }

    // Handle empty responses
    const contentType = response.headers.get('content-type');
    if (response.status === 204 || !contentType?.includes('application/json')) {
      return { data: {} as T, error: null, status: response.status };
    }

    const data = (await response.json()) as T;
    return { data, error: null, status: response.status };
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      return { data: null, error: 'Request timeout', status: 0 };
    }
    const message = err instanceof Error ? err.message : String(err);
    logger.error(`safeFetch exception: ${url}`, {
      component: 'safeFetch',
      action: 'exception',
      metadata: { url, error: message },
    });
    return { data: null, error: message, status: 0 };
  } finally {
    clearTimeout(timeoutId);
  }
}
