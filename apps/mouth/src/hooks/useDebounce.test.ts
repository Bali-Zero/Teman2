import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "./useDebounce";

describe("useDebounce", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("hello", 300));
    expect(result.current).toBe("hello");
  });

  it("does not update the debounced value before the delay", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "a", delay: 300 } },
    );

    rerender({ value: "b", delay: 300 });

    // Advance time but less than delay
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(result.current).toBe("a");
    vi.useRealTimers();
  });

  it("updates the debounced value after the delay", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "a", delay: 300 } },
    );

    rerender({ value: "b", delay: 300 });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe("b");
    vi.useRealTimers();
  });

  it("resets the delay when value changes rapidly", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "a", delay: 300 } },
    );

    // Type fast: change value multiple times within delay
    rerender({ value: "ab", delay: 300 });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ value: "abc", delay: 300 });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ value: "abcd", delay: 300 });

    // Still shows initial value - timer was reset each time
    expect(result.current).toBe("a");

    // Now wait the full delay from last change
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe("abcd");
    vi.useRealTimers();
  });

  it("uses default delay of 300ms", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value),
      { initialProps: { value: "start" } },
    );

    rerender({ value: "end" });

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("start");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("end");
    vi.useRealTimers();
  });

  it("works with non-string values", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 0, delay: 200 } },
    );

    rerender({ value: 42, delay: 200 });

    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current).toBe(42);
    vi.useRealTimers();
  });
});
