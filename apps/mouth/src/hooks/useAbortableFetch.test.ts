import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAbortableFetch } from "./useAbortableFetch";

describe("useAbortableFetch", () => {
  it("returns createFetch function", () => {
    const { result } = renderHook(() => useAbortableFetch());
    expect(result.current.createFetch).toBeInstanceOf(Function);
  });

  it("provides an AbortSignal to the fetch function", async () => {
    const { result } = renderHook(() => useAbortableFetch());
    let receivedSignal: AbortSignal | null = null;

    await act(async () => {
      await result.current.createFetch(async (signal) => {
        receivedSignal = signal;
        return "data";
      });
    });

    expect(receivedSignal).toBeInstanceOf(AbortSignal);
  });

  it("aborts previous request when creating a new one", async () => {
    const { result } = renderHook(() => useAbortableFetch());
    let firstSignal: AbortSignal | null = null;

    // Start first request (don't await -- it will be aborted)
    act(() => {
      result.current.createFetch(async (signal) => {
        firstSignal = signal;
        // Simulate a slow request
        await new Promise((resolve) => setTimeout(resolve, 10_000));
        return "first";
      });
    });

    // Start second request - should abort first
    act(() => {
      result.current.createFetch(async (signal) => {
        return "second";
      });
    });

    expect(firstSignal!.aborted).toBe(true);
  });

  it("aborts on unmount", () => {
    const { result, unmount } = renderHook(() => useAbortableFetch());
    let signalRef: AbortSignal | null = null;

    act(() => {
      result.current.createFetch(async (signal) => {
        signalRef = signal;
        await new Promise((resolve) => setTimeout(resolve, 10_000));
        return "data";
      });
    });

    unmount();

    expect(signalRef!.aborted).toBe(true);
  });
});
