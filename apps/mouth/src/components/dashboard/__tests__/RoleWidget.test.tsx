import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoleWidget } from "../RoleWidget";
import * as useRoleMetricsModule from "@/hooks/useRoleMetrics";

// Mock useRoleMetrics to avoid real API calls
vi.mock("@/hooks/useRoleMetrics", () => ({
  useRoleMetrics: vi.fn(() => ({
    data: {
      role: "zero",
      metrics: {
        revenue_mtd: 48200,
        visti_scadenza: 3,
        fatture_overdue: 2,
        agenti_count: 46,
        fly_uptime: 99.9,
      },
      alerts: [],
    },
    isLoading: false,
    isError: false,
  })),
}));

describe("RoleWidget", () => {
  it("renders violet glass card wrapper", () => {
    const { container } = render(<RoleWidget role="zero" userId="user-1" />);
    expect(container.firstChild).toHaveClass("glass-violet");
  });

  it("renders REVENUE label for Zero role", () => {
    render(<RoleWidget role="zero" userId="user-1" />);
    expect(screen.getByText("Revenue · MTD")).toBeInTheDocument();
  });

  it("renders skeleton when loading", () => {
    vi.mocked(useRoleMetricsModule.useRoleMetrics).mockReturnValueOnce({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    const { container } = render(<RoleWidget role="team" userId="user-2" />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
  });

  it("renders error state on failure", () => {
    vi.mocked(useRoleMetricsModule.useRoleMetrics).mockReturnValueOnce({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    render(<RoleWidget role="team" userId="user-2" />);
    expect(screen.getByText(/errore/i)).toBeInTheDocument();
  });
});
