import React from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  focusManager,
} from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PortalMessageNotice } from "@/components/portal/PortalMessageNotice";
import { TeamPortalMessageAlerts } from "@/components/workspace/TeamPortalMessageAlerts";
import { PortalBottomNav } from "@/components/portal/PortalBottomNav";
import { PortalNotificationsPopover } from "@/components/portal/PortalNotifications";
import {
  portalUnreadKey,
  teamPortalUnreadKey,
} from "./usePortalUnreadMessages";

const mocks = vi.hoisted(() => ({
  messages: vi.fn(),
  team: vi.fn(),
  markRead: vi.fn(),
  path: "/portal",
  clientId: null as number | null,
}));
vi.mock("next/navigation", () => ({ usePathname: () => mocks.path }));
vi.mock("@/lib/api", () => ({
  api: {
    getUserProfile: () => ({ id: "synthetic-user" }),
    getPortalImpersonation: () => mocks.clientId,
    portal: { getMessages: mocks.messages, markMessageRead: mocks.markRead },
    crm: {
      getPortalUnreadCount: mocks.team,
      markPortalMessageRead: mocks.markRead,
    },
  },
}));
vi.mock("@/hooks/usePortalNotifications", () => ({
  usePortalNotifications: () => ({
    notifications: [],
    unreadCount: 0,
    isLoading: false,
    isError: false,
    markRead: mocks.markRead,
    markAllRead: mocks.markRead,
  }),
}));

function mount(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
  return { client, ...view };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.path = "/portal";
  mocks.clientId = null;
  mocks.messages.mockResolvedValue({ messages: [], unreadCount: 7, total: 90 });
  mocks.team.mockResolvedValue({
    total_unread: 3,
    by_client: [
      { client_id: 42, client_name: "Synthetic Client", unread_count: 3 },
    ],
  });
});
afterEach(() => focusManager.setFocused(undefined));

describe("portal message alerts", () => {
  it("shares the server total across banner, nav and bell without reading messages", async () => {
    mount(
      <>
        <PortalMessageNotice />
        <PortalBottomNav />
        <PortalNotificationsPopover />
      </>,
    );
    await screen.findByText("7 unread messages from your team");
    expect(mocks.messages).toHaveBeenCalledTimes(1);
    expect(mocks.messages).toHaveBeenCalledWith(1, 0);
    fireEvent.click(
      screen.getByRole("button", { name: "Notifications (7 unread messages)" }),
    );
    expect(
      screen.getAllByRole("link", { name: /7 unread messages/ }),
    ).toHaveLength(2);
    expect(
      screen.getAllByRole("link", { name: /7 unread messages/ })[0],
    ).toHaveAttribute("href", "/portal/messages");
    expect(mocks.markRead).not.toHaveBeenCalled();
  });

  it("refreshes all client indicators after the thread invalidates a successful read", async () => {
    const { client } = mount(
      <>
        <PortalMessageNotice />
        <PortalBottomNav />
      </>,
    );
    await screen.findByText("7 unread messages from your team");
    mocks.messages.mockResolvedValue({
      messages: [],
      unreadCount: 0,
      total: 90,
    });
    await act(() => client.invalidateQueries({ queryKey: portalUnreadKey }));
    await waitFor(() =>
      expect(screen.queryByText(/unread messages from your team/)).toBeNull(),
    );
    expect(screen.queryByText("7")).toBeNull();
  });

  it("preserves last known unread on failure and provides retry rather than a false zero", async () => {
    const { client } = mount(<PortalMessageNotice />);
    await screen.findByText("7 unread messages from your team");
    mocks.messages.mockRejectedValue(new Error("synthetic network failure"));
    await act(() => client.invalidateQueries({ queryKey: portalUnreadKey }));
    await screen.findByText(/Message count may be out of date/);
    expect(
      screen.getByText("7 unread messages from your team"),
    ).toBeInTheDocument();
    mocks.messages.mockResolvedValue({ unreadCount: 0 });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(screen.queryByText(/unread messages from your team/)).toBeNull(),
    );
  });

  it("shows an initial failure and checks again when the app regains focus", async () => {
    mocks.messages.mockRejectedValue(new Error("synthetic network failure"));
    mount(<PortalMessageNotice />);
    await screen.findByText(/Cannot check messages/);
    mocks.messages.mockResolvedValue({ unreadCount: 2 });
    act(() => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });
    await screen.findByText("2 unread messages from your team");
  });

  it("links the team directly to the correct thread and clears only after invalidation", async () => {
    const { client } = mount(<TeamPortalMessageAlerts />);
    fireEvent.click(
      await screen.findByRole("button", { name: "3 unread client messages" }),
    );
    expect(
      screen.getByRole("link", { name: /Synthetic Client/ }),
    ).toHaveAttribute("href", "/clients/42?tab=overview#portal-messages");
    expect(mocks.markRead).not.toHaveBeenCalled();
    mocks.team.mockResolvedValue({ total_unread: 0, by_client: [] });
    await act(() =>
      client.invalidateQueries({ queryKey: teamPortalUnreadKey }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /unread client messages/ }),
      ).toBeNull(),
    );
  });

  it("does not reuse another impersonated client's cached count", async () => {
    const { client, rerender } = mount(<PortalMessageNotice />);
    await screen.findByText("7 unread messages from your team");
    mocks.clientId = 99;
    mocks.messages.mockResolvedValue({ unreadCount: 1 });
    rerender(
      <QueryClientProvider client={client}>
        <PortalMessageNotice />
      </QueryClientProvider>,
    );
    await screen.findByText("1 unread message from your team");
    expect(screen.queryByText("7 unread messages from your team")).toBeNull();
  });
});

describe("team reply reminders", () => {
  it("keeps a read client conversation visible until a reply is saved", async () => {
    mocks.team.mockResolvedValue({
      total_unread: 0,
      by_client: [],
      total_pending: 1,
      pending_by_client: [
        { client_id: 42, client_name: "Synthetic Client", pending_count: 2 },
      ],
    });
    const { client } = mount(<TeamPortalMessageAlerts />);
    const trigger = await screen.findByRole("button", {
      name: "1 client awaiting a reply",
    });
    fireEvent.click(trigger);
    expect(
      screen.getByText("The reminder stays until you reply."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Synthetic Client/ }),
    ).toHaveAttribute("href", "/clients/42?tab=overview#portal-messages");
    expect(mocks.markRead).not.toHaveBeenCalled();
    fireEvent.click(trigger);
    expect(
      screen.getByRole("button", { name: "1 client awaiting a reply" }),
    ).toBeInTheDocument();
    mocks.team.mockResolvedValue({
      total_unread: 0,
      by_client: [],
      total_pending: 0,
      pending_by_client: [],
    });
    await act(() =>
      client.invalidateQueries({ queryKey: teamPortalUnreadKey }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /awaiting a reply/ }),
      ).toBeNull(),
    );
  });

  it("retains a known pending reply when the refresh fails", async () => {
    mocks.team.mockResolvedValue({
      total_unread: 0,
      by_client: [],
      total_pending: 1,
      pending_by_client: [
        { client_id: 42, client_name: "Synthetic Client", pending_count: 1 },
      ],
    });
    const { client } = mount(<TeamPortalMessageAlerts />);
    await screen.findByRole("button", { name: "1 client awaiting a reply" });
    mocks.team.mockRejectedValue(new Error("offline"));
    await act(() =>
      client.invalidateQueries({ queryKey: teamPortalUnreadKey }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "1 client awaiting a reply" }),
    );
    expect(
      await screen.findByRole("button", { name: "Retry" }),
    ).toBeInTheDocument();
  });
});
