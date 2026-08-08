import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceLayout from "./layout";

const {
  mockGetGateStatus,
  mockGetUserProfile,
  mockLocationReplace,
  mockRouterPush,
} = vi.hoisted(() => ({
  mockGetGateStatus: vi.fn(),
  mockGetUserProfile: vi.fn(),
  mockLocationReplace: vi.fn(),
  mockRouterPush: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
  usePathname: () => "/dashboard",
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ removeQueries: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getUserProfile: mockGetUserProfile,
    getProfile: vi.fn(),
    getGateStatus: mockGetGateStatus,
    logout: vi.fn(),
    isAdmin: () => true,
  },
}));

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
});
