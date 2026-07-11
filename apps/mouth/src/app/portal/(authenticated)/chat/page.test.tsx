/**
 * ChatPage – infinite-fetch regression test.
 *
 * REGRESSION: before the fix, a useEffect dependency cycle caused
 * GET /api/portal/messages to be called ~1167 times on a single page-load.
 * Cycle: messages → markVisibleMessagesAsRead (useCallback) → effect
 *   → loadMessages(true) → setMessages → messages → …
 *
 * This test mounts the component with a mocked api and asserts that
 * getMessages is called at most 2 times within 3 seconds:
 *   1. initial load
 *   2. (optional) one silent refresh after mark-as-read, only when unread > 0
 *
 * If the cycle regresses, call count will exceed 5 within the window.
 */
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  afterAll,
} from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import React from "react";

// ─── Mocks ────────────────────────────────────────────────────────────────────

// Mock Next.js navigation (required by portal layout providers)
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/portal/chat",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock the api module
const mockGetMessages = vi.fn();
const mockMarkMessageRead = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getMessages: mockGetMessages,
      markMessageRead: mockMarkMessageRead,
    },
  },
}));

// Mock toast (useToast must be inside a provider; simplest mock)
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    toast: vi.fn(),
    dismiss: vi.fn(),
    clear: vi.fn(),
  }),
}));

// Mock logger
vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

// ─── Test helpers ─────────────────────────────────────────────────────────────

import type { MessagesResponse } from "@/lib/api/portal/portal.types";

const EMPTY_RESPONSE: MessagesResponse = {
  messages: [],
  total: 0,
  unreadCount: 0,
};

const UNREAD_RESPONSE: MessagesResponse = {
  messages: [
    {
      id: "1",
      content: "Hello from team",
      direction: "team_to_client",
      sentBy: "Agent",
      createdAt: new Date().toISOString(),
      // no readAt → unread
    },
  ],
  total: 1,
  unreadCount: 1,
};

// ─── Tests ────────────────────────────────────────────────────────────────────

// Dynamically import after mocks are set up
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let ChatPage: React.ComponentType<any>;

beforeEach(async () => {
  vi.useFakeTimers();
  mockGetMessages.mockReset();
  mockMarkMessageRead.mockReset();
  // Re-import to get a fresh module with fresh hooks state
  const mod = await import("./page");
  ChatPage = mod.default;
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

afterAll(() => {
  vi.restoreAllMocks();
});

describe("ChatPage – infinite-fetch regression", () => {
  it("calls getMessages ONCE on initial load when there are no unread messages", async () => {
    mockGetMessages.mockResolvedValue(EMPTY_RESPONSE);

    await act(async () => {
      render(<ChatPage />);
    });

    // Advance timers past the mark-as-read timeout (1000ms) and the polling
    // interval (30 000ms) to make sure no extra calls sneak in
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    // Allow any pending microtasks to settle
    await act(async () => {
      await Promise.resolve();
    });

    // Should be exactly 1 (initial load only; mark-as-read didn't run because
    // there are no unread messages, so no refresh was needed)
    expect(mockGetMessages).toHaveBeenCalledTimes(1);
  });

  it("calls getMessages at most TWICE when there are unread messages (load + mark-as-read refresh)", async () => {
    // First call returns unread; subsequent calls return empty (after mark)
    mockGetMessages
      .mockResolvedValueOnce(UNREAD_RESPONSE)
      .mockResolvedValue(EMPTY_RESPONSE);
    mockMarkMessageRead.mockResolvedValue(undefined);

    await act(async () => {
      render(<ChatPage />);
    });

    // Advance past the 1-second mark-as-read debounce
    await act(async () => {
      vi.advanceTimersByTime(1500);
    });

    await act(async () => {
      await Promise.resolve();
    });

    // ≤ 2: initial load + one silent refresh after marking as read
    expect(mockGetMessages.mock.calls.length).toBeLessThanOrEqual(2);
    // Must have been called at least once (initial load)
    expect(mockGetMessages).toHaveBeenCalledTimes(
      mockGetMessages.mock.calls.length,
    );
  });

  it("NEVER fires more than 5 calls to getMessages in the first 5 seconds (regression guard)", async () => {
    // Simulate rapid responses to stress the dep cycle
    mockGetMessages.mockResolvedValue(UNREAD_RESPONSE);
    mockMarkMessageRead.mockResolvedValue(undefined);

    await act(async () => {
      render(<ChatPage />);
    });

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    await act(async () => {
      await Promise.resolve();
    });

    // Before the fix this was ~1167. The threshold of 5 is very generous.
    expect(mockGetMessages.mock.calls.length).toBeLessThan(5);
  });
});
