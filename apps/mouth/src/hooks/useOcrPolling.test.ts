import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  api: {
    request: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({ api: mocks.api }));

import { useOcrPolling } from "./useOcrPolling";

function pending(n: number) {
  return { pending_ocr: n };
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useOcrPolling", () => {
  beforeEach(() => {
    mocks.api.request.mockReset();
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("polls at the configured interval and hits the ocr-status endpoint", async () => {
    mocks.api.request.mockResolvedValue(pending(3));
    const onDone = vi.fn();
    const { result } = renderHook(() =>
      useOcrPolling({ clientId: 42, onDone }),
    );

    act(() => result.current.pollOcrStatus());
    expect(result.current.ocrPolling).toBe(true);

    // initial delay (2000ms default)
    await advance(2000);
    expect(mocks.api.request).toHaveBeenCalledTimes(1);
    expect(mocks.api.request).toHaveBeenCalledWith(
      "/api/crm/clients/42/ocr-status",
    );

    // subsequent poll cadence (3000ms default)
    await advance(3000);
    expect(mocks.api.request).toHaveBeenCalledTimes(2);
    await advance(3000);
    expect(mocks.api.request).toHaveBeenCalledTimes(3);

    expect(onDone).not.toHaveBeenCalled();
    expect(result.current.ocrPolling).toBe(true);
  });

  it("stops on the terminal status (pending_ocr === 0) and calls onDone", async () => {
    mocks.api.request
      .mockResolvedValueOnce(pending(2))
      .mockResolvedValueOnce(pending(0));
    const onDone = vi.fn();
    const { result } = renderHook(() => useOcrPolling({ clientId: 7, onDone }));

    act(() => result.current.pollOcrStatus());
    await advance(2000); // 1st check: still pending
    expect(mocks.api.request).toHaveBeenCalledTimes(1);
    expect(result.current.ocrPolling).toBe(true);

    await advance(3000); // 2nd check: pending_ocr === 0 → terminal
    expect(mocks.api.request).toHaveBeenCalledTimes(2);
    expect(result.current.ocrPolling).toBe(false);
    expect(onDone).toHaveBeenCalledTimes(1);

    // no further checks scheduled
    await advance(10000);
    expect(mocks.api.request).toHaveBeenCalledTimes(2);
  });

  it("gives up after maxAttempts and calls onDone", async () => {
    mocks.api.request.mockResolvedValue(pending(5)); // never terminal on its own
    const onDone = vi.fn();
    const { result } = renderHook(() =>
      useOcrPolling({ clientId: 1, onDone, maxAttempts: 2 }),
    );

    act(() => result.current.pollOcrStatus());
    await advance(2000); // check #1: attempts=0 < maxAttempts, attempts -> 1
    await advance(3000); // check #2: attempts=1 < maxAttempts, attempts -> 2
    expect(mocks.api.request).toHaveBeenCalledTimes(2);
    expect(result.current.ocrPolling).toBe(true);

    await advance(3000); // check #3: attempts=2 >= maxAttempts -> terminal
    expect(mocks.api.request).toHaveBeenCalledTimes(3);
    expect(result.current.ocrPolling).toBe(false);
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("stops scheduling further checks on unmount (default cleanupOnUnmount)", async () => {
    mocks.api.request.mockResolvedValue(pending(9));
    const onDone = vi.fn();
    const { result, unmount } = renderHook(() =>
      useOcrPolling({ clientId: 5, onDone }),
    );

    act(() => result.current.pollOcrStatus());
    await advance(2000);
    expect(mocks.api.request).toHaveBeenCalledTimes(1);

    unmount();
    await advance(30000);

    // the in-flight timer was cleared, and the aborted guard blocks any
    // straggler from scheduling a follow-up poll
    expect(mocks.api.request).toHaveBeenCalledTimes(1);
    expect(onDone).not.toHaveBeenCalled();
  });

  it("surfaces the error path and calls onDone by default (guilt)", async () => {
    mocks.api.request.mockRejectedValue(new Error("network down"));
    const onDone = vi.fn();
    const { result } = renderHook(() => useOcrPolling({ clientId: 9, onDone }));

    act(() => result.current.pollOcrStatus());
    await advance(2000);

    expect(result.current.ocrPolling).toBe(false);
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("does not call onDone on the error path when callOnDoneOnError is false (innocence)", async () => {
    mocks.api.request.mockRejectedValue(new Error("network down"));
    const onDone = vi.fn();
    const { result } = renderHook(() =>
      useOcrPolling({ clientId: 9, onDone, callOnDoneOnError: false }),
    );

    act(() => result.current.pollOcrStatus());
    await advance(2000);

    expect(result.current.ocrPolling).toBe(false);
    expect(onDone).not.toHaveBeenCalled();
  });
});
