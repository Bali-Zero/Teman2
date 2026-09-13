import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import GarudaVoaStaffDetailPage from "./page";
import type { StaffPracticeView } from "../types";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  useParams: vi.fn(),
  getProfile: vi.fn(),
  isAdmin: vi.fn(),
  getStaffPractice: vi.fn(),
  transitionPractice: vi.fn(),
  assignPractice: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  useGarudaAssignmentTargets: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: mocks.useParams,
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: mocks.getProfile,
    isAdmin: mocks.isAdmin,
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: mocks.toastSuccess,
    error: mocks.toastError,
  }),
}));

// The picker's source is the assignment gate's own enumeration, not the shared
// CRM roster hook it replaced. Mocked whole, as that hook was: these tests
// render the page without a QueryClientProvider.
vi.mock("../assignment-targets", () => ({
  useGarudaAssignmentTargets: mocks.useGarudaAssignmentTargets,
}));

vi.mock("../api-client", async () => {
  const actual =
    await vi.importActual<typeof import("../api-client")>("../api-client");
  return {
    ...actual,
    getStaffPractice: mocks.getStaffPractice,
    transitionPractice: mocks.transitionPractice,
    assignPractice: mocks.assignPractice,
  };
});

const RECEIVED_PRACTICE: StaffPracticeView = {
  practice_id: "practice_1",
  order_id: "order_1",
  state: "Received",
  assigned_to: null,
  updated_at: "2026-08-01T10:00:00Z",
  artifact_available: false,
  private_staff_note: null,
  resume_target: null,
  active_block_id: null,
};

const BLOCKED_PRACTICE: StaffPracticeView = {
  ...RECEIVED_PRACTICE,
  state: "Blocked",
  resume_target: "In review",
  active_block_id: "block_abc123",
};

// Only the six fields required by the frozen StaffPracticeView contract.
const MINIMUM_PRACTICE: StaffPracticeView = {
  practice_id: "practice_1",
  order_id: "order_1",
  state: "Blocked",
  assigned_to: null,
  updated_at: "2026-08-01T10:00:00Z",
  artifact_available: false,
};

