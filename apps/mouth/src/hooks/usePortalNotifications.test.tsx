import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getNotifications: mocks.getNotifications,
      markAllNotificationsRead: mocks.markAllNotificationsRead,
      markNotificationRead: mocks.markNotificationRead,
    },
  },
}));

import { usePortalNotifications } from "./usePortalNotifications";

const createClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

const wrapperFor = (queryClient: QueryClient) => {
  function QueryWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  return QueryWrapper;
};

const availableResponse = { notifications: [], unread_count: 0 };

describe("usePortalNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getNotifications.mockResolvedValue(availableResponse);
  });

  it("maps an explicit backend degraded state to retryable query error", async () => {
    mocks.getNotifications.mockResolvedValue({
      ...availableResponse,
      degraded: true,
    });
    const queryClient = createClient();
    const { result } = renderHook(() => usePortalNotifications(), {
      wrapper: wrapperFor(queryClient),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.notifications).toEqual([]);

    act(() => result.current.retry());
    await waitFor(() =>
      expect(mocks.getNotifications).toHaveBeenCalledTimes(2),
    );
  });

  it("surfaces a mark-read failure and retries the same notification", async () => {
    mocks.markNotificationRead
      .mockRejectedValueOnce(new Error("synthetic write outage"))
      .mockResolvedValueOnce(undefined);
    const queryClient = createClient();
    const { result } = renderHook(() => usePortalNotifications(), {
      wrapper: wrapperFor(queryClient),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.markRead(7));
    await waitFor(() => expect(result.current.isMarkReadError).toBe(true));

    act(() => result.current.retryMarkRead());
    await waitFor(() =>
      expect(mocks.markNotificationRead).toHaveBeenNthCalledWith(2, 7),
    );
    await waitFor(() => expect(result.current.isMarkReadError).toBe(false));
  });

  it("surfaces and retries a mark-all failure", async () => {
    mocks.markAllNotificationsRead
      .mockRejectedValueOnce(new Error("synthetic write outage"))
      .mockResolvedValueOnce(undefined);
    const queryClient = createClient();
    const { result } = renderHook(() => usePortalNotifications(), {
      wrapper: wrapperFor(queryClient),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.markAllRead());
    await waitFor(() => expect(result.current.isMarkAllReadError).toBe(true));

    act(() => result.current.retryMarkAllRead());
    await waitFor(() =>
      expect(mocks.markAllNotificationsRead).toHaveBeenCalledTimes(2),
    );
    await waitFor(() => expect(result.current.isMarkAllReadError).toBe(false));
  });
});
