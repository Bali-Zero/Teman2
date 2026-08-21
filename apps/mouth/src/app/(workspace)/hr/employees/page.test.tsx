/**
 * Defect 1 (2026-08-19 audit): the Add-Employee "Team Member" select used the
 * raw useTeamMembers() feed with zero role filtering — a client OR a service
 * account (e.g. the "monitoring" login-healthcheck probe) could be picked and
 * an admin could create an HR/payroll record for a machine.
 *
 * Guilt: neither a client nor a service-account role may appear in the select.
 * Innocence: a real, free-text team-role title still appears.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EmployeesPage from "./page";

const hrApiMock = vi.hoisted(() => ({
  listEmployees: vi.fn(),
  upsertEmployee: vi.fn(),
}));

vi.mock("@/lib/api/hr/hr", () => hrApiMock);

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const useTeamMembersMock = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useTeamMembers", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/useTeamMembers")>(
    "@/hooks/useTeamMembers",
  );
  return {
    ...actual,
    useTeamMembers: useTeamMembersMock,
  };
});

const TEAM_MEMBERS = [
  {
    id: "human-1",
    email: "reception@balizero.com",
    full_name: "Dea",
    name: "Dea",
    role: "Reception",
    avatar_url: null,
    avatar: null,
  },
  {
    id: "client-1",
    email: "client@example.com",
    full_name: "Client Example",
    name: "Client",
    role: "client",
    avatar_url: null,
    avatar: null,
  },
  {
    id: "probe-1",
    email: "probe@balizero.com",
    full_name: "Login Healthcheck Probe",
    name: "Probe",
    role: "monitoring",
    avatar_url: null,
    avatar: null,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  hrApiMock.listEmployees.mockResolvedValue({ employees: [] });
  useTeamMembersMock.mockReturnValue({ data: TEAM_MEMBERS, isLoading: false });
});

async function openForm() {
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: /add employee/i }),
  );
}

describe("EmployeesPage team-member select", () => {
  it("excludes clients and service accounts from the Team Member dropdown", async () => {
    render(<EmployeesPage />);
    await openForm();

    const select = await screen.findByRole("combobox", {
      name: /team member/i,
    });
    const optionLabels = Array.from(select.querySelectorAll("option")).map(
      (o) => o.textContent,
    );

    expect(optionLabels.some((label) => label?.includes("Dea"))).toBe(true);
    expect(
      optionLabels.some((label) => label?.includes("Client Example")),
    ).toBe(false);
    expect(
      optionLabels.some((label) => label?.includes("Login Healthcheck Probe")),
    ).toBe(false);
  });

  it("still offers a real human team member (innocence)", async () => {
    render(<EmployeesPage />);
    await openForm();

    const select = await screen.findByRole("combobox", {
      name: /team member/i,
    });
    await waitFor(() => {
      expect(select.querySelectorAll("option")).toHaveLength(2); // placeholder + Dea
    });
  });
});
