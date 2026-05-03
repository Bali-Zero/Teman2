/**
 * Streaming retry utilities — exponential backoff for SSE connection establishment.
 *
 * Retries ONLY the initial fetch handshake on classified network errors.
 * Mid-stream drops are surfaced to the caller so the UI can offer a retry button
 * (resuming partial state requires backend support; see TODO below).
 *
 * TODO(backend-resume-token): once the RAG backend emits `X-Stream-Resume-Token`
 * with per-chunk checkpoints (see apps/mouth/docs/issues/backend-resume-token-DRAFT.md),
 * extend this module to send the token on retry and skip already-delivered chunks
 * instead of restarting the whole turn.
 */

export type StreamErrorClass =
  | 'network' // fetch failed before any byte: DNS, connection refused, TLS, offline
  | 'abort' // user/page abort via AbortController — never retry
  | 'http' // server returned non-2xx — surface to caller, no blind retry
  | 'timeout' // idle/total timeout in caller — caller decides
  | 'parse' // SSE decode failed — likely upstream bug, no retry
  | 'unknown';

export interface RetryConfig {
  maxRetries: number;
  baseDelayMs: number;
  /** Multiplier applied to baseDelayMs each attempt: delay = base * factor^(attempt-1). */
  factor: number;
  /** Cap so a misconfigured factor cannot stall indefinitely. */
  maxDelayMs: number;
}

export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelayMs: 500,
  factor: 2,
  maxDelayMs: 5_000,
};

export function classifyStreamError(error: unknown): StreamErrorClass {
  if (!(error instanceof Error)) return 'unknown';

  const name = error.name;
  const message = error.message || '';

  if (name === 'AbortError' || /aborted/i.test(message)) return 'abort';

  if (name === 'TypeError' && /fetch|network|load failed/i.test(message)) {
    return 'network';
  }

  if (/^HTTP \d{3}/.test(message)) return 'http';
  if (/timeout|timed out/i.test(message)) return 'timeout';
  if (/JSON|parse|unexpected token/i.test(message)) return 'parse';

  // navigator.onLine === false at throw time → treat as network
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return 'network';
  }

  return 'unknown';
}

export function computeBackoffDelay(
  attempt: number,
  config: RetryConfig = DEFAULT_RETRY_CONFIG
): number {
  if (attempt < 1) return 0;
  const raw = config.baseDelayMs * Math.pow(config.factor, attempt - 1);
  return Math.min(raw, config.maxDelayMs);
}

export interface RetryableFetchOptions {
  config?: Partial<RetryConfig>;
  signal?: AbortSignal;
  /** Called before each retry; useful for telemetry & UI banners. */
  onRetry?: (attempt: number, delayMs: number, error: Error) => void;
}

/**
 * Wrap an async operation with classified retry. Retries ONLY for class === "network".
 * Honors AbortSignal: an external abort short-circuits the loop with no further attempts.
 */
export async function retryableFetch<T>(
  fn: (attempt: number) => Promise<T>,
  options: RetryableFetchOptions = {}
): Promise<T> {
  const config: RetryConfig = { ...DEFAULT_RETRY_CONFIG, ...options.config };
  const signal = options.signal;

  let attempt = 0;
  let lastError: Error | undefined;

  while (attempt <= config.maxRetries) {
    if (signal?.aborted) {
      const abortErr = new Error('Request aborted');
      abortErr.name = 'AbortError';
      throw abortErr;
    }

    try {
      return await fn(attempt);
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      const cls = classifyStreamError(lastError);

      if (cls !== 'network' || attempt >= config.maxRetries) {
        throw lastError;
      }

      attempt += 1;
      const delay = computeBackoffDelay(attempt, config);
      options.onRetry?.(attempt, delay, lastError);

      await sleepWithAbort(delay, signal);
    }
  }

  // Unreachable, but keeps TS happy.
  throw lastError ?? new Error('retryableFetch exhausted without error');
}

function sleepWithAbort(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      const err = new Error('Request aborted');
      err.name = 'AbortError';
      reject(err);
      return;
    }

    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);

    const onAbort = () => {
      clearTimeout(timer);
      const err = new Error('Request aborted');
      err.name = 'AbortError';
      reject(err);
    };

    signal?.addEventListener('abort', onAbort, { once: true });
  });
}
