import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import GateScreen from "../GateScreen";
import { api } from "@/lib/api";
import type { ComplianceAlertItem, GateStatus } from "@/lib/api";

/**
 * Regression tests for the deadlines gate section.
 *
 * Bug context (2026-07-20): the section used to deep-link to /clients, but
 * the workspace layout intercepts EVERY route except /review while the gate
 * is blocked — so "Review deadlines →" looped the user back into the wall
 * and there was NO UI anywhere to acknowledge a deadline alert. Team members
 * with deadline alerts (e.g. adit@, ari@) were permanently locked out.
 * The section is now self-contained: it lists the user's deadline alerts
 * inline and acknowledges them via POST /api/compliance/alerts/{id}/outcome
 * (allowlisted in the backend gate dependency).
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listMyComplianceAlerts: vi.fn(),
    acknowledgeComplianceAlert: vi.fn(),
  },
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

const listMock = vi.mocked(api.listMyComplianceAlerts);
const ackMock = vi.mocked(api.acknowledgeComplianceAlert);

function isoDate(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function makeAlert(
  id: string,
  offsetDays: number,
  overrides: Partial<ComplianceAlertItem> = {},
): ComplianceAlertItem {
  return {
    alert_id: id,
    client_id: 42,
    category: "visa_expiry",
    severity: "urgent",
    status: "pending",
    deadline: isoDate(offsetDays),
    days_until: offsetDays,
    message_en: `Alert ${id}`,
    ...overrides,
  };
}

function makeStatus(deadlineCount: number): GateStatus {
  return {
    blocked: deadlineCount > 0,
    sections: {
      documents: { count: 0, blocking: true },
      late_note: { count: 0, blocking: true },
      deadlines: { count: deadlineCount, blocking: true },
    },
    as_of: "2026-07-20T09:00:00Z",
    degraded: false,
  };
}

function renderGate(status: GateStatus, onRefresh = vi.fn()) {
  return {
    onRefresh,
    ...render(
      <GateScreen
        status={status}
        userEmail="adit@balizero.com"
        isAdmin={false}
        onRefresh={onRefresh}
        onEnter={vi.fn()}
      />,
    ),
  };
}

describe("GateScreen — Deadlines section", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMock.mockImplementation(async ({ status } = {}) => ({
      items:
        status === "pending"
          ? [
              makeAlert("a-overdue", -2),
              makeAlert("a-soon", 3),
              makeAlert("a-far", 10),
            ]
          : [],
    }));
  });

  it("lists only in-horizon alerts inline (overdue included, far-future excluded)", async () => {
    renderGate(makeStatus(3));

    // In-horizon items appear…
    expect(await screen.findByText("Alert a-overdue")).toBeInTheDocument();
    expect(screen.getByText("Alert a-soon")).toBeInTheDocument();
    // …the out-of-horizon one does not.
    expect(screen.queryByText("Alert a-far")).not.toBeInTheDocument();
    // The old dead-end deep-link is gone.
    expect(
      screen.queryByRole("button", { name: /review deadlines/i }),
    ).not.toBeInTheDocument();
    // Fetched as pending + sent (the two gate-blocking statuses).
    expect(listMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: "pending" }),
    );
    expect(listMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: "sent" }),
    );
  });

  it("acknowledges an alert inline, removes it and re-probes the gate", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    ackMock.mockResolvedValue({ status: "acknowledged" });
    renderGate(makeStatus(2), onRefresh);

    const buttons = await screen.findAllByRole("button", {
      name: /^acknowledge$/i,
    });
    fireEvent.click(buttons[0]);

    await waitFor(() => expect(ackMock).toHaveBeenCalledWith("a-overdue"));
    await waitFor(() =>
      expect(screen.queryByText("Alert a-overdue")).not.toBeInTheDocument(),
    );
    expect(onRefresh).toHaveBeenCalled();
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("shows a toast and keeps the item when acknowledge fails", async () => {
    ackMock.mockRejectedValue(new Error("boom"));
    renderGate(makeStatus(2));

    const buttons = await screen.findAllByRole("button", {
      name: /^acknowledge$/i,
    });
    fireEvent.click(buttons[0]);

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(screen.getByText("Alert a-overdue")).toBeInTheDocument();
  });

  it("shows a retry hint when the list cannot be loaded", async () => {
    listMock.mockRejectedValue(new Error("network down"));
    renderGate(makeStatus(2));

    expect(
      await screen.findByText(/could not load the deadlines list/i),
    ).toBeInTheDocument();
  });

  it("renders the all-clear state without fetching alerts", () => {
    renderGate(makeStatus(0));

    expect(
      screen.getByText(/no deadlines to acknowledge/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /enter workspace/i }),
    ).toBeInTheDocument();
    expect(listMock).not.toHaveBeenCalled();
  });
});
