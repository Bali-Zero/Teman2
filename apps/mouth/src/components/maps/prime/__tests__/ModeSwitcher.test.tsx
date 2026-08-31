import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const mocks = vi.hoisted(() => ({
  setMode: vi.fn(),
  hasSession: vi.fn(),
}));

vi.mock("@/contexts/PrimeNexusContext", () => ({
  usePrimeNexus: () => ({ mode: "invest", setMode: mocks.setMode }),
}));

vi.mock("@/lib/api", () => ({
  api: { hasSession: mocks.hasSession },
}));

import { ModeSwitcher } from "../ModeSwitcher";

describe("ModeSwitcher — cookie-primary auth gate (auth-gates-cookie-primary)", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    delete (window as { location?: Location }).location;
    (window as unknown as { location: Partial<Location> }).location = {
      href: "https://kita.balizero.com/prime",
    };
  });

  afterEach(() => {
    (window as unknown as { location: Location }).location = originalLocation;
  });

  // Innocence: a mode that doesn't require auth must never consult the
  // session probe at all — clicking "Invest" is not a gate.
  it("switches a no-auth-required mode directly, without probing the session", async () => {
    render(<ModeSwitcher />);
    await userEvent.click(screen.getByRole("button", { name: /invest/i }));

    expect(mocks.hasSession).not.toHaveBeenCalled();
    expect(mocks.setMode).toHaveBeenCalledWith("invest");
  });

  it("switches an auth-required mode when the session probe says authenticated", async () => {
    mocks.hasSession.mockResolvedValue("authenticated");
    render(<ModeSwitcher />);

    await userEvent.click(screen.getByRole("button", { name: /crm/i }));

    await waitFor(() => expect(mocks.setMode).toHaveBeenCalledWith("crm"));
    expect(mocks.hasSession).toHaveBeenCalled();
    expect(window.location.href).toBe("https://kita.balizero.com/prime");
  });

  it("redirects to login instead of switching when the probe says anonymous", async () => {
    mocks.hasSession.mockResolvedValue("anonymous");
    render(<ModeSwitcher />);

    await userEvent.click(screen.getByRole("button", { name: /crm/i }));

    await waitFor(() =>
      expect(window.location.href).toBe("/login?redirect=/prime"),
    );
    expect(mocks.setMode).not.toHaveBeenCalled();
  });

  // Fail-open: an inconclusive probe must not trap a real user behind a
  // dead network — this only gates a UI mode switch, not data (the domain
  // panel behind each mode still enforces its own 401 server-side).
  it("fails open (switches the mode) when the probe is inconclusive (unknown)", async () => {
    mocks.hasSession.mockResolvedValue("unknown");
    render(<ModeSwitcher />);

    await userEvent.click(screen.getByRole("button", { name: /intel/i }));

    await waitFor(() => expect(mocks.setMode).toHaveBeenCalledWith("intel"));
    expect(window.location.href).toBe("https://kita.balizero.com/prime");
  });
});
