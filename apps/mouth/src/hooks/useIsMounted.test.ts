import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useIsMounted } from "./useIsMounted";

describe("useIsMounted", () => {
  it("returns isMounted as true while component is mounted", () => {
    const { result } = renderHook(() => useIsMounted());
    expect(result.current.isMounted()).toBe(true);
  });

  it("returns isMounted as false after unmount", () => {
    const { result, unmount } = renderHook(() => useIsMounted());
    expect(result.current.isMounted()).toBe(true);

    unmount();

    expect(result.current.isMounted()).toBe(false);
  });

  it("provides a ref that reflects mount status", () => {
    const { result, unmount } = renderHook(() => useIsMounted());
    expect(result.current.isMountedRef.current).toBe(true);

    unmount();

    expect(result.current.isMountedRef.current).toBe(false);
  });

  it("safeCallback executes fn when mounted", () => {
    const { result } = renderHook(() => useIsMounted());
    const fn = vi.fn(() => "result");

    const safeFn = result.current.safeCallback(fn);
    const returnVal = safeFn();

    expect(fn).toHaveBeenCalledTimes(1);
    expect(returnVal).toBe("result");
  });

  it("safeCallback does NOT execute fn when unmounted", () => {
    const { result, unmount } = renderHook(() => useIsMounted());
    const fn = vi.fn(() => "result");
    const safeFn = result.current.safeCallback(fn);

    unmount();

    const returnVal = safeFn();
    expect(fn).not.toHaveBeenCalled();
    expect(returnVal).toBeUndefined();
  });
});
