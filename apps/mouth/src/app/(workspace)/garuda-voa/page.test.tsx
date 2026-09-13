import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import GarudaVoaStaffListPage from "./page";
import type { StaffPracticeListResponse } from "./types";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getProfile: vi.fn(),
  isAdmin: vi.fn(),
  listStaffPractices: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: mocks.getProfile,
    isAdmin: mocks.isAdmin,
  },
}));

vi.mock("./api-client", () => ({
  listStaffPractices: mocks.listStaffPractices,
}));

const ADMIN_ROW: StaffPracticeListResponse["items"][number] = {
  practice_id: "practice_1",
  order_id: "order_1",
  state: "Received",
  assigned_to: null,
  updated_at: "2026-08-01T10:00:00Z",
  artifact_available: false,
};

const TEAM_ROW: StaffPracticeListResponse["items"][number] = {
  practice_id: "practice_2",
  order_id: "order_2",
  state: "In review",
  assigned_to: "team@balizero.com",
  updated_at: "2026-08-02T10:00:00Z",
  artifact_available: false,
};

describe("GarudaVoaStaffListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getProfile.mockResolvedValue({ email: "zero@balizero.com" });
  });

  it("shows the assigned filter and all rows for an admin", async () => {
    mocks.isAdmin.mockReturnValue(true);
    mocks.listStaffPractices.mockResolvedValue({
      items: [ADMIN_ROW, TEAM_ROW],
      next_cursor: null,
    });

    render(<GarudaVoaStaffListPage />);

    await waitFor(() =>
      expect(screen.getByTestId("garuda-voa-row-practice_1")).toBeTruthy(),
    );
    expect(screen.getByTestId("garuda-voa-row-practice_2")).toBeTruthy();
    expect(screen.getByLabelText("Assigned")).toBeTruthy();
    expect(mocks.listStaffPractices).toHaveBeenCalledWith(
      expect.objectContaining({ assigned: "all" }),
    );
  });

  it("hides the assigned filter and forces assigned=me for a non-admin team member", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.listStaffPractices.mockResolvedValue({
      items: [TEAM_ROW],
      next_cursor: null,
    });

    render(<GarudaVoaStaffListPage />);

    await waitFor(() =>
      expect(screen.getByTestId("garuda-voa-row-practice_2")).toBeTruthy(),
    );
    expect(screen.queryByLabelText("Assigned")).toBeNull();
    expect(mocks.listStaffPractices).toHaveBeenCalledWith(
      expect.objectContaining({ assigned: "me" }),
    );
  });

  it("renders an empty state when there are no practices", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.listStaffPractices.mockResolvedValue({
      items: [],
      next_cursor: null,
    });

    render(<GarudaVoaStaffListPage />);

    await waitFor(() => expect(screen.getByText("No practices")).toBeTruthy());
  });
});
