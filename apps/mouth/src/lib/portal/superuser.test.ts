import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchPortalSuperuser } from "./superuser";

describe("fetchPortalSuperuser", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the superuser status and email", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ is_superuser: true, email: "admin@example.test" }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchPortalSuperuser("token")).resolves.toEqual({
      isSuperuser: true,
      email: "admin@example.test",
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/portal/admin/me", {
      credentials: "include",
      headers: { Authorization: "Bearer token" },
      signal: expect.any(AbortSignal),
    });
  });

  it("returns false for a non-superuser response without an authorization header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ is_superuser: false, email: null })),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchPortalSuperuser()).resolves.toEqual({
      isSuperuser: false,
      email: null,
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/portal/admin/me", {
      credentials: "include",
      headers: undefined,
      signal: expect.any(AbortSignal),
    });
  });

  it("returns false for a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
    );

    await expect(fetchPortalSuperuser()).resolves.toEqual({
      isSuperuser: false,
      email: null,
    });
  });

  it("returns false for invalid JSON or a non-boolean flag", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response("not json"))
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ is_superuser: "true" })),
        ),
    );

    await expect(fetchPortalSuperuser()).resolves.toEqual({
      isSuperuser: false,
      email: null,
    });
    await expect(fetchPortalSuperuser()).resolves.toEqual({
      isSuperuser: false,
      email: null,
    });
  });

  it("returns false when fetch throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network unavailable")),
    );

    await expect(fetchPortalSuperuser()).resolves.toEqual({
      isSuperuser: false,
      email: null,
    });
  });
});
