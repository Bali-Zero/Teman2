import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import React from "react";
import { PortalBottomNav } from "./PortalBottomNav";

// Hoisted mocks (must be defined before vi.mock)
const { mockUsePathname, mockGetMessages } = vi.hoisted(() => ({
  mockUsePathname: vi.fn(() => "/portal"),
  mockGetMessages: vi.fn(),
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getMessages: mockGetMessages,
    },
  },
}));

describe("PortalBottomNav", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePathname.mockReturnValue("/portal");
    // Default mock that resolves immediately
    mockGetMessages.mockResolvedValue({
      messages: [],
      total: 0,
      unreadCount: 0,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should render navigation tabs", async () => {
    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(screen.getByText("Home")).toBeInTheDocument();
      expect(screen.getByText("Vault")).toBeInTheDocument();
      expect(screen.getByText("Chat")).toBeInTheDocument();
      expect(screen.getByText("Profile")).toBeInTheDocument();
    });
  });

  it("should highlight active tab based on pathname", async () => {
    mockUsePathname.mockReturnValue("/portal/vault");

    render(<PortalBottomNav />);

    await waitFor(() => {
      const vaultLink = screen.getByText("Vault").closest("a");
      expect(vaultLink).toHaveAttribute("href", "/portal/vault");
    });
  });

  it("should fetch and display unread message count", async () => {
    mockGetMessages.mockResolvedValue({
      messages: [],
      total: 0,
      unreadCount: 5,
    });

    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1, 0);
    });

    await waitFor(() => {
      const badge = screen.getByText("5");
      expect(badge).toBeInTheDocument();
    });
  });

  it("should display 99+ for counts over 99", async () => {
    mockGetMessages.mockResolvedValue({
      messages: [],
      total: 0,
      unreadCount: 150,
    });

    render(<PortalBottomNav />);

    await waitFor(() => {
      const badge = screen.getByText("99+");
      expect(badge).toBeInTheDocument();
    });
  });

  it("should not show badge when unread count is 0", async () => {
    mockGetMessages.mockResolvedValue({
      messages: [],
      total: 0,
      unreadCount: 0,
    });

    const { container } = render(<PortalBottomNav />);

    // Wait for API call to complete
    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalled();
    });

    // Badge with unread count should not exist
    // The badge element has specific classes, so we check for absence of badge content
    expect(screen.queryByText("99+")).not.toBeInTheDocument();
    // No numeric badge should be visible (checking for the badge span specifically)
    const badges = container.querySelectorAll(".bg-red-500");
    expect(badges.length).toBe(0);
  });

  it("should poll for unread count every 30 seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockGetMessages.mockResolvedValue({
      messages: [],
      total: 0,
      unreadCount: 0,
    });

    render(<PortalBottomNav />);

    // Wait for initial fetches (2 calls: initial useEffect + pathname change useEffect)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const initialCallCount = mockGetMessages.mock.calls.length;
    expect(initialCallCount).toBeGreaterThanOrEqual(1);

    // Fast-forward 30 seconds for polling
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });

    // Should have at least one more call from the polling interval
    expect(mockGetMessages.mock.calls.length).toBeGreaterThan(initialCallCount);
  });

  it("should refetch when navigating away from chat", async () => {
    mockUsePathname.mockReturnValue("/portal/chat");
    mockGetMessages.mockResolvedValue({
      messages: [],
      total: 0,
      unreadCount: 0,
    });

    const { rerender } = render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalled();
    });

    const callCountAfterInitial = mockGetMessages.mock.calls.length;

    // Navigate away from chat
    mockUsePathname.mockReturnValue("/portal/vault");
    rerender(<PortalBottomNav />);

    await waitFor(() => {
      // Should have been called again due to pathname change
      expect(mockGetMessages.mock.calls.length).toBeGreaterThan(
        callCountAfterInitial,
      );
    });
  });

  it("should handle API errors gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockGetMessages.mockRejectedValue(new Error("API Error"));

    // Should not throw
    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalled();
    });

    // Component should still render
    expect(screen.getByText("Home")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it("should only render on mobile (md:hidden)", async () => {
    const { container } = render(<PortalBottomNav />);

    await waitFor(() => {
      expect(screen.getByText("Home")).toBeInTheDocument();
    });

    const nav = container.querySelector(".md\\:hidden");
    expect(nav).toBeInTheDocument();
  });
});
