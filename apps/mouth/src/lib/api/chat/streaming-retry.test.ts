import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  classifyStreamError,
  computeBackoffDelay,
  retryableFetch,
  DEFAULT_RETRY_CONFIG,
} from './streaming-retry';

describe('classifyStreamError', () => {
  it('classifies AbortError as abort', () => {
    const err = new Error('aborted');
    err.name = 'AbortError';
    expect(classifyStreamError(err)).toBe('abort');
  });

  it('classifies fetch TypeError as network', () => {
    const err = new TypeError('Failed to fetch');
    expect(classifyStreamError(err)).toBe('network');
  });

  it('classifies HTTP <code> messages as http', () => {
    expect(classifyStreamError(new Error('HTTP 401'))).toBe('http');
    expect(classifyStreamError(new Error('HTTP 503'))).toBe('http');
  });

  it('classifies timeout messages as timeout', () => {
    expect(classifyStreamError(new Error('idle timeout'))).toBe('timeout');
    expect(classifyStreamError(new Error('Request timed out'))).toBe('timeout');
  });

  it('classifies JSON parse errors as parse', () => {
    expect(classifyStreamError(new Error('Unexpected token < in JSON'))).toBe('parse');
  });

  it('falls back to network when navigator.onLine is false', () => {
    const onLine = Object.getOwnPropertyDescriptor(navigator, 'onLine');
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      configurable: true,
    });
    try {
      // Generic Error with no other signal: would be "unknown" otherwise.
      expect(classifyStreamError(new Error('oops'))).toBe('network');
    } finally {
      if (onLine) Object.defineProperty(navigator, 'onLine', onLine);
    }
  });

  it('returns unknown for non-Error values', () => {
    expect(classifyStreamError('string error')).toBe('unknown');
    expect(classifyStreamError(null)).toBe('unknown');
  });
});

describe('computeBackoffDelay', () => {
  it('matches the documented schedule 500/1000/2000', () => {
    expect(computeBackoffDelay(1)).toBe(500);
    expect(computeBackoffDelay(2)).toBe(1000);
    expect(computeBackoffDelay(3)).toBe(2000);
  });

  it('caps at maxDelayMs', () => {
    expect(
      computeBackoffDelay(20, {
        ...DEFAULT_RETRY_CONFIG,
        maxDelayMs: 3_000,
      })
    ).toBe(3_000);
  });

  it('returns 0 for non-positive attempt', () => {
    expect(computeBackoffDelay(0)).toBe(0);
    expect(computeBackoffDelay(-5)).toBe(0);
  });
});

describe('retryableFetch', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const networkError = () => {
    const err = new TypeError('Failed to fetch');
    return err;
  };

  it('succeeds on first attempt without retry', async () => {
    const fn = vi.fn().mockResolvedValue('ok');
    const result = await retryableFetch(fn);
    expect(result).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('retries on network error then succeeds', async () => {
    const fn = vi.fn().mockRejectedValueOnce(networkError()).mockResolvedValueOnce('ok');
    const onRetry = vi.fn();

    const promise = retryableFetch(fn, { onRetry });

    // Advance through the 500ms backoff for attempt 1.
    await vi.advanceTimersByTimeAsync(500);

    expect(await promise).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(2);
    expect(onRetry).toHaveBeenCalledWith(1, 500, expect.any(TypeError));
  });

  it('throws after exhausting maxRetries on persistent network errors', async () => {
    const fn = vi.fn().mockRejectedValue(networkError());

    const promise = retryableFetch(fn).catch((e) => e);

    // 3 retries: 500 + 1000 + 2000
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);

    const result = await promise;
    expect(result).toBeInstanceOf(TypeError);
    expect(fn).toHaveBeenCalledTimes(4); // 1 initial + 3 retries
  });

  it('does NOT retry on HTTP errors', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('HTTP 401'));
    await expect(retryableFetch(fn)).rejects.toThrow('HTTP 401');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('does NOT retry when AbortSignal is already aborted', async () => {
    const controller = new AbortController();
    controller.abort();
    const fn = vi.fn().mockResolvedValue('never');

    await expect(retryableFetch(fn, { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    });
    expect(fn).not.toHaveBeenCalled();
  });

  it('aborts mid-backoff when signal fires during sleep', async () => {
    const controller = new AbortController();
    const fn = vi.fn().mockRejectedValue(networkError());

    const promise = retryableFetch(fn, { signal: controller.signal }).catch((e: unknown) => e);

    // First attempt failed, now sleeping 500ms — abort 100ms in.
    await vi.advanceTimersByTimeAsync(100);
    controller.abort();
    await vi.advanceTimersByTimeAsync(500);

    const result = (await promise) as Error;
    expect(result.name).toBe('AbortError');
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
