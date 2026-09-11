import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * auth-gates-cookie-primary — class-wide gate contract (spec §2 rows #1-8).
 *
 * All eight pages below used to gate on `api.isAuthenticated()` (a
 * local-token-only, positive-only signal — see client.ts docstring) and now
 * gate on `useSessionState()` (cookie-primary). The contract is the same for
 * every member of the class:
 *   - "anonymous"            -> router.push("/login")
 *   - "pending" | "unknown"  -> no push, no load (silent wait, never a
 *                               redirect flicker while the probe is inflight
 *                               or inconclusive)
 *   - "authenticated"        -> no push, the page proceeds to load (and, for
 *                               the admin-gated pages, to its isAdmin() check)
 */

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  sessionState: "authenticated" as
    "pending" | "authenticated" | "anonymous" | "unknown",
  api: {
    isAuthenticated: vi.fn(),
    isAdmin: vi.fn(),
    getTeamStatus: vi.fn(),
    getDailyHours: vi.fn(),
    getWeeklySummary: vi.fn(),
    exportTimesheet: vi.fn(),
    getSystemHealth: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    adminApi: {
      getTeamActivityOverview: vi.fn(),
      getTeamStats: vi.fn(),
      getTeamActivityMessages: vi.fn(),
      getTeamTimesheet: vi.fn(),
      getCrmActions: vi.fn(),
      exportMessages: vi.fn(),
    },
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush }),
  usePathname: () => "/",
}));

vi.mock("@/lib/api", () => ({ api: mocks.api }));

vi.mock("@/hooks/useSessionState", () => ({
  useSessionState: () => mocks.sessionState,
}));

vi.mock("@/lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsTrigger: ({ children }: { children?: React.ReactNode }) => (
    <button type="button">{children}</button>
  ),
  TabsContent: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

// Heavy children — presence-only stubs, irrelevant to the auth-gate contract.
vi.mock("@/components/cell/CellDashboard", () => ({
  CellDashboard: () => <div data-testid="cell-dashboard" />,
}));
vi.mock("@/components/admin/DbExplorer", () => ({
  DbExplorer: () => <div data-testid="db-explorer" />,
}));
vi.mock("@/components/admin/VectorExplorer", () => ({
  VectorExplorer: () => <div data-testid="vector-explorer" />,
}));
vi.mock("@/components/admin/ServiceHealthCard", () => ({
  ServiceHealthCard: () => <div data-testid="service-health-card" />,
}));
vi.mock("@/components/agents/AgentCard", () => ({
  AgentCard: () => <div data-testid="agent-card" />,
}));
vi.mock("@/components/agents/SchedulerStatus", () => ({
  SchedulerStatus: () => <div data-testid="scheduler-status" />,
}));

import CellPage from "../(workspace)/admin/cell/page";
import AdminPage from "../(workspace)/admin/page";
import SystemDashboardPage from "../(workspace)/admin/system/page";
import TeamActivityPage from "../(workspace)/admin/team-activity/page";
import RolesPermissionsPage from "../(workspace)/settings/roles/page";
import SecuritySettingsPage from "../(workspace)/settings/security/page";
import UserManagementPage from "../(workspace)/settings/users/page";
import AgentsPage from "../agents/page";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sessionState = "authenticated";
  // Legacy signal some pages still call pre-cure; a fixed `true` keeps that
  // call harmless without it ever being the thing a test asserts against —
  // see the file docstring above the gate contract.
  mocks.api.isAuthenticated.mockReturnValue(true);
  mocks.api.isAdmin.mockReturnValue(true);
  mocks.api.getTeamStatus.mockResolvedValue([]);
  mocks.api.getDailyHours.mockResolvedValue([]);
  mocks.api.getWeeklySummary.mockResolvedValue([]);
  mocks.api.getSystemHealth.mockResolvedValue({});
  mocks.api.get.mockResolvedValue({ agents: [] });
  mocks.api.adminApi.getTeamActivityOverview.mockResolvedValue({
    stats: {
      total_conversations: 0,
      total_messages: 0,
      total_team_members: 0,
      active_today: 0,
      messages_today: 0,
    },
    top_users: [],
  });
  mocks.api.adminApi.getTeamStats.mockResolvedValue({ team_stats: [] });
});

