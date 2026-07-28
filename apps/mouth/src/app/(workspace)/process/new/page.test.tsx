import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clientDetailQueryKey } from "@/hooks/useClientDetail";

const {
  mockPush,
  mockGetPracticeTypesCatalog,
  mockGetClient,
  mockGetFamilyMembers,
  mockGetClientPractices,
  mockCreatePractice,
  mockRefetchClientProfile,
  stableSearchParams,
} = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockGetPracticeTypesCatalog: vi.fn(),
  mockGetClient: vi.fn(),
  mockGetFamilyMembers: vi.fn(),
  mockGetClientPractices: vi.fn(),
  mockCreatePractice: vi.fn(),
  mockRefetchClientProfile: vi.fn(),
  stableSearchParams: {
    get: vi.fn((key: string) => (key === "client_id" ? "7" : null)),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => stableSearchParams,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({
      email: "synthetic.team@example.test",
    }),
    isAdmin: vi.fn(() => true),
    crm: {
      getPracticeTypesCatalog: mockGetPracticeTypesCatalog,
      getClient: mockGetClient,
      getFamilyMembers: mockGetFamilyMembers,
      getClientPractices: mockGetClientPractices,
      createPractice: mockCreatePractice,
      getClients: vi.fn(),
    },
  },
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({
    options: [
      {
        value: "synthetic.team@example.test",
        label: "Synthetic Team Member",
      },
    ],
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

vi.mock("@/components/partners/ReferrerDropdown", () => ({
  ReferrerDropdown: () => <div data-testid="referrer-dropdown" />,
}));

vi.mock("@/lib/api/partners/partners", () => ({
  createReferral: vi.fn(),
}));

vi.mock("@/lib/metrics/cases-metrics", () => ({
  casesMetrics: {
    trackPageView: vi.fn(),
    trackApiCall: vi.fn(),
    trackClientSearch: vi.fn(),
    trackError: vi.fn(),
    trackButtonClick: vi.fn(),
    startPerformanceMark: vi.fn(),
    trackCaseCreation: vi.fn(),
    endPerformanceMark: vi.fn(),
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

describe("NewPracticePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetPracticeTypesCatalog.mockResolvedValue({
      categories: [
        {
          code: "visa",
          label: "Visa",
          services: [
            {
              code: "SYNTHETIC_VISA",
              name: "Synthetic Visa Process",
              description: "Synthetic service for cache QA",
              base_price: null,
              typical_duration_days: 7,
            },
          ],
        },
      ],
    });
    mockGetClient.mockResolvedValue({
      id: 7,
      uuid: "synthetic-client-7",
      full_name: "Synthetic Process Client",
      email: "synthetic.process@example.test",
      status: "active",
      client_type: "individual",
      created_at: "2026-07-27T00:00:00Z",
      updated_at: "2026-07-27T00:00:00Z",
    });
    mockGetFamilyMembers.mockResolvedValue([]);
    mockGetClientPractices.mockResolvedValue([]);
    mockCreatePractice.mockResolvedValue({ id: 71 });
    mockRefetchClientProfile.mockResolvedValue({
      client: { id: 7 },
      practices: [{ id: 71 }],
      stats: { practices_count: 1 },
    });
  });

  it("refetches the selected client before returning to its process tab", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const queryKey = clientDetailQueryKey(7);
    queryClient.setQueryDefaults(queryKey, {
      queryFn: mockRefetchClientProfile,
    });
    queryClient.setQueryData(queryKey, { client: { id: 7 } });

    const { default: NewPracticePage } = await import("./page");
    render(
      <QueryClientProvider client={queryClient}>
        <NewPracticePage />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("Synthetic Process Client"),
    ).toBeInTheDocument();
    const selects = await screen.findAllByRole("combobox");
    await user.selectOptions(selects[0], "visa");
    await user.selectOptions(selects[1], "SYNTHETIC_VISA");
    await user.click(screen.getByRole("button", { name: "Create Process" }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/clients/7?tab=process");
    });
    expect(mockRefetchClientProfile).toHaveBeenCalledTimes(1);
    expect(mockRefetchClientProfile.mock.invocationCallOrder[0]).toBeLessThan(
      mockPush.mock.invocationCallOrder[0],
    );
    expect(queryClient.getQueryData(queryKey)).toMatchObject({
      practices: [{ id: 71 }],
      stats: { practices_count: 1 },
    });
  });
});
