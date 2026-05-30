import { afterEach, describe, expect, it, vi } from "vitest";
import { debounce, debounceLeading } from "./debounce";
import { createMemoize, memoize, memoizeWithTTL } from "./memoize";
import { throttle, throttleWithTrailing } from "./throttle";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("performance debounce utilities", () => {
  it("runs only the latest debounced call after the wait period", () => {
    vi.useFakeTimers();
    const callback = vi.fn();
    const debounced = debounce(callback, 100);

    debounced("first");
    vi.advanceTimersByTime(50);
    debounced("second");

    expect(callback).not.toHaveBeenCalled();

    vi.advanceTimersByTime(99);
    expect(callback).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("second");
  });

  it("runs a leading call immediately and suppresses calls inside the wait period", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    const callback = vi.fn();
    const debounced = debounceLeading(callback, 100);

    debounced("first");
    debounced("second");

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("first");

    vi.advanceTimersByTime(100);
    vi.setSystemTime(new Date("2026-01-01T00:00:00.100Z"));
    debounced("third");

    expect(callback).toHaveBeenCalledTimes(2);
    expect(callback).toHaveBeenLastCalledWith("third");
  });
});

describe("performance throttle utilities", () => {
  it("runs the first throttled call immediately and ignores calls during the limit", () => {
    vi.useFakeTimers();
    const callback = vi.fn();
    const throttled = throttle(callback, 100);

    throttled("first");
    throttled("second");

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("first");

    vi.advanceTimersByTime(100);
    throttled("third");

    expect(callback).toHaveBeenCalledTimes(2);
    expect(callback).toHaveBeenLastCalledWith("third");
  });

  it("runs the last suppressed call when trailing throttle opens again", () => {
    vi.useFakeTimers();
    const callback = vi.fn();
    const throttled = throttleWithTrailing(callback, 100);

    throttled("first");
    throttled("second");
    throttled("third");

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("first");

    vi.advanceTimersByTime(100);

    expect(callback).toHaveBeenCalledTimes(2);
    expect(callback).toHaveBeenLastCalledWith("third");
  });
});

describe("performance memoization utilities", () => {
  it("reuses cached values for equivalent arguments", () => {
    const callback = vi.fn((value: number) => ({ doubled: value * 2 }));
    const memoized = memoize(callback);

    const first = memoized(7);
    const second = memoized(7);
    const third = memoized(8);

    expect(first).toBe(second);
    expect(third).toEqual({ doubled: 16 });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it("supports custom cache keys", () => {
    const callback = vi.fn(
      (input: { id: string; label: string }) => input.label,
    );
    const memoized = memoize(callback, (input) => input.id);

    expect(memoized({ id: "client-1", label: "first" })).toBe("first");
    expect(memoized({ id: "client-1", label: "second" })).toBe("first");

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("expires memoized values after the configured TTL", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    const callback = vi.fn(
      (value: string) => `${value}-${callback.mock.calls.length}`,
    );
    const memoized = memoizeWithTTL(callback, 100);

    expect(memoized("case")).toBe("case-1");
    expect(memoized("case")).toBe("case-1");

    vi.setSystemTime(new Date("2026-01-01T00:00:00.101Z"));

    expect(memoized("case")).toBe("case-2");
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it("can clear cached values explicitly", () => {
    const callback = vi.fn((value: number) => value * 10);
    const memoized = createMemoize(callback);

    expect(memoized(3)).toBe(30);
    expect(memoized(3)).toBe(30);
    memoized.clearCache();
    expect(memoized(3)).toBe(30);

    expect(callback).toHaveBeenCalledTimes(2);
  });
});
