import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Practice } from "@/lib/api/crm/crm.types";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  push: vi.fn(),
  useParams: vi.fn(),
  getProfile: vi.fn(),
  getPractice: vi.fn(),
  updatePractice: vi.fn(),
  deletePractice: vi.fn(),
  isAdmin: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  sonnerSuccess: vi.fn(),
  sonnerError: vi.fn(),
  loggerError: vi.fn(),
  loggerInfo: vi.fn(),
  trackPageView: vi.fn(),
  startPerformanceMark: vi.fn(),
  endPerformanceMark: vi.fn(),
  trackApiCall: vi.fn(),
  trackError: vi.fn(),
  trackButtonClick: vi.fn(),
  trackModal: vi.fn(),
  trackCaseUpdate: vi.fn(),
  trackQuickAction: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: mocks.useParams,
  useRouter: () => ({
    back: mocks.back,
    push: mocks.push,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: mocks.getProfile,
    isAdmin: mocks.isAdmin,
    crm: {
      getPractice: mocks.getPractice,
      updatePractice: mocks.updatePractice,
      deletePractice: mocks.deletePractice,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: mocks.toastSuccess,
    error: mocks.toastError,
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.sonnerSuccess,
    error: mocks.sonnerError,
  },
}));

vi.mock("@/lib/metrics/cases-metrics", () => ({
  casesMetrics: {
    trackPageView: mocks.trackPageView,
    startPerformanceMark: mocks.startPerformanceMark,
    endPerformanceMark: mocks.endPerformanceMark,
    trackApiCall: mocks.trackApiCall,
    trackError: mocks.trackError,
    trackButtonClick: mocks.trackButtonClick,
    trackModal: mocks.trackModal,
    trackCaseUpdate: mocks.trackCaseUpdate,
    trackQuickAction: mocks.trackQuickAction,
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: mocks.loggerError,
    info: mocks.loggerInfo,
  },
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({
    options: [
      {
        value: "zero@balizero.com",
        label: "Zero Tester",
        avatar: null,
      },
    ],
  }),
}));

vi.mock("./RequiredDocumentsCard", () => ({
  RequiredDocumentsCard: ({ practiceId }: { practiceId: number }) => (
    <div data-testid="required-documents">Documents for {practiceId}</div>
  ),
}));

vi.mock("@balizero/core/utils", () => ({
  formatIDR: (amount: number) => `IDR ${amount}`,
}));

import CaseDetailPage from "./page";

const profile = {
  id: "user-1",
  email: "operator@balizero.com",
  name: "Operator",
  role: "admin",
};

function makePractice(overrides: Partial<Practice> = {}): Practice {
  return {
    id: 42,
    client_id: 7,
    client_name: "John Doe",
    client_email: "john@example.com",
    client_phone: "+62 812-345",
    client_lead: "Team Lead",
    practice_type_id: 3,
    practice_type_code: "kitas_application",
    practice_type_name: "Investor KITAS",
    status: "waiting_documents",
    priority: "normal",
    payment_status: "unpaid",
    quoted_price: 1_500_000,
    actual_price: 1_750_000,
    assigned_to: "zero@balizero.com",
    notes: "Initial note",
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-07-01T00:00:00.000Z",
    start_date: "2026-02-01T00:00:00.000Z",
    expiry_date: "2027-02-01T00:00:00.000Z",
    status_transitions: [
      { status: "inquiry", at: "2026-01-01T00:00:00.000Z" },
      {
        status: "waiting_documents",
        at: "2026-01-03T00:00:00.000Z",
      },
    ],
    ...overrides,
  };
}

async function renderLoaded(practice: Practice = makePractice()) {
  mocks.getPractice.mockResolvedValueOnce(practice);
  const user = userEvent.setup();
  render(<CaseDetailPage />);
  await screen.findByRole("heading", {
    name: `${practice.practice_type_code
      ?.toUpperCase()
      .replace(/_/g, " ")} #${practice.id}`,
  });
  return user;
}

