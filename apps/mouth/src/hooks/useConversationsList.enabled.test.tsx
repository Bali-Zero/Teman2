/**
 * `useConversationsList` calls an authenticated-only endpoint.
 *
 * The hook used to fire on mount unconditionally, which is fine on the private
 * surfaces it was written for and wrong on `/chat`, which anonymous visitors
 * can reach: measured live on 2026-08-27, every anonymous pageview collected a
 * 401 from `conversations/list`. The `enabled` flag added for that gate is only
 * worth anything if it actually stops the request, so these tests assert
 * against the REAL React Query machinery — a live QueryClient, the real
 * `useQuery` — and watch whether the query function is reached at all.
 *
 * Both directions are covered on purpose. A gate that never lets anything
 * through would pass the "does not fetch" half and silently break every
 * logged-in user, which is the more expensive failure of the two.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  api: { listConversations: vi.fn() },
}));

vi.mock("@/lib/api", () => ({ api: mocks.api }));

import { useConversationsList } from "./useConversations";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return React.createElement(QueryClientProvider, { client }, children);
}

describe("useConversationsList — the enabled gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.api.listConversations.mockResolvedValue({ conversations: [] });
  });

  it("does not touch the authenticated endpoint when disabled", async () => {
    const { result } = renderHook(() => useConversationsList(20, 0, false), {
      wrapper,
    });

    // Give React Query every chance to fetch before concluding it did not.
    await waitFor(() => {
      expect(result.current.fetchStatus).toBe("idle");
    });
    expect(mocks.api.listConversations).not.toHaveBeenCalled();
  });

  it("fetches when enabled", async () => {
    renderHook(() => useConversationsList(20, 0, true), { wrapper });

    await waitFor(() => {
      expect(mocks.api.listConversations).toHaveBeenCalledTimes(1);
    });
    expect(mocks.api.listConversations).toHaveBeenCalledWith(20, 0);
  });

  it("still fetches for callers that pass no flag at all", async () => {
    // The parameter defaults to true precisely so the private surfaces that
    // already use this hook keep working untouched. If this goes red, the gate
    // has leaked out of `/chat` and disabled someone else's data.
    renderHook(() => useConversationsList(), { wrapper });

    await waitFor(() => {
      expect(mocks.api.listConversations).toHaveBeenCalledTimes(1);
    });
  });
});
