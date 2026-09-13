import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import IntegrationsPage from "./page";

/**
 * kita wave 2e — Drive card reconnect path.
 *
 * `connected` is a stored-token check, not a live one: is_connected() on the
 * backend never re-asks Google, so a grant revoked on Google's side still
 * reads "Connected" with the pre-cure card offering no way back. These tests
 * pin: connected always offers Reconnect (GUILT would be no button at all),
 * disconnected offers Connect (INNOCENCE: no Reconnect leaks into that
 * state), `configured: false` disables both and shows the admin message, and
 * an auth-url failure surfaces inline instead of silently resetting.
 */

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  get: vi.fn(),
  getAuthUrl: vi.fn(),
  error: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    get: mocks.get,
    drive: {
      getAuthUrl: mocks.getAuthUrl,
    },
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: mocks.error,
  },
}));

// jsdom throws "Not implemented: navigation" if a test lets the real
// assignment through; the redirect target is asserted, not followed.
function stubLocation() {
  // @ts-expect-error -- test-only stub
  delete window.location;
  // @ts-expect-error -- test-only stub
  window.location = { href: "" };
}

describe("Google Drive integration card (kita wave 2e)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("connected: offers Reconnect and clicking it calls the auth-url endpoint", async () => {
    stubLocation();
    mocks.get.mockResolvedValue({ connected: true, configured: true });
    mocks.getAuthUrl.mockResolvedValue({
      auth_url: "https://accounts.google.com/o/oauth2/auth",
    });

    render(<IntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Reconnect" });
    expect(screen.queryByRole("button", { name: "Connect" })).toBeNull();

    button.click();

    await waitFor(() => expect(mocks.getAuthUrl).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(window.location.href).toBe(
        "https://accounts.google.com/o/oauth2/auth",
      ),
    );
  });

  it("disconnected: offers Connect, not Reconnect", async () => {
    mocks.get.mockResolvedValue({ connected: false, configured: true });

    render(<IntegrationsPage />);

    await screen.findByRole("button", { name: "Connect" });
    expect(screen.queryByRole("button", { name: "Reconnect" })).toBeNull();
  });

  it("configured=false: disables the action and shows the admin message", async () => {
    mocks.get.mockResolvedValue({ connected: false, configured: false });

    render(<IntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Connect" });
    expect(button).toBeDisabled();
    expect(
      await screen.findByText(/OAuth is not configured on the server/i),
    ).toBeInTheDocument();
  });

  it("configured=false while connected: Reconnect is disabled too", async () => {
    mocks.get.mockResolvedValue({ connected: true, configured: false });

    render(<IntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Reconnect" });
    expect(button).toBeDisabled();
  });

  it("auth-url failure: shows an inline error instead of silently resetting", async () => {
    mocks.get.mockResolvedValue({ connected: false, configured: true });
    mocks.getAuthUrl.mockRejectedValue(new Error("service unavailable"));

    render(<IntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Connect" });
    button.click();

    await waitFor(() => expect(mocks.getAuthUrl).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText(/could not start the google drive connection/i),
    ).toBeInTheDocument();
    // The button must be usable again, not stuck on "Redirecting…".
    expect(
      await screen.findByRole("button", { name: "Connect" }),
    ).not.toBeDisabled();
  });
});
