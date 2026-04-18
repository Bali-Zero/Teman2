import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import {
  readLanguageCookie,
  useLanguage,
  writeLanguageCookie,
} from "./useLanguage";

vi.mock("@/lib/api", () => ({
  api: {
    patch: vi.fn(),
  },
}));

import { api } from "@/lib/api";

// jsdom exposes a mutable document.cookie — clear it between tests.
function clearAllCookies(): void {
  const all = document.cookie.split(";");
  for (const c of all) {
    const eq = c.indexOf("=");
    const name = (eq > -1 ? c.substring(0, eq) : c).trim();
    if (name) {
      document.cookie = `${name}=; Max-Age=0; Path=/`;
    }
  }
}

describe("useLanguage — cookie plumbing", () => {
  beforeEach(() => {
    clearAllCookies();
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearAllCookies();
    vi.restoreAllMocks();
  });

  it("writeLanguageCookie writes a parseable bz_lang cookie", () => {
    writeLanguageCookie("it");
    expect(document.cookie).toMatch(/bz_lang=it/);
    expect(readLanguageCookie()).toBe("it");
  });

  it("readLanguageCookie returns null when cookie is absent", () => {
    expect(readLanguageCookie()).toBeNull();
  });

  it("readLanguageCookie returns null when cookie holds an unsupported locale", () => {
    // Simulate a stale/foreign cookie from another app.
    document.cookie = "bz_lang=fr; Path=/";
    expect(readLanguageCookie()).toBeNull();
  });
});

describe("useLanguage — hook", () => {
  beforeEach(() => {
    clearAllCookies();
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearAllCookies();
    vi.restoreAllMocks();
  });

  it("defaults to 'en' when no cookie is present", async () => {
    vi.mocked(api.patch).mockResolvedValue({} as never);
    const { result } = renderHook(() => useLanguage());
    expect(result.current.language).toBe("en");
  });

  it("hydrates from an existing cookie on mount", async () => {
    document.cookie = "bz_lang=it; Path=/";
    const { result } = renderHook(() => useLanguage());
    await waitFor(() => expect(result.current.language).toBe("it"));
  });

  it("setLanguage writes cookie AND fires BE sync (happy path)", async () => {
    vi.mocked(api.patch).mockResolvedValue({} as never);
    const { result } = renderHook(() => useLanguage());

    await act(async () => {
      result.current.setLanguage("id");
    });

    // Cookie update is synchronous.
    expect(document.cookie).toMatch(/bz_lang=id/);
    expect(result.current.language).toBe("id");
    // Eventually: BE was called, sync flag flips back to false.
    await waitFor(() => expect(vi.mocked(api.patch)).toHaveBeenCalledTimes(1));
    expect(vi.mocked(api.patch)).toHaveBeenCalledWith("/api/portal/settings", {
      language: "id",
    });
    await waitFor(() => expect(result.current.isSyncing).toBe(false));
  });

  it("setLanguage keeps cookie when BE sync fails (cookie-first tolerance)", async () => {
    vi.mocked(api.patch).mockRejectedValue(new Error("HTTP 500"));
    const { result } = renderHook(() => useLanguage());

    await act(async () => {
      result.current.setLanguage("it");
    });

    // Cookie stays set even though the BE blew up.
    expect(document.cookie).toMatch(/bz_lang=it/);
    expect(result.current.language).toBe("it");
    // And isSyncing must still flip back to false (the finally branch).
    await waitFor(() => expect(result.current.isSyncing).toBe(false));
  });

  it("setLanguage ignores unsupported locales (defensive)", () => {
    const { result } = renderHook(() => useLanguage());

    act(() => {
      // Cast: callers sometimes pass dynamic values (e.g. from a URL).
      (result.current.setLanguage as (l: string) => void)("fr");
    });

    // Cookie must NOT be set to a bogus value, language must not change.
    expect(document.cookie).not.toMatch(/bz_lang=fr/);
    expect(result.current.language).toBe("en");
  });
});
