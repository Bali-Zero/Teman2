import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/error-handler";

import ObligationsPage from "./page";

const pushMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

const PROPOSED_ROW = {
  id: 101,
  client_id: 42,
  rule_id: "PPH21_MONTHLY",
  period_key: "2026-09",
  due_date: "2026-10-10",
  status: "proposed",
  needs_review_reason: "New rule matched",
  reviewer_email: null,
  reviewed_at: null,
  review_note: null,
  alert_id: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const LIST_RESPONSE = {
  total: 1,
  limit: 50,
  offset: 0,
  items: [PROPOSED_ROW],
};

describe("ObligationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.get.mockResolvedValue(LIST_RESPONSE);
    apiMock.post.mockResolvedValue({});
  });

  it("renders proposed rows from the list response", async () => {
    render(<ObligationsPage />);

    expect(await screen.findByText("PPH21_MONTHLY")).toBeVisible();
    expect(screen.getByText("2026-09")).toBeVisible();
    expect(screen.getByText("2026-10-10")).toBeVisible();
    expect(screen.getByText("New rule matched")).toBeVisible();
    // "proposed" also appears as the status-filter default option, so assert
    // presence (>=1) rather than uniqueness.
    expect(screen.getAllByText("proposed").length).toBeGreaterThan(0);
    // client_id and id are rendered as bare numbers, ids-only (no PII join).
    expect(screen.getByText("42")).toBeVisible();
    expect(screen.getByText("101")).toBeVisible();

    expect(apiMock.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/compliance/obligations?"),
    );
    expect(apiMock.get).toHaveBeenCalledWith(
      expect.stringContaining("status=proposed"),
    );
  });

  it("approve sends the note and refetches the list", async () => {
    apiMock.post.mockResolvedValueOnce({
      obligation: { ...PROPOSED_ROW, status: "alerted" },
      alert_id: "alert_obligation_42_abcd1234",
    });

    render(<ObligationsPage />);
    await screen.findByText("PPH21_MONTHLY");

    const noteInput = screen.getByLabelText("Note for obligation 101");
    fireEvent.change(noteInput, { target: { value: "looks correct" } });

    const approveBtn = screen.getByRole("button", { name: "Approve" });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/compliance/obligations/101/approve",
        { note: "looks correct" },
      );
    });

    // Refetch: the initial load + the post-approve reload.
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledTimes(2));

    expect(
      await screen.findByText(
        "✓ Obligation #101 approved → alert alert_obligation_42_abcd1234.",
      ),
    ).toBeVisible();
  });

  it("reject requires a reason and is disabled without one", async () => {
    render(<ObligationsPage />);
    await screen.findByText("PPH21_MONTHLY");

    const rejectBtn = screen.getByRole("button", { name: "Reject" });
    fireEvent.click(rejectBtn);

    expect(
      await screen.findByText("A reason is required to reject."),
    ).toBeVisible();
    expect(apiMock.post).not.toHaveBeenCalled();

    const noteInput = screen.getByLabelText("Note for obligation 101");
    fireEvent.change(noteInput, { target: { value: "duplicate rule" } });
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/compliance/obligations/101/reject",
        { reason: "duplicate rule" },
      );
    });
  });

  it("generate with needs_manual_classification=true shows the warning banner", async () => {
    apiMock.post.mockResolvedValueOnce({
      client_id: 42,
      inserted_count: 3,
      company_type: "OTHER",
      needs_manual_classification: true,
      warning:
        "profile_from_rows could not map this client's company_type to a known type",
      rows: [],
    });

    render(<ObligationsPage />);
    await screen.findByText("PPH21_MONTHLY");

    fireEvent.change(screen.getByPlaceholderText("e.g. 42"), {
      target: { value: "42" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposals" }));

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/compliance/obligations/generate",
        { client_id: 42, horizon_days: 90 },
      );
    });

    expect(
      await screen.findByText(/Inserted 3 new proposals for client 42/),
    ).toBeVisible();
    expect(screen.getByText(/company_type to a known type/)).toBeVisible();
  });

  it("shows the admin-only message on a 403", async () => {
    apiMock.get.mockReset();
    apiMock.get.mockRejectedValue(
      new ApiError("CRM admin required", 403, { detail: "CRM admin required" }),
    );

    render(<ObligationsPage />);

    expect(await screen.findByText("Admin only.")).toBeVisible();
  });
});
