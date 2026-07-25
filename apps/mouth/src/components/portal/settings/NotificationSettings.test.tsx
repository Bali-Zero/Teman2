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
    });
    render(<NotificationSettings />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders migration-missing banner when hook signals 503", () => {
    hookMock.mockReturnValue({
      data: null,
      migrationMissing: true,
      isLoading: false,
      error: undefined,
      updatePrefs: vi.fn(),
    });
    render(<NotificationSettings />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /temporarily unavailable/i,
    );
    // No toggles should be rendered in degraded state.
    expect(screen.queryByLabelText(/email notifications/i)).toBeNull();
  });

  it("renders toggles and fires updatePrefs on change", () => {
    const updatePrefs = vi.fn();
    hookMock.mockReturnValue({
      data: { email_enabled: true, wa_enabled: false, wa_phone: null },
      migrationMissing: false,
      isLoading: false,
      error: undefined,
      updatePrefs,
    });
    render(<NotificationSettings />);

    const email = screen.getByLabelText(/email notifications/i);
    expect(email).toBeChecked();

    const wa = screen.getByLabelText(/whatsapp notifications/i);
    fireEvent.click(wa);

    expect(updatePrefs).toHaveBeenCalledWith({
      email_enabled: true,
      wa_enabled: true,
      wa_phone: null,
    });
  });

  it("reads theme tokens for toggles, input and notice (WS3 day pass)", () => {
    hookMock.mockReturnValue({
      data: { email_enabled: true, wa_enabled: true, wa_phone: "6281" },
      migrationMissing: false,
      isLoading: false,
      error: undefined,
      updatePrefs: vi.fn(),
    });
    const { container } = render(<NotificationSettings />);

    // Toggle accent reads the daylight copper step (was accent-[#d4845a]).
    const email = screen.getByLabelText(/email notifications/i);
    expect(email.className).toContain("accent-[var(--bz-copper)]");

    // WhatsApp number input: token well + border + ink (was
    // bg-white/5 + border-white/10 + #f0ece4).
    const input = screen.getByLabelText(/whatsapp number/i);
    expect(input.className).toContain("bg-[var(--glass-rim)]");
    expect(input.className).toContain("border-[var(--bz-border)]");
    expect(input.className).toContain("text-[var(--bz-text-1)]");

    // Drain guard: no hardcoded hex colors in the panel.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("colors the migration-missing banner with the warning token", () => {
    hookMock.mockReturnValue({
      data: null,
      migrationMissing: true,
      isLoading: false,
      error: undefined,
      updatePrefs: vi.fn(),
    });
    render(<NotificationSettings />);
    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("text-[var(--state-warning)]");
  });
});
