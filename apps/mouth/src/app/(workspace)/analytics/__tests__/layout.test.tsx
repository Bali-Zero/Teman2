import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  getProfile: vi.fn(),
  hasSession: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush }),
}));

vi.mock("@/lib/api", () => ({
  api: { getProfile: mocks.getProfile, hasSession: mocks.hasSession },
}));

import AnalyticsLayout from "../layout";

describe("AnalyticsLayout — founder gate (auth-gates-cookie-primary)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("authorizes the founder on a successful profile load", async () => {
    mocks.getProfile.mockResolvedValue({ email: "zero@balizero.com" });

    render(
      <AnalyticsLayout>
        <div>Founder dashboard</div>
      </AnalyticsLayout>,
    );

    expect(mocks.getProfile).toHaveBeenCalledWith({
      redirectOnUnauthorized: false,
    });
    await waitFor(() => {
      expect(screen.getByText("Founder dashboard")).toBeInTheDocument();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("shows Access Denied for a successfully-loaded non-founder profile", async () => {
    mocks.getProfile.mockResolvedValue({ email: "someone@balizero.com" });

    render(
      <AnalyticsLayout>
        <div>Founder dashboard</div>
      </AnalyticsLayout>,
    );

    await waitFor(() => {
      expect(screen.getByText("Access Denied")).toBeInTheDocument();
    });
    expect(screen.queryByText("Founder dashboard")).not.toBeInTheDocument();
    expect(mocks.routerPush).not.toHaveBeenCalled();
    expect(mocks.hasSession).not.toHaveBeenCalled();
  });

  it("redirects to login when the profile loads but carries no email (malformed)", async () => {
    mocks.getProfile.mockResolvedValue({ email: "" });

    render(
      <AnalyticsLayout>
        <div>Founder dashboard</div>
      </AnalyticsLayout>,
    );

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(mocks.hasSession).not.toHaveBeenCalled();
  });

  // auth-gates-cookie-primary round 2 (spec §6-bis / §7.9): `/api/auth/profile`
  // is bearer-only (FastAPI 0.141.1 HTTPBearer answers 401 with no
  // Authorization header, even for a VALID cookie session) — a getProfile()
  // failure here is never proof the founder is anonymous.
  it("redirects to login when getProfile() fails AND the session probe says anonymous", async () => {
    mocks.getProfile.mockRejectedValue(new Error("Forbidden"));
    mocks.hasSession.mockResolvedValue("anonymous");

    render(
      <AnalyticsLayout>
        <div>Founder dashboard</div>
      </AnalyticsLayout>,
    );

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(mocks.hasSession).toHaveBeenCalled();
  });

  it("shows Access Denied (never redirects) when getProfile() fails but the session probe says authenticated — cookie-only founder", async () => {
    mocks.getProfile.mockRejectedValue(new Error("Forbidden"));
    mocks.hasSession.mockResolvedValue("authenticated");

    render(
      <AnalyticsLayout>
        <div>Founder dashboard</div>
      </AnalyticsLayout>,
    );

    await waitFor(() => {
      expect(screen.getByText("Access Denied")).toBeInTheDocument();
    });
    expect(mocks.routerPush).not.toHaveBeenCalledWith("/login");
    expect(screen.queryByText("Founder dashboard")).not.toBeInTheDocument();
  });
});
