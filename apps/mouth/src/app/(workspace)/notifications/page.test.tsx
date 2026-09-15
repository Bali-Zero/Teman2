import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NotificationsDashboardPage from "./page";

const requestMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({
  api: { crm: { request: requestMock } },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

const toastMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: toastMock,
}));

const ALERT = {
  id: 501,
  client_id: 42,
  client_name: "Fixture Client Alpha",
  client_email: "alpha@example.test",
  alert_type: "passport_warning",
  status: "pending",
  email_subject: "Passport expiring soon",
  created_at: "2026-09-01T00:00:00Z",
  sent_at: null,
  error_message: null,
};

const DASHBOARD_RESPONSE = {
  stats: {
    total_alerts_24h: 1,
    total_alerts_7d: 1,
    total_alerts_30d: 1,
    pending_count: 1,
    sent_count_24h: 0,
    failed_count_24h: 0,
    alerts_by_type: {},
    alerts_by_status: {},
    top_clients: [],
  },
  recent_alerts: [ALERT],
  system_status: "healthy",
};

describe("NotificationsDashboardPage — keyboard activation (K2c CONFIRM 4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requestMock.mockResolvedValue(DASHBOARD_RESPONSE);
  });

  it("Enter on the Pause control runs the pause path and does not toggle the row", async () => {
    const user = userEvent.setup();
    render(<NotificationsDashboardPage />);

    const row = await screen.findByRole("button", {
      name: "Notification for Fixture Client Alpha",
    });
    expect(row).toHaveAttribute("aria-expanded", "false");

    // Two Pause buttons render for the same row (a `touchAction` 44px
    // fallback and a hover/focus `actions` control, per HairlineRow) — both
    // must stop propagation identically, so either one proves the cure.
    const [pauseButton] = screen.getAllByRole("button", {
      name: "Pause notifications for Fixture Client Alpha",
    });

    pauseButton.focus();
    await user.keyboard("{Enter}");

    // The pause path ran (the confirm toast fired)...
    expect(toastMock).toHaveBeenCalledWith(
      "Pause notifications for this client for 24 hours?",
      expect.objectContaining({
        action: expect.objectContaining({ label: "Pause" }),
      }),
    );

    // ...and the row itself did NOT toggle open, which is what would happen
    // if the keydown had bubbled to the row's own onKeyDown.
    expect(row).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Email subject")).not.toBeInTheDocument();
  });

  it("Enter on the row itself still toggles it open", async () => {
    const user = userEvent.setup();
    render(<NotificationsDashboardPage />);

    const row = await screen.findByRole("button", {
      name: "Notification for Fixture Client Alpha",
    });
    row.focus();
    await user.keyboard("{Enter}");

    await waitFor(() => expect(row).toHaveAttribute("aria-expanded", "true"));
    expect(screen.getByText("Email subject")).toBeVisible();
  });
});
