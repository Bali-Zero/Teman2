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
  mockLocationReplace,
  mockRouterPush,
  mockLogger,
} = vi.hoisted(() => ({
  mockGetGateStatus: vi.fn(),
  mockGetUserProfile: vi.fn(),
  mockGetProfile: vi.fn(),
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
});
