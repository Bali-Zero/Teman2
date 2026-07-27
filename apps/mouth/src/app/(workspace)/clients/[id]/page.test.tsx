import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientProfile } from "@/lib/api/crm/crm.types";

const {
  mockUpdateClient,
  mockSetClientCache,
  mockInvalidateClient,
  mockUseClientDetail,
  stableTimeline,
  stableSearchParams,
} = vi.hoisted(() => ({
  mockUpdateClient: vi.fn(),
  mockSetClientCache: vi.fn(),
  mockInvalidateClient: vi.fn(),
  mockUseClientDetail: vi.fn(),
  stableTimeline: [],
  stableSearchParams: { get: vi.fn(() => null) },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "7" }),
  useRouter: () => ({
    back: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
  }),
  useSearchParams: () => stableSearchParams,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({
      email: "synthetic.team@example.test",
    }),
    crm: {
      updateClient: mockUpdateClient,
      createInteraction: vi.fn(),
    },
  },
}));

vi.mock("@/hooks/useClientDetail", () => ({
  useClientDetail: mockUseClientDetail,
  useClientTimeline: () => ({ data: stableTimeline }),
  useDocumentCategories: () => ({ data: [] }),
  useClientBusinessStory: () => ({
    data: [],
    error: null,
    isLoading: false,
  }),
  useInvalidateClient: () => mockInvalidateClient,
  useSetClientCache: () => mockSetClientCache,
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({ options: [] }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("./components/OverviewTab", () => ({
  OverviewTab: () => <div data-testid="OverviewTab" />,
}));
vi.mock("./components/DocumentsTab", () => ({
  DocumentsTab: () => <div data-testid="DocumentsTab" />,
}));
vi.mock("./components/ProcessTab", () => ({
  ProcessTab: () => <div data-testid="ProcessTab" />,
}));
vi.mock("./components/FamilyTab", () => ({
  FamilyTab: () => <div data-testid="FamilyTab" />,
}));
vi.mock("./components/ImmigrationTab", () => ({
  ImmigrationTab: () => <div data-testid="ImmigrationTab" />,
}));
vi.mock("./components/CompanyTab", () => ({
  CompanyTab: () => <div data-testid="CompanyTab" />,
}));
vi.mock("./components/TaxTab", () => ({
  TaxTab: () => <div data-testid="TaxTab" />,
}));
vi.mock("./components/TimelineTab", () => ({
  TimelineTab: () => <div data-testid="TimelineTab" />,
}));
vi.mock("./components/WaTimelineTab", () => ({
  WaTimelineTab: () => <div data-testid="WaTimelineTab" />,
}));
vi.mock("./components/PortalMessages", () => ({
  PortalMessages: () => <div data-testid="PortalMessages" />,
}));
vi.mock("./components/BusinessStoryPanel", () => ({
  BusinessStoryPanel: () => <div data-testid="BusinessStoryPanel" />,
}));
vi.mock("./components/modals/EditClientModal", () => ({
  EditClientModal: () => null,
}));
vi.mock("./components/modals/AddFamilyMemberModal", () => ({
  AddFamilyMemberModal: () => null,
}));
vi.mock("./components/modals/EditFamilyMemberModal", () => ({
  EditFamilyMemberModal: () => null,
}));
vi.mock("./components/modals/AddDocumentModal", () => ({
  AddDocumentModal: () => null,
}));
vi.mock("./components/modals/EditDocumentModal", () => ({
  EditDocumentModal: () => null,
}));

const makeProfile = (
  practiceStatus?: string,
  practicesCount = practiceStatus ? 1 : 0,
): ClientProfile => ({
  client: {
    id: 7,
    uuid: "synthetic-client-7",
    full_name: "Synthetic Status Client",
    email: "synthetic.status@example.test",
    status: "active",
    client_type: "individual",
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
  family_members: [],
  documents: [],
  expiry_alerts: [],
  practices: practiceStatus
    ? [
        {
          id: 71,
          status: practiceStatus,
          practice_type_code: "SYNTHETIC",
          practice_type_name: "Synthetic Process",
        },
      ]
    : [],
  company_links: [],
  stats: {
    family_count: 0,
    documents_count: 0,
    practices_count: practicesCount,
    expired_count: 0,
    red_alerts: 0,
    yellow_alerts: 0,
  },
});

describe("ClientDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseClientDetail.mockReturnValue({
      data: makeProfile(),
      isLoading: false,
      error: null,
    });
    mockInvalidateClient.mockResolvedValue(undefined);
    mockUpdateClient.mockResolvedValue({
      ...makeProfile().client,
      status: "inactive",
    });
  });

  it("selects a status with the mouse and patches the authoritative client", async () => {
    const user = userEvent.setup();
    const { default: ClientDetailPage } = await import("./page");
    render(<ClientDetailPage />);

    await user.click(
      screen.getByRole("button", { name: "Change client status" }),
    );
    await user.click(screen.getByRole("button", { name: "inactive" }));

    await waitFor(() => {
      expect(mockUpdateClient).toHaveBeenCalledWith(
        7,
        { status: "inactive" },
        "synthetic.team@example.test",
      );
    });
    expect(mockSetClientCache).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, status: "inactive" }),
    );
  });

  it("counts only processes visible in the active and completed lists", async () => {
    mockUseClientDetail.mockReturnValue({
      data: makeProfile("cancelled", 1),
      isLoading: false,
      error: null,
    });
    const { default: ClientDetailPage } = await import("./page");
    render(<ClientDetailPage />);

    expect(
      screen.getByRole("button", { name: "Process (0)" }),
    ).toBeInTheDocument();
  });
});
