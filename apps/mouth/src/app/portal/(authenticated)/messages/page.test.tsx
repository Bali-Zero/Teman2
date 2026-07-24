/**
 * MessagesPage – smoke test.
 *
 * /portal/messages re-exports the Chat page (both URLs serve the same
 * client ↔ team messaging UI). This test guards the re-export wiring and
 * pins the day-theme masthead (WS3 slice 6) so the alias route cannot drift
 * from /portal/chat.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import React from "react";

// Mock Next.js navigation (required by portal layout providers)
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/portal/messages",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock the api module
const mockGetMessages = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getMessages: mockGetMessages,
      markMessageRead: vi.fn().mockResolvedValue(undefined),
    },
  },
}));

// Mock toast
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

import type { MessagesResponse } from "@/lib/api/portal/portal.types";

const EMPTY_RESPONSE: MessagesResponse = {
  messages: [],
  total: 0,
  unreadCount: 0,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let MessagesPage: React.ComponentType<any>;

beforeEach(async () => {
  vi.useFakeTimers();
  mockGetMessages.mockReset();
  const mod = await import("./page");
  MessagesPage = mod.default;
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("MessagesPage – /portal/messages alias", () => {
  it("re-exports the Chat page: renders the same day-theme masthead", async () => {
    mockGetMessages.mockResolvedValue(EMPTY_RESPONSE);

    await act(async () => {
      render(<MessagesPage />);
    });

    await act(async () => {
      await Promise.resolve();
    });

    // Same masthead as /portal/chat (serif headline, token-driven)
    const h1 = document.querySelector("h1");
    expect(h1).not.toBeNull();
    expect(h1!.textContent).toBe("Messages");
    expect(h1!.style.fontFamily).toBe("var(--font-serif)");
    // Initial fetch fired → the alias is wired to the real page, not a stub
    expect(mockGetMessages).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state with token-driven chrome", async () => {
    mockGetMessages.mockResolvedValue(EMPTY_RESPONSE);

    const { container } = await act(async () => render(<MessagesPage />));

    await act(async () => {
      await Promise.resolve();
    });

    expect(container.textContent).toContain("No messages yet");
    // Drain guard: no legacy hardcoded dark-glass colors
    expect(container.innerHTML).not.toContain("rgba(255,255,255");
    expect(container.innerHTML).not.toContain("#0c0c0e"); // token-lint-ok: drain-guard assertion string, not a color usage
  });
});
