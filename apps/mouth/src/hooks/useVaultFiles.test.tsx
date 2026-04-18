import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import React from "react";
import { useVaultFiles } from "./useVaultFiles";

// Mock the api module the hook depends on.
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

const validFile = {
  id: 1,
  type: "passport",
  name: "passport.pdf",
  status: "verified",
  expiry_date: null,
  size_kb: 100,
  practice_id: null,
  practice_name: null,
  downloadable: true,
  created_at: "2026-04-18T00:00:00Z",
};

const validResp = {
  success: true,
  data: [validFile],
};

describe("useVaultFiles", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed vault files on success", async () => {
    vi.mocked(api.get).mockResolvedValue(validResp as never);

    const { result } = renderHook(() => useVaultFiles(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].id).toBe(1);
    expect(result.current.data?.[0].name).toBe("passport.pdf");
    expect(result.current.error).toBeUndefined();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/portal/documents");
  });

  it("surfaces schema drift as error", async () => {
    // Wrong item shape: missing required `id`, `type`, `name`, `downloadable`,
    // `created_at`. Zod parse must throw.
    vi.mocked(api.get).mockResolvedValue({
      success: true,
      data: [{ foo: "bar" }],
    } as never);

    const { result } = renderHook(() => useVaultFiles(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.data).toBeUndefined();
  });

  it("surfaces non-success envelope as error", async () => {
    vi.mocked(api.get).mockResolvedValue({
      success: false,
      data: [],
    } as never);

    const { result } = renderHook(() => useVaultFiles(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.error?.message).toBe("Vault response not successful");
    expect(result.current.data).toBeUndefined();
  });

  it("accepts an empty list without error", async () => {
    vi.mocked(api.get).mockResolvedValue({
      success: true,
      data: [],
    } as never);

    const { result } = renderHook(() => useVaultFiles(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    expect(result.current.data).toEqual([]);
    expect(result.current.error).toBeUndefined();
  });

  it("revalidates on explicit mutate (stale-while-revalidate)", async () => {
    const first = { success: true, data: [validFile] };
    const second = {
      success: true,
      data: [validFile, { ...validFile, id: 2, name: "visa.pdf" }],
    };
    vi.mocked(api.get)
      .mockResolvedValueOnce(first as never)
      .mockResolvedValueOnce(second as never);

    const { result } = renderHook(() => useVaultFiles(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data).toHaveLength(1);

    // Trigger revalidation — SWR keeps stale data visible while fetching.
    await act(async () => {
      await result.current.mutate();
    });
    await waitFor(() => expect(result.current.data).toHaveLength(2));

    expect(result.current.data?.[1].id).toBe(2);
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(2);
  });
});
