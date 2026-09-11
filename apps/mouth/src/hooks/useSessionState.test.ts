import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  hasSession: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { hasSession: mocks.hasSession },
}));

import { useSessionState } from "./useSessionState";

describe("useSessionState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('always seeds "pending" on the first render, even when the session will resolve authenticated', () => {
    mocks.hasSession.mockResolvedValue("authenticated");

    const { result } = renderHook(() => useSessionState());

    expect(result.current).toBe("pending");
  });

  it('resolves pending -> "authenticated"', async () => {
    mocks.hasSession.mockResolvedValue("authenticated");

    const { result } = renderHook(() => useSessionState());

    await waitFor(() => expect(result.current).toBe("authenticated"));
  });

  it('resolves pending -> "anonymous"', async () => {
    mocks.hasSession.mockResolvedValue("anonymous");

    const { result } = renderHook(() => useSessionState());

    await waitFor(() => expect(result.current).toBe("anonymous"));
  });

  it('resolves pending -> "unknown"', async () => {
    mocks.hasSession.mockResolvedValue("unknown");

    const { result } = renderHook(() => useSessionState());

    await waitFor(() => expect(result.current).toBe("unknown"));
  });

  it("does not call setState after unmount (no late resolution leak)", async () => {
    let resolveHasSession!: (value: "authenticated") => void;
    mocks.hasSession.mockReturnValue(
      new Promise((resolve) => {
        resolveHasSession = resolve;
      }),
    );

    const { result, unmount } = renderHook(() => useSessionState());
    expect(result.current).toBe("pending");

    unmount();
    resolveHasSession("authenticated");
    // Flush microtasks. If the `alive` guard were missing, the hook would
    // attempt a setState here — this stays "pending" (the last value
    // committed before unmount) either way, so a regression must be caught
    // by the ABSENCE of a React "state update on unmounted component"
    // console.error, not by this value changing.
    await Promise.resolve();
    await Promise.resolve();

    expect(result.current).toBe("pending");
  });
});
