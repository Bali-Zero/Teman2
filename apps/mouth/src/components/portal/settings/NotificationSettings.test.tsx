import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const hookMock = vi.fn();
vi.mock("@/hooks/useNotificationPrefs", () => ({
  useNotificationPrefs: () => hookMock(),
}));

import { NotificationSettings } from "./NotificationSettings";

describe("NotificationSettings", () => {
  beforeEach(() => {
    hookMock.mockReset();
  });

  it("renders loading state", () => {
    hookMock.mockReturnValue({
      data: null,
      migrationMissing: false,
      isLoading: true,
      error: undefined,
      updatePrefs: vi.fn(),
      isUpdating: false,
    });
    render(<NotificationSettings />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders migration-missing banner when hook signals 503", () => {
    const mutate = vi.fn();
    hookMock.mockReturnValue({
      data: null,
      migrationMissing: true,
      isLoading: false,
      error: undefined,
      mutate,
      updatePrefs: vi.fn(),
      isUpdating: false,
    });
    render(<NotificationSettings />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /temporarily unavailable/i,
    );
    // No toggles should be rendered in degraded state.
    expect(screen.queryByLabelText(/email notifications/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mutate).toHaveBeenCalledOnce();
  });

  it("suppresses raw read errors and retries through SWR", () => {
    const mutate = vi.fn();
    hookMock.mockReturnValue({
      data: null,
      migrationMissing: false,
      isLoading: false,
      error: new Error("relation notification_prefs failed at internal-host"),
      mutate,
      updatePrefs: vi.fn(),
      isUpdating: false,
    });
    render(<NotificationSettings />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      /unable to load preferences/i,
    );
    expect(screen.queryByText(/notification_prefs|internal-host/i)).toBeNull();
    expect(screen.queryByLabelText(/email notifications/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mutate).toHaveBeenCalledOnce();
  });

  it("renders toggles and fires updatePrefs on change", () => {
    const updatePrefs = vi.fn();
    hookMock.mockReturnValue({
      data: { email_enabled: true, wa_enabled: false, wa_phone: null },
      migrationMissing: false,
      isLoading: false,
      error: undefined,
      updatePrefs,
      isUpdating: false,
    });
    render(<NotificationSettings />);

    const email = screen.getByLabelText(/email notifications/i);
    expect(email).toBeChecked();

    const wa = screen.getByLabelText(/whatsapp notifications/i);
    expect(screen.getByLabelText(/whatsapp number/i)).toBeInTheDocument();
    fireEvent.click(wa);

    expect(updatePrefs).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /enter a valid whatsapp number/i,
    );
  });

  it("saves a number before enabling WhatsApp notifications", async () => {
    const updatePrefs = vi.fn().mockResolvedValue({
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "12025550123",
    });
    hookMock.mockReturnValue({
      data: { email_enabled: true, wa_enabled: false, wa_phone: null },
      migrationMissing: false,
      isLoading: false,
      error: undefined,
      updatePrefs,
      isUpdating: false,
    });
    render(<NotificationSettings />);

    const phone = screen.getByLabelText(/whatsapp number/i);
    fireEvent.change(phone, { target: { value: "12025550123" } });
    fireEvent.blur(phone);
    expect(updatePrefs).toHaveBeenNthCalledWith(1, {
      email_enabled: true,
      wa_enabled: false,
      wa_phone: "12025550123",
    });

    fireEvent.click(screen.getByLabelText(/whatsapp notifications/i));
    expect(updatePrefs).toHaveBeenNthCalledWith(2, {
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "12025550123",
    });
  });

  it("renders update failures instead of leaking an unhandled rejection", async () => {
    const updatePrefs = vi.fn().mockRejectedValue(new Error("HTTP 500"));
    hookMock.mockReturnValue({
      data: { email_enabled: true, wa_enabled: false, wa_phone: null },
      migrationMissing: false,
      isLoading: false,
      error: undefined,
      updatePrefs,
      isUpdating: false,
    });
    render(<NotificationSettings />);

    fireEvent.click(screen.getByLabelText(/email notifications/i));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /unable to save notification preferences/i,
    );
  });
});
