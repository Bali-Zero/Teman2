import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import React from "react";
import { useNotificationPrefs } from "./useNotificationPrefs";
import { ApiError } from "@/lib/api/error-handler";

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

const validPrefs = {
  email_enabled: true,
  wa_enabled: false,
  wa_phone: null,
};

describe("useNotificationPrefs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed prefs on GET success", async () => {
    vi.mocked(api.get).mockResolvedValue(validPrefs as never);

    const { result } = renderHook(() => useNotificationPrefs(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    expect(result.current.data?.email_enabled).toBe(true);
    expect(result.current.migrationMissing).toBe(false);
    expect(result.current.error).toBeUndefined();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith(
      "/api/portal/notifications/prefs",
    );
  });

  it("gracefully handles a client-safe 503 on GET by status", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError("Notification preferences are temporarily unavailable", 503),
    );

    const { result } = renderHook(() => useNotificationPrefs(), { wrapper });
    await waitFor(() => expect(result.current.migrationMissing).toBe(true));

    expect(result.current.data).toBeNull();
    // Migration-missing must NOT leak as a hard error — UI stays alive.
    expect(result.current.error).toBeUndefined();
  });

  it("surfaces non-migration errors through SWR", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("HTTP 500"));

    const { result } = renderHook(() => useNotificationPrefs(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.migrationMissing).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it("updatePrefs PUTs and updates local cache on success", async () => {
    vi.mocked(api.get).mockResolvedValue(validPrefs as never);
    const newPrefs = {
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "628123456789",
    };
    vi.mocked(api.put).mockResolvedValue(newPrefs as never);

    const { result } = renderHook(() => useNotificationPrefs(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    let returned;
    await act(async () => {
      returned = await result.current.updatePrefs(newPrefs);
    });

    expect(returned).toEqual(newPrefs);
    expect(vi.mocked(api.put)).toHaveBeenCalledWith(
      "/api/portal/notifications/prefs",
      newPrefs,
    );
    await waitFor(() => expect(result.current.data?.wa_enabled).toBe(true));
    expect(result.current.isUpdating).toBe(false);
  });

  it("updatePrefs maps a client-safe 503 to the unavailable flag", async () => {
    vi.mocked(api.get).mockResolvedValue(validPrefs as never);
    vi.mocked(api.put).mockRejectedValue(
      new ApiError("Notification preferences are temporarily unavailable", 503),
    );

    const { result } = renderHook(() => useNotificationPrefs(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    let returned: unknown = undefined;
    await act(async () => {
      returned = await result.current.updatePrefs({
        email_enabled: false,
        wa_enabled: false,
        wa_phone: null,
      });
    });

    // Hook swallows the 503 and returns null.
    expect(returned).toBeNull();
    expect(result.current.migrationMissing).toBe(true);
    expect(result.current.data).toBeNull();
  });
});
