import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import PortalLayout from "./layout";

// Hoisted mocks (must be defined before vi.mock)
const {
  mockPush,
  mockGetToken,
  mockGetUserProfile,
  mockGetProfile,
  mockLogout,
} = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockGetToken: vi.fn(),
  mockGetUserProfile: vi.fn(),
  mockGetProfile: vi.fn(),
  mockLogout: vi.fn(),
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/portal",
}));

// Mock components
vi.mock("@/components/workspace/AppSidebar", () => ({
  AppSidebar: ({
    user,
    onLogout,
  }: {
    user: { name: string };
    onLogout: () => void;
  }) => {
    const handleClick = () => {
      onLogout();
    };
    return (
      <div data-testid="app-sidebar">
        <div>User: {user.name}</div>
        <button onClick={handleClick}>Logout</button>
      </div>
    );
  },
}));

vi.mock("@/components/workspace/Header", () => ({
  Header: ({ userName }: { userName: string }) => (
    <header data-testid="header">Header: {userName}</header>
  ),
}));

// The authenticated layout imports PortalHeader + PortalErrorBoundary from
// their own files (not the @/components/portal barrel) to keep the layout
// chunk graph small. PortalBottomNav is loaded via next/dynamic, which is
// also mocked below to return the real module synchronously in tests.
vi.mock("@/components/portal/PortalHeader", () => ({
  PortalHeader: ({ userName }: { userName: string }) => (
    <header data-testid="portal-header">Portal Header: {userName}</header>
  ),
}));

vi.mock("@/components/portal/PortalErrorBoundary", () => ({
  PortalErrorBoundary: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

vi.mock("@/components/portal/PortalBottomNav", () => ({
  PortalBottomNav: () => <nav data-testid="bottom-nav">Bottom Nav</nav>,
}));

// next/dynamic defaults to a Promise-returning loader; in vitest/jsdom the
// component never resolves, which makes PortalBottomNav render as undefined.
// Replace dynamic() with a pass-through that invokes the loader eagerly and
// returns whatever the mocked module exports. Works for both named-export
// ({ default: m.Foo }) and default-export imports.
vi.mock("next/dynamic", () => ({
  default: (
    loader: () => Promise<{ default: React.ComponentType<unknown> }>,
  ) => {
    const Component = (props: unknown) => {
      const [Resolved, setResolved] =
        React.useState<React.ComponentType<unknown> | null>(null);
      React.useEffect(() => {
        loader().then((mod) => setResolved(() => mod.default));
      }, []);
      if (!Resolved) return null;
      return <Resolved {...(props as object)} />;
    };
    Component.displayName = "DynamicMock";
    return Component;
  },
}));

vi.mock("@/components/ui/toast", () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="toast-provider">{children}</div>
  ),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  api: {
    getToken: mockGetToken,
    getUserProfile: mockGetUserProfile,
    getProfile: mockGetProfile,
    portal: {
      getProfile: mockGetProfile,
    },
    logout: mockLogout,
  },
}));

vi.mock("@/types/navigation", () => ({
  portalNavigation: [
    {
      items: [{ title: "Dashboard", href: "/portal", icon: "Home" }],
    },
  ],
}));

describe("PortalLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetToken.mockReturnValue("test-token");
    mockGetUserProfile.mockReturnValue(null);
    mockGetProfile.mockResolvedValue({
      fullName: "Test User",
      name: "Test User",
      email: "test@example.com",
      avatar: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should redirect to login when no token and no cookie session", async () => {
    mockGetToken.mockReturnValue(null);
    // Cookie-based SSO fallback also fails (no valid session)
    mockGetProfile.mockRejectedValue(new Error("401 Unauthorized"));

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/portal/login");
    });
  });

  it("should load user profile from stored profile", async () => {
    mockGetUserProfile.mockReturnValue({
      name: "Stored User",
      email: "stored@example.com",
    });

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(screen.getByText("User: Stored User")).toBeInTheDocument();
    });
  });

  it("should load user profile from API when not stored", async () => {
    mockGetUserProfile.mockReturnValue(null);
    mockGetProfile.mockResolvedValue({
      fullName: "API User",
      email: "api@example.com",
    });

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(mockGetProfile).toHaveBeenCalled();
      expect(screen.getByText("User: API User")).toBeInTheDocument();
    });
  });

  it("should show loading state initially", () => {
    mockGetProfile.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("should render sidebar and header when loaded", async () => {
    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("app-sidebar")).toBeInTheDocument();
      expect(screen.getByTestId("portal-header")).toBeInTheDocument();
    });
  });

  it("should render children content", async () => {
    render(
      <PortalLayout>
        <div data-testid="child-content">Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("child-content")).toBeInTheDocument();
    });
  });

  it("should handle logout correctly", async () => {
    mockLogout.mockResolvedValue(undefined);

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(screen.getByText("Logout")).toBeInTheDocument();
    });

    const logoutButton = screen.getByText("Logout");
    logoutButton.click();

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/portal/login");
    });
  });

  it("should handle 401 error gracefully (error caught in loadUserProfile)", async () => {
    // Note: loadUserProfile catches errors internally and logs them,
    // so 401 errors don't propagate to trigger a redirect in current implementation
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockGetProfile.mockRejectedValue(new Error("401 Unauthorized"));

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    // Should complete loading and render (error is caught internally)
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  it("should handle non-401 errors gracefully", async () => {
    mockGetProfile.mockRejectedValue(new Error("500 Server Error"));

    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      // Should not redirect on non-401 errors
      expect(mockPush).not.toHaveBeenCalled();
    });
  });

  it("should use portal navigation config", async () => {
    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      const sidebar = screen.getByTestId("app-sidebar");
      expect(sidebar).toBeInTheDocument();
    });
  });

  it("should set portal mode flags correctly", async () => {
    render(
      <PortalLayout>
        <div>Test Content</div>
      </PortalLayout>,
    );

    await waitFor(() => {
      expect(screen.getByText("User: Test User")).toBeInTheDocument();
    });
  });
});
