/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useHaptic } from "./useHaptic";

describe("useHaptic", () => {
  beforeEach(() => {
    vi.stubGlobal("navigator", {
      vibrate: vi.fn(() => true),
    });
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("vibrates with the given duration when vibrate is supported", () => {
    const { result } = renderHook(() => useHaptic());
    result.current(10);
    expect(navigator.vibrate).toHaveBeenCalledWith(10);
  });

  it("vibrates with a pattern array", () => {
    const { result } = renderHook(() => useHaptic());
    result.current([20, 30, 20]);
    expect(navigator.vibrate).toHaveBeenCalledWith([20, 30, 20]);
  });

  it("is a no-op when navigator.vibrate is undefined", () => {
    vi.stubGlobal("navigator", {}); // no vibrate
    const { result } = renderHook(() => useHaptic());
    // must not throw
    expect(() => result.current(10)).not.toThrow();
  });

  it("is a no-op when prefers-reduced-motion is reduce", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const vibrate = vi.fn(() => true);
    vi.stubGlobal("navigator", { vibrate });
    const { result } = renderHook(() => useHaptic());
    result.current(10);
    expect(vibrate).not.toHaveBeenCalled();
  });
});
