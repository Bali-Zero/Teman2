import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  markAllRead: vi.fn(),
  markRead: vi.fn(),
  retry: vi.fn(),
  retryMarkAllRead: vi.fn(),
  retryMarkRead: vi.fn(),
  usePortalNotifications: vi.fn(),
}));

vi.mock("@/hooks/usePortalNotifications", () => ({
  usePortalNotifications: mocks.usePortalNotifications,
}));

import {
  PortalNotificationBadge,
  PortalNotificationsList,
  PortalNotificationsPopover,
} from "./PortalNotifications";

const unread = {
  id: 7,
  type: "document_uploaded",
  title: "Synthetic document received",
  body: "A safe fixture is ready for review.",
  data: null,
  read: false,
  created_at: "2026-08-04T00:00:00Z",
};

function mockHook(overrides: Record<string, unknown> = {}) {
  mocks.usePortalNotifications.mockReturnValue({
    notifications: [],
    unreadCount: 0,
    isLoading: false,
    isError: false,
    isMarkingRead: false,
    isMarkingAllRead: false,
    isMarkReadError: false,
    isMarkAllReadError: false,
    markRead: mocks.markRead,
    markAllRead: mocks.markAllRead,
    retry: mocks.retry,
    retryMarkAllRead: mocks.retryMarkAllRead,
    retryMarkRead: mocks.retryMarkRead,
    ...overrides,
  });
}

describe("PortalNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHook();
  });

  it("renders bounded badges and the empty state", () => {
    const { rerender } = render(<PortalNotificationBadge count={0} />);
    expect(screen.queryByText("99+")).toBeNull();

    rerender(<PortalNotificationBadge count={120} />);
    expect(screen.getByText("99+")).toBeInTheDocument();

    render(
      <PortalNotificationsList
        notifications={[]}
        onMarkRead={mocks.markRead}
        onMarkAllRead={mocks.markAllRead}
      />,
    );
    expect(screen.getByText("No notifications yet")).toBeInTheDocument();
  });

  it("exposes named actions and honours mutation pending states", () => {
    render(
      <PortalNotificationsList
        notifications={[unread]}
        onMarkRead={mocks.markRead}
        onMarkAllRead={mocks.markAllRead}
        isMarkingRead
        isMarkingAllRead
      />,
    );

    expect(screen.getByText("Synthetic document received")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mark all read" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Mark as read" })).toBeDisabled();
  });

  it("reports loading and retryable error states", () => {
    mockHook({ isLoading: true });
    const { rerender } = render(<PortalNotificationsPopover />);
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading notifications",
    );

    mockHook({ isLoading: false, isError: true });
    rerender(<PortalNotificationsPopover />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Notifications are unavailable",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Retry notifications" }),
    );
    expect(mocks.retry).toHaveBeenCalledTimes(1);
  });

  it("reports mutation failures and exposes the matching retry actions", () => {
    mockHook({
      notifications: [unread],
      unreadCount: 1,
      isMarkReadError: true,
      isMarkAllReadError: true,
    });
    render(<PortalNotificationsPopover />);
    fireEvent.click(
      screen.getByRole("button", { name: "Notifications (1 unread)" }),
    );

    expect(screen.getAllByRole("alert")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Retry mark as read" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Retry mark all as read" }),
    );
    expect(mocks.retryMarkRead).toHaveBeenCalledTimes(1);
    expect(mocks.retryMarkAllRead).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["loading", { isLoading: true }],
    ["empty", {}],
  ])("moves focus inside the %s dialog state", (_state, overrides) => {
    mockHook(overrides);
    render(<PortalNotificationsPopover />);
    const trigger = screen.getByRole("button", { name: "Notifications" });
    trigger.focus();

    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "Notifications" });
    expect(dialog).toHaveAttribute("tabindex", "-1");
    expect(dialog).toHaveFocus();
  });

  it("exposes popover state and closes on Escape with focus restored", () => {
    mockHook({
      notifications: [unread],
      unreadCount: 1,
    });
    render(<PortalNotificationsPopover />);
    const trigger = screen.getByRole("button", {
      name: "Notifications (1 unread)",
    });

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const dialog = screen.getByRole("dialog", { name: "Notifications" });
    expect(dialog).toHaveFocus();

    screen.getByRole("button", { name: "Mark as read" }).focus();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "Notifications" })).toBeNull();
    expect(trigger).toHaveFocus();
  });
});
