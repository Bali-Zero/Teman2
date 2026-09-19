import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OverviewTab } from "./OverviewTab";
import { api } from "@/lib/api";
import type { ClientProfile, ExpiryAlert } from "@/lib/api/crm/crm.types";

// OverviewTab also mounts AiSummaryCard / WaCaseIntelligencePanel, both of
// which fetch on mount — stub them to their real "not generated" shape so
// they render their quiet empty state instead of throwing.
vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      getClientAiSummary: vi.fn(),
      getClientWaCaseIntelligence: vi.fn(),
      queryClientIntelligence: vi.fn(),
      extractPassportForClient: vi.fn(),
    },
    post: vi.fn(),
    request: vi.fn(),
  },
}));

const client = {
  id: 42,
  uuid: "test-uuid",
  full_name: "Test Client",
  status: "active",
  client_type: "individual",
  date_of_birth: undefined,
} as unknown as ClientProfile["client"];

const stats = {
  family_count: 0,
  documents_count: 0,
  practices_count: 0,
  expired_count: 0,
  red_alerts: 0,
  yellow_alerts: 0,
} as ClientProfile["stats"];

function alert(overrides: Partial<ExpiryAlert>): ExpiryAlert {
  return {
    entity_type: "client",
    entity_id: 42,
    entity_name: "Test Client",
    client_id: 42,
    client_name: "Test Client",
    document_type: "passport",
    expiry_date: "2026-01-01",
    days_until_expiry: 30,
    alert_color: "red",
    ...overrides,
  };
}

const baseProps = {
  client,
  stats,
  documents: [],
  activePractices: [],
  completedPractices: [],
  formatDate: (d: string) => d,
  formatCurrency: (n: number) => String(n),
  onEditClick: vi.fn(),
  onRefresh: vi.fn().mockResolvedValue(undefined),
  clientId: 42,
};

describe("OverviewTab — Needs attention ledger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.crm.getClientAiSummary).mockResolvedValue({
      status: "not_generated",
    } as any);
    vi.mocked(api.crm.getClientWaCaseIntelligence).mockResolvedValue({
      status: "not_generated",
      cases: [],
    } as any);
  });

  it("GUILT: orders the expired alert before the expiring one, titled from real fields", async () => {
    render(
      <OverviewTab
        {...baseProps}
        expiryAlerts={[
          alert({
            document_type: "visa",
            alert_color: "red",
            days_until_expiry: 21,
          }),
          alert({
            document_type: "passport",
            alert_color: "expired",
            days_until_expiry: -5,
          }),
        ]}
        needsViewerAction={false}
      />,
    );

    const list = await screen.findByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Passport expired"),
      expect.stringContaining("Visa expires soon"),
    ]);
  });

  it("GUILT: a row whose next actor is not the viewer renders wait, never you", () => {
    render(
      <OverviewTab
        {...baseProps}
        expiryAlerts={[alert({ alert_color: "red" })]}
        needsViewerAction={false}
      />,
    );
    expect(screen.getByText("Wait")).toBeTruthy();
    expect(screen.queryByText("You")).toBeNull();
  });

  it("the viewer being the next actor renders you, never wait", () => {
    render(
      <OverviewTab
        {...baseProps}
        expiryAlerts={[alert({ alert_color: "red" })]}
        needsViewerAction={true}
      />,
    );
    expect(screen.getByText("You")).toBeTruthy();
    expect(screen.queryByText("Wait")).toBeNull();
  });

  it("INNOCENCE: no alerts renders no ledger, and existing Overview content still renders", async () => {
    render(
      <OverviewTab
        {...baseProps}
        expiryAlerts={[]}
        needsViewerAction={false}
      />,
    );
    expect(screen.queryByText("Needs attention")).toBeNull();
    expect(await screen.findByText("🔮 Ask the Oracle")).toBeTruthy();
  });

  it("INNOCENCE: six alerts render five rows plus a quiet Show all (6)", () => {
    const alerts = Array.from({ length: 6 }, (_, i) =>
      alert({
        document_type: `doc_${i}`,
        alert_color: "red",
        days_until_expiry: i + 1,
      }),
    );
    render(
      <OverviewTab
        {...baseProps}
        expiryAlerts={alerts}
        needsViewerAction={false}
      />,
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByText("Show all (6)")).toBeTruthy();
  });
});
