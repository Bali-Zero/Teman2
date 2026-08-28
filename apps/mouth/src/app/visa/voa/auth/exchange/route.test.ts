import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/logger", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

/**
 * The magic-link exchange handler. Every test here exists because the failure
 * it pins is SILENT in production: a burnt token, a leaked credential, or a
 * redirect onto an authenticated page with no session all render as an
 * ordinary page, never as an error.
 */

const TOKEN = "t".repeat(40); // >= MagicLinkExchange.token min_length 32
const RESULT_ID = "R".repeat(24); // matches ^[A-Za-z0-9_-]{22,128}$
const FAILURE = "/visa/voa/auth?error=invalid";
const ACCOUNT_COOKIE =
  "garuda_session=opaque-secret; Domain=.balizero.com; HttpOnly; Path=/; SameSite=none; Secure";

function makeRequest(
  fields: Record<string, string> = { magic_token: TOKEN, result_id: RESULT_ID },
): NextRequest {
  return new NextRequest("https://balizero.com/visa/voa/auth/exchange", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(fields).toString(),
  });
}

function upstream(status: number, cookies: string[] = []): Response {
  const headers = new Headers();
  for (const c of cookies) headers.append("set-cookie", c);
  return new Response(null, { status, headers });
}

describe("POST /visa/voa/auth/exchange", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;

  beforeEach(() => {
    process.env.GARUDA_PUBLIC_ENABLED = "true";
  });

  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
    vi.unstubAllGlobals();
  });

  it("404s and never touches the backend when the dark-launch flag is off", async () => {
    // Route handlers do not run layouts, so layout.tsx's notFound() does NOT
    // protect this path. Without the handler's own check this would be the one
    // VOA surface alive in production while the funnel is meant to be dark.
    delete process.env.GARUDA_PUBLIC_ENABLED;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('404s when the flag is the string "false"', async () => {
    process.env.GARUDA_PUBLIC_ENABLED = "false";
    vi.stubGlobal("fetch", vi.fn());
    const { POST } = await import("./route");
    expect((await POST(makeRequest())).status).toBe(404);
  });

  it("redeems the token and forwards the account cookie verbatim", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(upstream(204, [ACCOUNT_COOKIE]));
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(`/visa/voa/upload/${RESULT_ID}`);
    // Verbatim: the attributes are the backend's runtime choice
    // (get_cookie_domain / get_samesite_policy). Reconstructing them here
    // would be a copy that silently goes stale.
    expect(res.headers.getSetCookie()).toEqual([ACCOUNT_COOKIE]);
  });

  it("sends the token in the request BODY, never in the URL", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(upstream(204, [ACCOUNT_COOKIE]));
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    await POST(makeRequest());

    const [target, init] = fetchMock.mock.calls[0];
    expect(String(target)).toBe(
      "https://balizero.com/api/visa/voa/auth/sessions",
    );
    expect(String(target)).not.toContain(TOKEN);
    expect(init.body).toBe(JSON.stringify({ token: TOKEN }));
    // Mandatory, and must satisfy ^[A-Za-z0-9._~-]{16,200}$.
    const key = init.headers["Idempotency-Key"];
    expect(key).toMatch(/^[A-Za-z0-9._~-]{16,200}$/);
  });

  it("uses a FRESH Idempotency-Key per submission", async () => {
    // A same-key replay returns 204 with no Set-Cookie, so a reused key would
    // hand back a redirect with no session — the silent failure below.
    const fetchMock = vi
      .fn()
      .mockResolvedValue(upstream(204, [ACCOUNT_COOKIE]));
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    await POST(makeRequest());
    await POST(makeRequest());

    const keys = fetchMock.mock.calls.map(
      (c: unknown[]) =>
        (c[1] as { headers: Record<string, string> }).headers[
          "Idempotency-Key"
        ],
    );
    expect(new Set(keys).size).toBe(2);
  });

  it("forwards EVERY Set-Cookie, not a comma-folded single value", async () => {
    // Guilt test for `headers.get("set-cookie")` in place of getSetCookie():
    // the folded form is stored by no browser correctly.
    const second = "garuda_extra=x; Path=/; HttpOnly";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(upstream(204, [ACCOUNT_COOKIE, second])),
    );

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.headers.getSetCookie()).toEqual([ACCOUNT_COOKIE, second]);
  });

  it("does NOT land the visitor on the authenticated page when the backend refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream(401)));

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(FAILURE);
    expect(res.headers.getSetCookie()).toEqual([]);
  });

  it("treats a 204 WITHOUT a session cookie as a failure, not a sign-in", async () => {
    // The documented replay outcome. Redirecting to /upload here would put an
    // unauthenticated visitor on an authenticated page.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream(204)));

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.headers.get("location")).toBe(FAILURE);
  });

  it("never echoes the token back into the redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream(401)));

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.headers.get("location")).not.toContain(TOKEN);
  });

  it("survives a transport failure without leaking the token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNRESET")));

    const { POST } = await import("./route");
    const res = await POST(makeRequest());

    expect(res.headers.get("location")).toBe(FAILURE);
  });

  it.each([
    [
      "token one char too short",
      { magic_token: "t".repeat(31), result_id: RESULT_ID },
    ],
    [
      "result_id one char too short",
      { magic_token: TOKEN, result_id: "R".repeat(21) },
    ],
    [
      "result_id with a path traversal",
      { magic_token: TOKEN, result_id: "../../etc" },
    ],
    [
      "result_id with an absolute URL",
      { magic_token: TOKEN, result_id: "https://evil.example" },
    ],
    ["missing token", { result_id: RESULT_ID }],
    ["missing result_id", { magic_token: TOKEN }],
  ])("rejects %s without calling the backend", async (_label, fields) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const res = await POST(makeRequest(fields as Record<string, string>));

    expect(res.headers.get("location")).toBe(FAILURE);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