describe("CaseDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useParams.mockReturnValue({ id: "42" });
    mocks.getProfile.mockResolvedValue(profile);
    mocks.isAdmin.mockReturnValue(true);
    mocks.updatePractice.mockResolvedValue(undefined);
    mocks.deletePractice.mockResolvedValue(undefined);
    vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(window.confirm).mockReturnValue(true);
  });

  it("shows loading until the practice request settles", async () => {
    let resolvePractice!: (practice: Practice) => void;
    mocks.getPractice.mockReturnValue(
      new Promise<Practice>((resolve) => {
        resolvePractice = resolve;
      }),
    );

    render(<CaseDetailPage />);

    expect(screen.getByText("Loading process details...")).toBeInTheDocument();

    resolvePractice(makePractice());
    expect(
      await screen.findByRole("heading", { name: "KITAS APPLICATION #42" }),
    ).toBeInTheDocument();
  });

  it("rejects an invalid route id without calling the practice API", async () => {
    mocks.useParams.mockReturnValue({ id: "not-a-number" });

    render(<CaseDetailPage />);

    expect(await screen.findByText("Invalid process ID")).toBeInTheDocument();
    expect(mocks.getPractice).not.toHaveBeenCalled();
    expect(mocks.trackError).toHaveBeenCalledWith(
      "Invalid Case ID",
      "No case ID provided",
      "CasesDetailPage",
      undefined,
      undefined,
    );
  });

  it("surfaces load failures and lets the user navigate back to the list", async () => {
    mocks.getPractice.mockRejectedValueOnce(new Error("backend unavailable"));
    const user = userEvent.setup();

    render(<CaseDetailPage />);

    expect(
      await screen.findByRole("heading", {
        name: "Failed to load process details",
      }),
    ).toBeInTheDocument();
    expect(mocks.toastError).toHaveBeenCalledWith(
      "Error",
      "Failed to load process details",
    );
    expect(mocks.trackApiCall).toHaveBeenCalledWith(
      "/api/crm/practices/42",
      "GET",
      false,
      expect.any(Number),
      42,
      expect.anything(),
    );

    await user.click(screen.getByRole("button", { name: /Back to Process/i }));
    expect(mocks.push).toHaveBeenCalledWith("/process");
  });

  it("renders process, client and assigned-team data and records the load", async () => {
    await renderLoaded();

    expect(screen.getAllByText("John Doe").length).toBeGreaterThan(0);
    expect(screen.getByText("john@example.com")).toHaveAttribute(
      "href",
      "mailto:john@example.com",
    );
    expect(screen.getByText("+62 812-345")).toHaveAttribute(
      "href",
      "https://wa.me/62812345",
    );
    expect(screen.getByText("Zero Tester")).toBeInTheDocument();
    expect(screen.getAllByText("IDR 1750000")).toHaveLength(2);
    expect(screen.getByTestId("required-documents")).toHaveTextContent(
      "Documents for 42",
    );

    await waitFor(() => {
      expect(mocks.trackPageView).toHaveBeenCalledWith(
        "detail",
        42,
        profile.email,
      );
      expect(mocks.endPerformanceMark).toHaveBeenCalledWith(
        "case_detail_load",
        42,
        expect.anything(),
      );
    });
  });

  it("keeps rendering when profile/metrics initialization fails", async () => {
    mocks.getProfile.mockRejectedValueOnce(new Error("profile failed"));

    await renderLoaded();

    expect(screen.getByText("Investor KITAS")).toBeInTheDocument();
    expect(mocks.loggerError).toHaveBeenCalledWith(
      "Failed to init metrics",
      expect.objectContaining({ action: "initMetrics" }),
      expect.any(Error),
    );
  });

  it("navigates back and to the related client with analytics", async () => {
    const user = await renderLoaded();

    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(mocks.back).toHaveBeenCalledTimes(1);

    await user.click(screen.getAllByRole("button", { name: "John Doe" })[0]);
    expect(mocks.push).toHaveBeenCalledWith("/clients/7?tab=process");
    expect(mocks.trackButtonClick).toHaveBeenCalledWith(
      "Back to Process",
      "CasesDetailPage",
      42,
      "/process",
      expect.anything(),
    );
  });

  it("cycles payment and priority and updates the visible values", async () => {
    const user = await renderLoaded();

    await user.click(
      screen.getAllByRole("button", { name: "Cycle payment status" })[0],
    );
    await waitFor(() => {
      expect(mocks.updatePractice).toHaveBeenCalledWith(42, {
        payment_status: "partial",
      });
    });
    expect(screen.getAllByText("partial").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Cycle priority" }));
    await waitFor(() => {
      expect(mocks.updatePractice).toHaveBeenCalledWith(42, {
        priority: "high",
      });
    });
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Priority updated",
      "→ high",
    );
  });

  it("reports inline update failures without mutating the visible value", async () => {
    mocks.updatePractice.mockRejectedValueOnce(new Error("payment denied"));
    const user = await renderLoaded();

    await user.click(
      screen.getAllByRole("button", { name: "Cycle payment status" })[0],
    );

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalledWith(
        "Failed to update payment status",
        "payment denied",
      );
    });
    expect(screen.getAllByText("unpaid").length).toBeGreaterThan(0);
  });

  it("jumps to another workflow state and persists it", async () => {
    const user = await renderLoaded();

    await user.click(screen.getByTitle("Jump to: Processing"));

    await waitFor(() => {
      expect(mocks.updatePractice).toHaveBeenCalledWith(42, {
        status: "on_process",
      });
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Status updated",
      "→ on process",
    );
  });

  it("saves notes and restores the read-only view", async () => {
    const user = await renderLoaded();

    await user.click(screen.getByRole("button", { name: "Edit notes" }));
    const notes = screen.getByRole("textbox", { name: "" });
    await user.clear(notes);
    await user.type(notes, "Updated internal note");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mocks.updatePractice).toHaveBeenCalledWith(42, {
        notes: "Updated internal note",
      });
    });
    expect(
      await screen.findByText("Updated internal note"),
    ).toBeInTheDocument();
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Notes saved");
  });

  it("validates prices locally and saves a valid quoted price", async () => {
    const user = await renderLoaded();

    await user.click(screen.getByRole("button", { name: "Edit quoted price" }));
    let priceInput = screen.getByRole("spinbutton");
    await user.clear(priceInput);
    await user.type(priceInput, "-1");
    fireEvent.keyDown(priceInput, { key: "Enter" });
    expect(mocks.updatePractice).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Edit quoted price" }));
    priceInput = screen.getByRole("spinbutton");
    await user.clear(priceInput);
    await user.type(priceInput, "2000000");
    fireEvent.keyDown(priceInput, { key: "Enter" });

    await waitFor(() => {
      expect(mocks.updatePractice).toHaveBeenCalledWith(42, {
        quoted_price: 2_000_000,
      });
    });
    expect(await screen.findByText("IDR 2000000")).toBeInTheDocument();
  });

  it("closes an unchanged edit and submits changed fields with a reload", async () => {
    const original = makePractice();
    const updated = makePractice({
      priority: "urgent",
      quoted_price: 2_000_000,
    });
    mocks.getPractice
      .mockResolvedValueOnce(original)
      .mockResolvedValueOnce(updated);
    const user = userEvent.setup();
    render(<CaseDetailPage />);
    await screen.findByRole("heading", { name: "KITAS APPLICATION #42" });

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const firstModal = screen.getByRole("heading", { name: "Edit Process #42" })
      .parentElement?.parentElement;
    expect(firstModal).not.toBeNull();
    await user.click(
      within(firstModal as HTMLElement).getByRole("button", {
        name: "Save Changes",
      }),
    );
    expect(mocks.toastError).toHaveBeenCalledWith(
      "No Changes",
      "No fields were modified.",
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const modal = screen.getByRole("heading", { name: "Edit Process #42" })
      .parentElement?.parentElement as HTMLElement;
    await user.click(within(modal).getByRole("button", { name: "🔥 Urgent" }));
    const quotedInput = within(modal).getByDisplayValue("1500000");
    await user.clear(quotedInput);
    await user.type(quotedInput, "2000000");
    await user.click(
      within(modal).getByRole("button", { name: "Save Changes" }),
    );

    await waitFor(() => {
      expect(mocks.updatePractice).toHaveBeenCalledWith(42, {
        priority: "urgent",
        quoted_price: 2_000_000,
      });
      expect(mocks.getPractice).toHaveBeenCalledTimes(2);
    });
    expect(mocks.trackCaseUpdate).toHaveBeenCalledWith(
      42,
      ["priority", "quoted_price"],
      "details",
      profile.email,
    );
  });

  it("maps authorization errors from edit requests to a user-safe message", async () => {
    mocks.updatePractice.mockRejectedValueOnce(new Error("403 Forbidden"));
    const user = await renderLoaded();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const modal = screen.getByRole("heading", { name: "Edit Process #42" })
      .parentElement?.parentElement as HTMLElement;
    await user.click(within(modal).getByRole("button", { name: "↑ High" }));
    await user.click(
      within(modal).getByRole("button", { name: "Save Changes" }),
    );

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalledWith(
        "Error",
        "You do not have permission to update this process.",
      );
    });
  });

  it("offers copy/contact actions and deletes a confirmed process", async () => {
    const user = await renderLoaded();

    await user.click(screen.getByRole("button", { name: "More options" }));
    await user.click(screen.getByRole("button", { name: "Copy link" }));
    expect(await navigator.clipboard.readText()).toBe(window.location.href);
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Copied",
      "Process link copied to clipboard",
    );

    await user.click(screen.getByRole("button", { name: "More options" }));
    await user.click(screen.getByRole("button", { name: "WhatsApp client" }));
    expect(window.open).toHaveBeenCalledWith(
      "https://wa.me/62812345?text=Hi John Doe, regarding your process...",
      "_blank",
    );

    await user.click(screen.getByRole("button", { name: "More options" }));
    await user.click(screen.getByRole("button", { name: "Delete process" }));

    await waitFor(() => {
      expect(mocks.deletePractice).toHaveBeenCalledWith(42, profile.email);
      expect(mocks.sonnerSuccess).toHaveBeenCalledWith("Process deleted");
      expect(mocks.push).toHaveBeenCalledWith("/process");
    });
  });
});
