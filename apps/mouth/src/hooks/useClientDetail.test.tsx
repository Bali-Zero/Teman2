import type { ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import {
  buildBusinessStorySearchTerms,
  clientDetailQueryKey,
  useInvalidateClient,
  useSetClientCache,
} from "./useClientDetail";
import type {
  Client,
  ClientCompanyLink,
  ClientProfile,
} from "@/lib/api/crm/crm.types";

const makeClient = (status: Client["status"]): Client => ({
  id: 7,
  uuid: "synthetic-client-7",
  full_name: "Synthetic Cache Client",
  email: "synthetic.cache@example.test",
  status,
  client_type: "individual",
  created_at: "2026-07-27T00:00:00Z",
  updated_at: "2026-07-27T00:00:00Z",
});

const makeProfile = (status: Client["status"]): ClientProfile => ({
  client: makeClient(status),
  family_members: [],
  documents: [],
  expiry_alerts: [],
  practices: [],
  company_links: [],
  stats: {
    family_count: 0,
    documents_count: 0,
    practices_count: 0,
    expired_count: 0,
    red_alerts: 0,
    yellow_alerts: 0,
  },
});

const wrapperFor =
  (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

describe("buildBusinessStorySearchTerms", () => {
  it("starts from the person and deduplicates linked company names", () => {
    const links: ClientCompanyLink[] = [
      {
        link_id: 1,
        company_id: 10,
        company_name: "Bimala Investments Bali PT",
        company_type: "PT PMA",
        role: "Shareholder",
        is_primary: true,
        status: "active",
      },
      {
        link_id: 2,
        company_id: 10,
        company_name: "  Bimala Investments Bali PT  ",
        company_type: "PT PMA",
        role: "Director",
        is_primary: false,
        status: "active",
      },
    ];

    expect(buildBusinessStorySearchTerms("Giulia Del Giudice", links)).toEqual([
      "Giulia Del Giudice",
      "Bimala Investments Bali PT",
    ]);
  });

  it("keeps Ocean and Bimala fallback search terms for unlinked people", () => {
    expect(buildBusinessStorySearchTerms("Natan Kleimonov", [])).toEqual([
      "Natan Kleimonov",
      "ocean",
      "bimala",
    ]);
  });
});

describe("client detail cache transitions", () => {
  it("patches the client immediately while preserving the rest of the profile", () => {
    const queryClient = new QueryClient();
    const queryKey = clientDetailQueryKey(7);
    const activeProfile = makeProfile("active");
    queryClient.setQueryData(queryKey, activeProfile);

    const { result } = renderHook(() => useSetClientCache(7), {
      wrapper: wrapperFor(queryClient),
    });

    act(() => {
      result.current(makeClient("inactive"));
    });

    expect(queryClient.getQueryData<ClientProfile>(queryKey)).toEqual({
      ...activeProfile,
      client: makeClient("inactive"),
    });
  });

  it("invalidates the exact client detail query", async () => {
    const queryClient = new QueryClient();
    const queryKey = clientDetailQueryKey(7);
    queryClient.setQueryData(queryKey, makeProfile("active"));

    const { result } = renderHook(() => useInvalidateClient(7), {
      wrapper: wrapperFor(queryClient),
    });

    await act(async () => {
      await result.current();
    });

    expect(queryClient.getQueryState(queryKey)?.isInvalidated).toBe(true);
  });
});