// #1 admin/cell/page.tsx — too entangled with CellDashboard for a clean
// content assertion (it renders CellDashboard unconditionally regardless of
// the gate); a contract-level push/no-push check is the declared scope here.
describe("admin/cell/page (gate #1)", () => {
  it("authenticated + admin: no redirect", async () => {
    render(<CellPage />);

    await waitFor(() => {
      expect(screen.getByTestId("cell-dashboard")).toBeInTheDocument();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login", async () => {
    mocks.sessionState = "anonymous";

    render(<CellPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect (silent wait)",
    async (state) => {
      mocks.sessionState = state;

      render(<CellPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
    },
  );
});

// #2 admin/page.tsx (team hours dashboard)
describe("admin/page.tsx (gate #2)", () => {
  it("authenticated + admin: no redirect, loads team data", async () => {
    render(<AdminPage />);

    await waitFor(() => {
      expect(mocks.api.getTeamStatus).toHaveBeenCalled();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, never loads", async () => {
    mocks.sessionState = "anonymous";

    render(<AdminPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(mocks.api.getTeamStatus).not.toHaveBeenCalled();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, no load",
    async (state) => {
      mocks.sessionState = state;

      render(<AdminPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(mocks.api.getTeamStatus).not.toHaveBeenCalled();
    },
  );

  // DECLARED RESIDUAL, pinned so a change here is a conscious one (refuter
  // finding, 2026-08-28; spec §7.1): a cookie-only ADMIN has no local
  // profile — `/api/auth/profile` is bearer-only and the JWT is httpOnly, so
  // `isAdmin()` cannot see their role. The class cure keeps them out of
  // /login (the mandate's gate), but the admin check still demotes them to
  // /chat. Curing THIS needs a cookie-compatible profile endpoint (backend —
  // out of this class cure's scope; tracked in PENDING-ARMS).
  it("authenticated but role unrecoverable (cookie-only admin): demoted to /chat, never /login", async () => {
    mocks.api.isAdmin.mockReturnValue(false);

    render(<AdminPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/chat");
    });
    expect(mocks.routerPush).not.toHaveBeenCalledWith("/login");
    expect(mocks.api.getTeamStatus).not.toHaveBeenCalled();
  });
});

// #3 admin/system/page.tsx (control room)
describe("admin/system/page.tsx (gate #3)", () => {
  it("authenticated + admin: no redirect, fetches system health", async () => {
    render(<SystemDashboardPage />);

    await waitFor(() => {
      expect(mocks.api.getSystemHealth).toHaveBeenCalled();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, never fetches", async () => {
    mocks.sessionState = "anonymous";

    render(<SystemDashboardPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(mocks.api.getSystemHealth).not.toHaveBeenCalled();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, stays on the VERIFYING ACCESS screen",
    async (state) => {
      mocks.sessionState = state;

      render(<SystemDashboardPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(mocks.api.getSystemHealth).not.toHaveBeenCalled();
      expect(screen.getByText("VERIFYING ACCESS...")).toBeInTheDocument();
    },
  );
});

// #4 admin/team-activity/page.tsx
describe("admin/team-activity/page.tsx (gate #4)", () => {
  it("authenticated + admin: no redirect, loads overview", async () => {
    render(<TeamActivityPage />);

    await waitFor(() => {
      expect(mocks.api.adminApi.getTeamActivityOverview).toHaveBeenCalled();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, never loads", async () => {
    mocks.sessionState = "anonymous";

    render(<TeamActivityPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(mocks.api.adminApi.getTeamActivityOverview).not.toHaveBeenCalled();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, no load",
    async (state) => {
      mocks.sessionState = state;

      render(<TeamActivityPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(mocks.api.adminApi.getTeamActivityOverview).not.toHaveBeenCalled();
    },
  );
});

// #5 settings/roles/page.tsx
describe("settings/roles/page.tsx (gate #5)", () => {
  it("authenticated + admin: no redirect, page renders", async () => {
    render(<RolesPermissionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Roles & Permissions")).toBeInTheDocument();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, renders nothing", async () => {
    mocks.sessionState = "anonymous";

    render(<RolesPermissionsPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(screen.queryByText("Roles & Permissions")).not.toBeInTheDocument();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, renders nothing yet",
    async (state) => {
      mocks.sessionState = state;

      render(<RolesPermissionsPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(screen.queryByText("Roles & Permissions")).not.toBeInTheDocument();
    },
  );
});

// #6 settings/security/page.tsx
describe("settings/security/page.tsx (gate #6)", () => {
  it("authenticated + admin: no redirect, page renders", async () => {
    render(<SecuritySettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Security Settings")).toBeInTheDocument();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, renders nothing", async () => {
    mocks.sessionState = "anonymous";

    render(<SecuritySettingsPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(screen.queryByText("Security Settings")).not.toBeInTheDocument();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, renders nothing yet",
    async (state) => {
      mocks.sessionState = state;

      render(<SecuritySettingsPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(screen.queryByText("Security Settings")).not.toBeInTheDocument();
    },
  );
});

// #7 settings/users/page.tsx
describe("settings/users/page.tsx (gate #7)", () => {
  it("authenticated + admin: no redirect, page renders and loads users", async () => {
    render(<UserManagementPage />);

    await waitFor(() => {
      expect(screen.getByText("User Management")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(mocks.api.getTeamStatus).toHaveBeenCalled();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, renders nothing, never loads", async () => {
    mocks.sessionState = "anonymous";

    render(<UserManagementPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(screen.queryByText("User Management")).not.toBeInTheDocument();
    expect(mocks.api.getTeamStatus).not.toHaveBeenCalled();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, renders nothing yet, no load",
    async (state) => {
      mocks.sessionState = state;

      render(<UserManagementPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(screen.queryByText("User Management")).not.toBeInTheDocument();
      expect(mocks.api.getTeamStatus).not.toHaveBeenCalled();
    },
  );
});

// #8 agents/page.tsx — auth-only gate, no admin branch.
describe("agents/page.tsx (gate #8)", () => {
  it("authenticated: no redirect, loads agents + scheduler status", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(mocks.api.get).toHaveBeenCalled();
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("anonymous: redirects to /login, never loads", async () => {
    mocks.sessionState = "anonymous";

    render(<AgentsPage />);

    await waitFor(() => {
      expect(mocks.routerPush).toHaveBeenCalledWith("/login");
    });
    expect(mocks.api.get).not.toHaveBeenCalled();
  });

  it.each(["pending", "unknown"] as const)(
    "%s: no redirect, no load",
    async (state) => {
      mocks.sessionState = state;

      render(<AgentsPage />);
      await Promise.resolve();

      expect(mocks.routerPush).not.toHaveBeenCalled();
      expect(mocks.api.get).not.toHaveBeenCalled();
    },
  );
});
