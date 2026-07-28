import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { useTeamMemberOptions } from "./useTeamMembers";

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
  },
}));

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

describe("useTeamMemberOptions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("deduplicates normalized emails and disambiguates repeated names", async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: "member-1",
        email: " ari@example.test ",
        full_name: "Ari Example",
        name: "Ari",
        role: "team",
        avatar_url: null,
        avatar: null,
      },
      {
        id: "member-1-copy",
        email: "ARI@EXAMPLE.TEST",
        full_name: "Ari Example",
        name: "Ari duplicate",
        role: "team",
        avatar_url: null,
        avatar: null,
      },
      {
        id: "member-2",
        email: "other@example.test",
        full_name: "Ari Example",
        name: "Other Ari",
        role: "tax",
        avatar_url: null,
        avatar: null,
      },
      {
        id: "client-1",
        email: "client@example.test",
        full_name: "Client Example",
        name: "Client",
        role: "client",
        avatar_url: null,
        avatar: null,
      },
    ]);

    const queryClient = createClient();
    const { result } = renderHook(() => useTeamMemberOptions(), {
      wrapper: wrapperFor(queryClient),
    });

    await waitFor(() => {
      expect(result.current.options).toHaveLength(2);
    });
    expect(result.current.options).toEqual([
      {
        value: "ari@example.test",
        label: "Ari Example (ari@example.test)",
        avatar: undefined,
      },
      {
        value: "other@example.test",
        label: "Ari Example (other@example.test)",
        avatar: undefined,
      },
    ]);
  });
});
