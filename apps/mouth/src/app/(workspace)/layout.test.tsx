import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceLayout from "./layout";
// Resolves to the mock below, which re-exports the REAL ApiError class — so
// `instanceof` in the layout compares against the same class this test throws.
import { ApiError } from "@/lib/api";

const {
  mockGetGateStatus,
  mockGetUserProfile,
  mockGetProfile,
  mockHasSession,
  mockLocationReplace,
  mockRouterPush,
  mockLogger,
} = vi.hoisted(() => ({
  mockGetGateStatus: vi.fn(),
  mockGetUserProfile: vi.fn(),
  mockGetProfile: vi.fn(),
  // Cookie-only session probe (auth-gates-cookie-primary). Default resolves
  // "anonymous" so a test that forgets to set it fails LOUD (a redirect) —
  // never silently falls into the new "stay on the page" branch.
  mockHasSession: vi.fn().mockResolvedValue("anonymous"),
  mockLocationReplace: vi.fn(),
  mockRouterPush: vi.fn(),
  mockLogger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Level is the assertion, not "did it log": warn and error BOTH forward to
// Sentry, debug does not (logger.ts). A test that only checked "logged" would
// pass with the pre-cure behaviour too.
vi.mock("@/lib/logger", () => ({ logger: mockLogger }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
  usePathname: () => "/dashboard",
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ removeQueries: vi.fn() }),
}));

// `ApiError` is re-exported REAL, not stubbed: the layout's 401 branch does
// `error instanceof ApiError`, and a mock that omits it makes that expression
// `x instanceof undefined` — a TypeError, not a false. A stub class would be
// worse than nothing: it would pass while production compares a different
// class. Import it from the module that DEFINES it, so pulling in the real
// "@/lib/api" barrel (and its client side effects) is not required.
vi.mock("@/lib/api", async () => {
  const { ApiError } = await vi.importActual<
    typeof import("@/lib/api/error-handler")
  >("@/lib/api/error-handler");
  return {
    ApiError,
    api: {
      getUserProfile: mockGetUserProfile,
      getProfile: mockGetProfile,
      getGateStatus: mockGetGateStatus,
      hasSession: mockHasSession,
      logout: vi.fn(),
      isAdmin: () => true,
    },
  };
});

vi.mock("@/hooks/useCellStatus", () => ({
  useCellStatus: () => ({
    loading: false,
    status: {
      alive: true,
      last_pulse: {
        pulse_number: 42,
        health_status: "green",
        response_time_ms: 18,
        budget_spent: 1,
        budget_limit: 10,
        action_taken: "Observing",
      },
    },
  }),
}));

vi.mock("@/components/workspace/AppSidebar", () => ({
  AppSidebar: () => <aside aria-label="Primary" />,
}));

vi.mock("@/components/workspace/Header", () => ({
  Header: () => <header />,
}));

vi.mock("@/components/workspace/ZantaraWidget", () => ({
  ZantaraWidget: () => null,
}));

vi.mock("@/components/workspace/KitaCommandPalette", () => ({
  KitaCommandPalette: () => null,
}));

vi.mock("@/components/ui/toast", () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/i18n", () => ({
  I18nProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/components/optimization", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/hooks/useDashboardData", () => ({
  removeDashboardQueries: vi.fn(),
}));

