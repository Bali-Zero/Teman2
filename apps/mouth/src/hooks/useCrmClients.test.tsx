import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { useCrmStats } from "./useCrmClients";

vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      request: vi.fn(),
      getPracticeStats: vi.fn(),
      getInteractionStats: vi.fn(),
    },
  },
}));
vi.mock("@/lib/logger");

const practiceStatsFixture = {
  total_practices: 0,
  active_practices: 0,
  by_status: {},
  by_type: [],
  revenue: { total_revenue: 0, paid_revenue: 0, outstanding_revenue: 0 },
};

const interactionStatsFixture = {
  total_interactions: 0,
  last_7_days: 0,
  by_type: {},
  by_sentiment: {},
  by_team_member: [],
};

const createClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

const wrapperFor =
  (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

const mockedRequest = vi.mocked(api.crm.request);
const mockedGetPracticeStats = vi.mocked(api.crm.getPracticeStats);
const mockedGetInteractionStats = vi.mocked(api.crm.getInteractionStats);

describe("useCrmStats — client-stats failure vs genuine zero", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetPracticeStats.mockResolvedValue(practiceStatsFixture);
    mockedGetInteractionStats.mockResolvedValue(interactionStatsFixture);
  });

  // GUILT: the client-stats endpoint fails (e.g. a 503 while the rag process
  // is down). Before the fix, Promise.allSettled swallowed this into
  // `totalClients: 0` — a real outage rendered identically to an empty book.
  // clients/page.tsx has no isError guard of its own for this value; it
  // renders "N total" only when `stats` (the query's `data`) is truthy. The
  // only way the page can avoid ever showing "0 total" on a failure is for
  // this query to actually reject, so `data` stays `undefined`.
  it("does not resolve totalClients=0 when the client-stats fetch rejects", async () => {
    mockedRequest.mockRejectedValue(new Error("503 Service Unavailable"));

    const queryClient = createClient();
    const { result } = renderHook(() => useCrmStats(), {
      wrapper: wrapperFor(queryClient),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.data).toBeUndefined();
    expect(result.current.isError).toBe(true);
  });

  // INNOCENCE: the client-stats endpoint succeeds and genuinely reports zero
  // clients (a real empty book). This must still resolve normally — the fix
  // must not turn a legitimate 0 into an error state.
  it("resolves totalClients=0 with no error when the fetch succeeds with a real zero", async () => {
    mockedRequest.mockResolvedValue({
      total: 0,
      by_status: {},
      by_team_member: [],
      passport_expired: 0,
      passport_expiring_soon: 0,
      silent_30d: 0,
    });

    const queryClient = createClient();
    const { result } = renderHook(() => useCrmStats(), {
      wrapper: wrapperFor(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.totalClients).toBe(0);
    expect(result.current.isError).toBe(false);
  });
});
