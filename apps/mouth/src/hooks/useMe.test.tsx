import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import React from "react";
import { useMe } from "./useMe";

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

const validProfile = {
  id: "u_1",
  user_id: "u_1",
  email: "zero@balizero.com",
  name: "Zero",
  role: "admin",
  status: "active",
  avatar: null,
  language: "it",
  language_preference: "it",
  tone: "professional",
  complexity: "medium",
  timezone: "Asia/Bali",
  role_level: "owner",
  metadata: null,
  meta_json: {},
};

describe("useMe", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed profile on success", async () => {
    vi.mocked(api.get).mockResolvedValue(validProfile as never);

    const { result } = renderHook(() => useMe(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    expect(result.current.data?.email).toBe("zero@balizero.com");
    expect(result.current.data?.language).toBe("it");
    expect(result.current.error).toBeUndefined();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/auth/profile");
  });

  it("surfaces schema drift as error (missing required field)", async () => {
    // Missing `email` — required per UserProfile schema.
    const bad = { ...validProfile, email: undefined };
    vi.mocked(api.get).mockResolvedValue(bad as never);

    const { result } = renderHook(() => useMe(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.data).toBeUndefined();
  });

  it("rejects a response that has neither id nor user_id", async () => {
    vi.mocked(api.get).mockResolvedValue({
      ...validProfile,
      id: undefined,
      user_id: undefined,
    } as never);

    const { result } = renderHook(() => useMe(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
  });
});
