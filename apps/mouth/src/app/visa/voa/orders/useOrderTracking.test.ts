import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useOrderTracking } from "./useOrderTracking";
import type { OrderView, PracticeState } from "./types";

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function order(practiceState: PracticeState): OrderView {
  return {
    order_id: "order-1",
    order_state: "paid",
    price_idr: 850000,
    browser_observation: "browser_not_returned",
    practice: {
      practice_id: "practice-1",
      state: practiceState,
      artifact_available: practiceState === "Delivered",
    },
  };
}

function jsonResponse(body: OrderView): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useOrderTracking", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it.each<[PracticeState, PracticeState]>([
    ["Approved", "Delivered"],
    ["Blocked", "In review"],
    ["Blocked", "Submitted"],
  ])("refreshes %s to %s without a manual reload", async (from, to) => {
    const next = order(to);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(order(from)))
      .mockResolvedValue(jsonResponse(next));
    const { result } = renderHook(() => useOrderTracking("order-1"));

    await advance(0);
    expect(result.current.state).toEqual({ step: "ready", order: order(from) });
    await advance(5000);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current.state).toEqual({ step: "ready", order: next });
    if (to === "Delivered") {
      await advance(15000);
      expect(fetchMock).toHaveBeenCalledTimes(2);
    }
  });

  it.each<OrderView>([
    { ...order("Received"), order_state: "failed", practice: null },
    { ...order("Received"), order_state: "expired", practice: null },
    { ...order("Received"), order_state: "refunded", practice: null },
    order("Delivered"),
    order("Rejected"),
  ])("stops polling for terminal order/practice %j", async (terminal) => {
    fetchMock.mockResolvedValue(jsonResponse(terminal));
    const { result } = renderHook(() => useOrderTracking("order-1"));

    await advance(0);
    await advance(15000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.current.state).toEqual({ step: "ready", order: terminal });
  });

  it("cancels a scheduled refresh on unmount", async () => {
    fetchMock.mockResolvedValue(jsonResponse(order("Approved")));
    const { unmount } = renderHook(() => useOrderTracking("order-1"));
    await advance(0);

    unmount();
    await advance(15000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("aborts an in-flight refresh on unmount", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(order("Approved")))
      .mockImplementationOnce(() => new Promise<Response>(() => {}));
    const { unmount } = renderHook(() => useOrderTracking("order-1"));
    await advance(0);
    await advance(5000);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(init.signal?.aborted).toBe(false);
    unmount();
    expect(init.signal?.aborted).toBe(true);
  });
});