describe("WorkspaceLayout CELL access", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    delete (window as { location?: Location }).location;
    (window as unknown as { location: Partial<Location> }).location = {
      hostname: "kita.balizero.com",
      href: "https://kita.balizero.com/dashboard",
      replace: mockLocationReplace,
    };
    delete process.env.NEXT_PUBLIC_HIDE_CELL_WIDGET;
    mockGetUserProfile.mockReturnValue({
      name: "Zero",
      email: "zero@balizero.com",
      role: "admin",
      team: "Management",
    });
    mockGetGateStatus.mockResolvedValue({
      blocked: false,
      sections: { documents: { count: 0 } },
    });
  });

  afterEach(() => {
    delete (window as { location?: Location }).location;
    (window as unknown as { location: Location }).location = originalLocation;
    delete process.env.NEXT_PUBLIC_HIDE_CELL_WIDGET;
    vi.clearAllMocks();
  });

  it("keeps the admin CELL entry point mounted by default", async () => {
    render(
      <WorkspaceLayout>
        <div>Dashboard content</div>
      </WorkspaceLayout>,
    );

    expect(
      await screen.findByTitle("CELL — Pulse #42 — GREEN"),
    ).toBeInTheDocument();
  });

  it("can hide the floating CELL control during visual browser runs", async () => {
    process.env.NEXT_PUBLIC_HIDE_CELL_WIDGET = "1";

    render(
      <WorkspaceLayout>
        <div>Dashboard content</div>
      </WorkspaceLayout>,
    );

    await waitFor(() => {
      expect(screen.getByText("Dashboard content")).toBeInTheDocument();
    });
    expect(
      screen.queryByTitle("CELL — Pulse #42 — GREEN"),
    ).not.toBeInTheDocument();
  });

  it("uses a full cross-origin navigation when a client lands on kita", async () => {
    mockGetUserProfile.mockReturnValue({
      name: "Portal Client",
      email: "portal-client@example.test",
      role: "client",
      team: "Client",
    });

    render(
      <WorkspaceLayout>
        <div>Workspace must not render</div>
      </WorkspaceLayout>,
    );

    await waitFor(() => {
      expect(mockLocationReplace).toHaveBeenCalledWith(
        "https://my.balizero.com/portal",
      );
    });
    expect(mockRouterPush).not.toHaveBeenCalledWith("/portal");
    expect(mockGetGateStatus).not.toHaveBeenCalled();
  });

  // Measured 2026-08-28 on /whatsapp: every anonymous visit logged the expected
  // 401 at ERROR, which forwards to Sentry — the flood made Sentry answer 429,
  // dropping REAL events. These two tests pin the classification: an expected
  // 401 must not reach a Sentry-forwarding level, and a GENUINE failure still
  // must. Both drive the real catch block, so they also exercise
  // `error instanceof ApiError` against the real class.
  describe("profile-load failures are classified, not silenced", () => {
    beforeEach(() => {
      // Force the fallback path: no cached profile, so getProfile() is awaited.
      mockGetUserProfile.mockReturnValue(null);
    });

    it("logs an anonymous visitor's 401 at debug, never at error", async () => {
      mockGetProfile.mockRejectedValue(
        new ApiError("Authentication required", 401),
      );

      render(
        <WorkspaceLayout>
          <div>Workspace must not render</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(mockLogger.debug).toHaveBeenCalled();
      });
      expect(mockLogger.error).not.toHaveBeenCalled();
      expect(mockLogger.warn).not.toHaveBeenCalled();
    });

    it("still logs a genuine profile failure at error", async () => {
      mockGetProfile.mockRejectedValue(new ApiError("Server exploded", 500));

      render(
        <WorkspaceLayout>
          <div>Workspace must not render</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(mockLogger.error).toHaveBeenCalled();
      });
    });
  });

  // auth-gates-cookie-primary (spec §4 #12; round 2 spec §6-bis): the outer
  // catch used to treat ANY loadUserProfile() failure as "not logged in".
  // `/api/auth/profile` is bearer-only (HTTPBearer strict) and — measured
  // 2026-08-29 against the locked FastAPI 0.141.1 — answers **401**, not
  // 403, to a request with no Authorization header, even one carrying a
  // VALID cookie session (the §1 "403" was wrong for this version). So
  // NEITHER a 401 NOR a 403 from getProfile can be trusted as "anonymous"
  // on its own: only hasSession() can tell. The gate now asks it
  // unconditionally, on every getProfile() failure.
  describe("cookie-only session fallback (auth-gates-cookie-primary)", () => {
    beforeEach(() => {
      // Force the fallback path: no cached profile, so getProfile() is awaited.
      mockGetUserProfile.mockReturnValue(null);
    });

    it("calls getProfile with redirectOnUnauthorized: false (the outer catch decides the redirect, not getProfile's own 401 handler)", async () => {
      mockGetProfile.mockRejectedValue(new ApiError("Forbidden", 403));
      mockHasSession.mockResolvedValue("authenticated");

      render(
        <WorkspaceLayout>
          <div>Workspace content</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(mockGetProfile).toHaveBeenCalledWith({
          redirectOnUnauthorized: false,
        });
      });
    });

    it("does not redirect a cookie-only session: getProfile() 403 + hasSession() authenticated", async () => {
      mockGetProfile.mockRejectedValue(new ApiError("Forbidden", 403));
      mockHasSession.mockResolvedValue("authenticated");

      render(
        <WorkspaceLayout>
          <div>Workspace content</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(mockGetGateStatus).toHaveBeenCalled();
      });
      expect(window.location.href).toBe("https://kita.balizero.com/dashboard");
      await waitFor(() => {
        expect(screen.getByText("Workspace content")).toBeInTheDocument();
      });
    });

    it("still redirects when the probe itself says anonymous: getProfile() 403 + hasSession() anonymous", async () => {
      mockGetProfile.mockRejectedValue(new ApiError("Forbidden", 403));
      mockHasSession.mockResolvedValue("anonymous");

      render(
        <WorkspaceLayout>
          <div>Workspace must not render</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(window.location.href).toEqual(expect.stringContaining("/login"));
      });
      expect(mockHasSession).toHaveBeenCalled();
      expect(mockGetGateStatus).not.toHaveBeenCalled();
    });

    // Round 2: FastAPI 0.141.1 answers 401 (not 403) to a bearer-only route
    // hit with no Authorization header — so a confirmed 401 from getProfile
    // is now ALSO not proof of anonymity. This replaces the round-1 test
    // that pinned the opposite (401 used to skip the probe entirely).
    it("still redirects on a confirmed 401 when the probe also says anonymous", async () => {
      mockGetProfile.mockRejectedValue(
        new ApiError("Authentication required", 401),
      );
      mockHasSession.mockResolvedValue("anonymous");

      render(
        <WorkspaceLayout>
          <div>Workspace must not render</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(window.location.href).toEqual(expect.stringContaining("/login"));
      });
      expect(mockHasSession).toHaveBeenCalled();
      expect(mockGetGateStatus).not.toHaveBeenCalled();
    });

    it("does not redirect a cookie-only visitor even on a bearer-only 401: getProfile() 401 + hasSession() authenticated", async () => {
      mockGetProfile.mockRejectedValue(
        new ApiError("Authentication required", 401),
      );
      mockHasSession.mockResolvedValue("authenticated");

      render(
        <WorkspaceLayout>
          <div>Workspace content</div>
        </WorkspaceLayout>,
      );

      await waitFor(() => {
        expect(mockGetGateStatus).toHaveBeenCalled();
      });
      expect(window.location.href).toBe("https://kita.balizero.com/dashboard");
      await waitFor(() => {
        expect(screen.getByText("Workspace content")).toBeInTheDocument();
      });
    });
  });
});