describe("GarudaVoaStaffDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useParams.mockReturnValue({ practiceId: "practice_1" });
    mocks.getProfile.mockResolvedValue({ email: "zero@balizero.com" });
    mocks.useGarudaAssignmentTargets.mockReturnValue({
      data: [{ email: "zero@balizero.com", label: "Zero" }],
      isError: false,
    });
  });

  it("renders only the transitions valid for the current state (Received)", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByTestId("transition-PR-02")).toBeTruthy(),
    );
    expect(screen.getByTestId("transition-PR-03")).toBeTruthy();
    // Not offered from Received: submit/approve/reject/resume/deliver.
    expect(screen.queryByTestId("transition-PR-04")).toBeNull();
    expect(screen.queryByTestId("transition-PR-06")).toBeNull();
    expect(screen.queryByTestId("transition-PR-11")).toBeNull();
  });

  it("renders a contract-minimum response without optional notes or a resume target", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(MINIMUM_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "practice_1" }),
    ).toBeVisible();
    expect(screen.queryByText("Private staff note")).toBeNull();
    expect(
      screen.getByText("No transitions are available from this state."),
    ).toBeVisible();
    expect(screen.queryByTestId("transition-PR-09")).toBeNull();
    expect(screen.queryByTestId("transition-PR-10")).toBeNull();
  });

  it("narrows a Blocked practice to the single resume transition matching resume_target", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(BLOCKED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByTestId("transition-PR-09")).toBeTruthy(),
    );
    // resume_target is "In review" -> PR-09 only, never PR-10.
    expect(screen.queryByTestId("transition-PR-10")).toBeNull();
  });

  it("prefills resolved_block_id read-only from active_block_id and sends it verbatim on resume", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(BLOCKED_PRACTICE);
    mocks.transitionPractice.mockResolvedValue({
      practice: {
        practice_id: "practice_1",
        state: "In review",
        artifact_available: false,
      },
      replayed: false,
    });

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByTestId("transition-PR-09")).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("transition-PR-09"));

    const blockIdField = screen.getByLabelText(
      "Resolved block id",
    ) as HTMLInputElement;
    expect(blockIdField.value).toBe("block_abc123");
    expect(blockIdField.readOnly).toBe(true);

    fireEvent.click(screen.getByText("Apply"));

    await waitFor(() =>
      expect(mocks.transitionPractice).toHaveBeenCalledWith(
        expect.objectContaining({
          request: {
            transition_id: "PR-09",
            resolved_block_id: "block_abc123",
          },
        }),
      ),
    );
  });

  it("shows the assignment select only for admins", async () => {
    mocks.isAdmin.mockReturnValue(true);
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByLabelText("Assigned to")).toBeTruthy(),
    );
  });

  it("does not show the assignment select for a non-admin", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByTestId("transition-PR-02")).toBeTruthy(),
    );
    expect(screen.queryByLabelText("Assigned to")).toBeNull();
  });

  it("applies a no-body transition (PR-02) and reports Idempotency-Replayed on retry", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);
    mocks.transitionPractice.mockResolvedValue({
      practice: {
        practice_id: "practice_1",
        state: "In review",
        artifact_available: false,
      },
      replayed: true,
    });

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByTestId("transition-PR-02")).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("transition-PR-02"));
    fireEvent.click(screen.getByText("Apply"));

    await waitFor(() =>
      expect(mocks.transitionPractice).toHaveBeenCalledWith(
        expect.objectContaining({
          practiceId: "practice_1",
          request: { transition_id: "PR-02" },
        }),
      ),
    );
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Already applied",
      expect.stringContaining("In review"),
    );
  });

  it("fills the picker from the assignment gate's own enumeration", async () => {
    mocks.isAdmin.mockReturnValue(true);
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    const select = (await screen.findByLabelText(
      "Assigned to",
    )) as HTMLSelectElement;
    await waitFor(() =>
      expect(
        select.querySelector('option[value="zero@balizero.com"]'),
      ).toBeTruthy(),
    );
    expect(mocks.useGarudaAssignmentTargets).toHaveBeenCalledWith(true);
  });

  it("never runs the picker query for a non-admin (the endpoint would 403)", async () => {
    mocks.isAdmin.mockReturnValue(false);
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    await waitFor(() =>
      expect(screen.getByTestId("transition-PR-02")).toBeTruthy(),
    );
    expect(mocks.useGarudaAssignmentTargets).toHaveBeenCalledWith(false);
  });

  it("shows an assignee the gate refuses as a disabled option rather than pretending the practice is unassigned", async () => {
    mocks.isAdmin.mockReturnValue(true);
    mocks.getStaffPractice.mockResolvedValue({
      ...RECEIVED_PRACTICE,
      assigned_to: "read-only@example.test",
    });

    render(<GarudaVoaStaffDetailPage />);

    const select = (await screen.findByLabelText(
      "Assigned to",
    )) as HTMLSelectElement;
    const current = select.querySelector(
      'option[value="read-only@example.test"]',
    ) as HTMLOptionElement | null;
    await waitFor(() => expect(current).toBeTruthy());
    expect(current?.disabled).toBe(true);
    expect(current?.textContent).toContain("not assignable");
    // the control must not fall back to "Unassigned" while a real assignment
    // exists — that is the lie this option exists to prevent
    await waitFor(() => expect(select.value).toBe("read-only@example.test"));
  });

  it("says when the assignee list could not be fetched instead of offering an empty picker", async () => {
    mocks.isAdmin.mockReturnValue(true);
    mocks.useGarudaAssignmentTargets.mockReturnValue({
      data: undefined,
      isError: true,
    });
    mocks.getStaffPractice.mockResolvedValue(RECEIVED_PRACTICE);

    render(<GarudaVoaStaffDetailPage />);

    expect(await screen.findByText(/Assignee list unavailable/)).toBeVisible();
  });
});
