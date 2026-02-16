/**
 * Unit tests for useTypewriter hook
 *
 * Tests cover:
 * - Empty text handling
 * - Typing progression
 * - Skip functionality
 * - Speed=0 instant display
 * - isTyping state transitions
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTypewriter } from "../../hooks/useTypewriter";

describe("useTypewriter", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return empty string for empty text", () => {
    const { result } = renderHook(() => useTypewriter("", 15));
    expect(result.current.displayText).toBe("");
    expect(result.current.isTyping).toBe(false);
  });

  it("should start typing when text is provided", () => {
    const { result } = renderHook(() => useTypewriter("Hello world", 15));

    // Initially empty, typing starts
    expect(result.current.isTyping).toBe(true);
    expect(result.current.displayText).toBe("");
  });

  it("should progressively reveal text", () => {
    const { result } = renderHook(() => useTypewriter("Hi", 10));

    // Advance timers to type characters
    act(() => {
      vi.advanceTimersByTime(50);
    });

    // Should have typed at least some characters
    expect(result.current.displayText.length).toBeGreaterThan(0);
  });

  it("should complete typing and set isTyping to false", () => {
    const { result } = renderHook(() => useTypewriter("Hi", 10));

    // Advance enough time to finish
    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current.displayText).toBe("Hi");
    expect(result.current.isTyping).toBe(false);
  });

  it("should skip to full text when skip() is called", () => {
    const { result } = renderHook(() =>
      useTypewriter("Hello world, this is a long text", 15),
    );

    expect(result.current.isTyping).toBe(true);

    act(() => {
      result.current.skip();
    });

    expect(result.current.displayText).toBe("Hello world, this is a long text");
    expect(result.current.isTyping).toBe(false);
  });

  it("should complete very quickly when speed is 0", () => {
    const { result } = renderHook(() => useTypewriter("Instant text", 0));

    // With speed 0, advance enough for all chars to type (each char takes ~0-10ms)
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current.displayText).toBe("Instant text");
    expect(result.current.isTyping).toBe(false);
  });

  it("should provide a skip function", () => {
    const { result } = renderHook(() => useTypewriter("test", 15));
    expect(typeof result.current.skip).toBe("function");
  });

  it("should reset when text changes", () => {
    const { result, rerender } = renderHook(
      ({ text }) => useTypewriter(text, 15),
      {
        initialProps: { text: "First" },
      },
    );

    // Type first text fully
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.displayText).toBe("First");

    // Change text
    rerender({ text: "Second" });

    // Should restart typing
    expect(result.current.isTyping).toBe(true);
  });
});
