import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/logger", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

function makeRequest(init: {
  authorization?: string;
  cookie?: string;
}): NextRequest {
  const headers: Record<string, string> = {};
  if (init.authorization) headers.authorization = init.authorization;
  if (init.cookie) headers.cookie = init.cookie;
  return new NextRequest("https://my.balizero.com/api/auth/portal-superuser", {
    method: "GET",
    headers,
  });
}

function upstream(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

describe("GET /api/auth/portal-superuser", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("answers 'no' without a session and never calls upstream", async () => {
    const fetchMock = upstream(200, { is_superuser: true });
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./route");

    const res = await GET(makeRequest({}));

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ success: true, is_superuser: false });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards a bearer session to the backend probe and relays a superuser", async () => {
    const fetchMock = upstream(200, { success: true, is_superuser: true });
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./route");

    const res = await GET(makeRequest({ authorization: "Bearer tok-1" }));

    expect(await res.json()).toEqual({ success: true, is_superuser: true });
    expect(res.headers.get("cache-control")).toBe("no-store");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/portal\/admin\/me$/);
    expect(init.headers).toEqual({ Authorization: "Bearer tok-1" });
  });

  it("turns the httpOnly session cookie into a bearer for the backend", async () => {
    const fetchMock = upstream(200, { is_superuser: false });
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./route");

    const res = await GET(
      makeRequest({ cookie: "nz_csrf_token=c; nz_access_token=tok-2" }),
    );

    expect(await res.json()).toEqual({ success: true, is_superuser: false });
    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      Authorization: "Bearer tok-2",
    });
  });

  it.each([
    ["upstream 401", 401, { detail: "Authentication required" }],
    ["upstream 500", 500, {}],
    ["non-boolean flag", 200, { is_superuser: "yes" }],
  ])("reads %s as 'no'", async (_label, status, body) => {
    vi.stubGlobal("fetch", upstream(status, body));
    const { GET } = await import("./route");

    const res = await GET(makeRequest({ authorization: "Bearer tok-3" }));

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ success: true, is_superuser: false });
  });

  it("reads a transport failure as 'no' instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const { GET } = await import("./route");

    const res = await GET(makeRequest({ authorization: "Bearer tok-4" }));

    expect(await res.json()).toEqual({ success: true, is_superuser: false });
  });
});
