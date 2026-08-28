import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PENDING_COOKIE } from "../contract";

vi.mock("@/lib/logger", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

/**
 * The magic-link exchange. Every test here pins a failure that is SILENT in
 * production: a burnt token, a leaked credential, a live credential left in
 * the browser, or a redirect onto an authenticated page with no session.
 */

const TOKEN = "t".repeat(40);
const RESULT_ID = "R".repeat(24);
const FAILURE = "/visa/voa/auth/continue?error=invalid";
const ACCOUNT_COOKIE =
  "garuda_session=opaque-secret; Domain=.balizero.com; HttpOnly; Path=/; SameSite=none; Secure";

function makePost({
  token = TOKEN,
  resultId = RESULT_ID,
  origin = "https://balizero.com",
}: {
  token?: string | null;
  resultId?: string | null;
  origin?: string;
} = {}): NextRequest {
  const headers: Record<string, string> = {
    "content-type": "application/x-www-form-urlencoded",
  };
  if (token !== null) headers.cookie = `${PENDING_COOKIE}=${token}`;
  const body = new URLSearchParams(
    resultId === null ? {} : { result_id: resultId },
  );
  return new NextRequest(`${origin}/visa/voa/auth/exchange`, {
    method: "POST",
    headers,
    body: body.toString(),
  });
}

function upstream(status: number, cookies: string[] = []): Response {
  const headers = new Headers();
  for (const c of cookies) headers.append("set-cookie", c);
  return new Response(null, { status, headers });
}

function cleared(res: Response): boolean {
  return res.headers
    .getSetCookie()
    .some((c) => c.startsWith(`${PENDING_COOKIE}=`) && c.includes("Max-Age=0"));
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
    const res = await POST(makePost());

    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('404s when the flag is the string "false"', async () => {
    process.env.GARUDA_PUBLIC_ENABLED = "false";
    vi.stubGlobal("fetch", vi.fn());
    const { POST } = await import("./route");
    expect((await POST(makePost())).status).toBe(404);
  });

  it("reads the token from the HttpOnly cookie, not the form body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(upstream(204, [ACCOUNT_COOKIE]));
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    await POST(makePost());

    const [target, init] = fetchMock.mock.calls[0];
    expect(String(target)).toBe(
      "https://balizero.com/api/visa/voa/auth/sessions",
    );
    expect(String(target)).not.toContain(TOKEN);
    expect(init.body).toBe(JSON.stringify({ token: TOKEN }));
    expect(init.headers["Idempotency-Key"]).toMatch(
      /^[A-Za-z0-9._~-]{16,200}$/,
    );
  });

  it("refuses when no pending cookie is present", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const res = await POST(makePost({ token: null }));

    expect(res.headers.get("location")).toBe(FAILURE);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses a FRESH Idempotency-Key per submission", async () => {
    // A same-key replay returns 204 with no Set-Cookie, so reusing one would
    // hand back a redirect with no session.
    const fetchMock = vi
      .fn()
      .mockResolvedValue(upstream(204, [ACCOUNT_COOKIE]));
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    await POST(makePost());
    await POST(makePost());

    const keys = fetchMock.mock.calls.map(
      (c: unknown[]) =>
        (c[1] as { headers: Record<string, string> }).headers[
          "Idempotency-Key"
        ],
    );
    expect(new Set(keys).size).toBe(2);
  });

  it("forwards the account cookie verbatim and redirects to upload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(upstream(204, [ACCOUNT_COOKIE])),
    );

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(`/visa/voa/upload/${RESULT_ID}`);
    // Verbatim: the attributes are the backend's runtime choice
    // (get_cookie_domain / get_samesite_policy). Reconstructing them here
    // would be a copy that silently goes stale.
    expect(res.headers.getSetCookie()).toContain(ACCOUNT_COOKIE);
  });

  it("forwards EVERY Set-Cookie, not a comma-folded single value", async () => {
    // Guilt test for `headers.get("set-cookie")` in place of getSetCookie():
    // the folded form is stored correctly by no browser.
    const second = "garuda_extra=x; Path=/; HttpOnly";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(upstream(204, [ACCOUNT_COOKIE, second])),
    );

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.headers.getSetCookie()).toContain(ACCOUNT_COOKIE);
    expect(res.headers.getSetCookie()).toContain(second);
  });

  it("requires the account cookie BY NAME, not merely that some cookie came back", async () => {
    // Adversarial review 2026-08-28: a length check passes when the backend
    // emits any unrelated cookie on the no-op/replay 204 path, landing an
    // unauthenticated visitor on the authenticated upload page.
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(upstream(204, ["garuda_extra=x; Path=/; HttpOnly"])),
    );

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.headers.get("location")).toBe(FAILURE);
  });

  it("treats a 204 with no cookies at all as a failure, not a sign-in", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream(204)));

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.headers.get("location")).toBe(FAILURE);
  });

  it("does NOT land the visitor on the authenticated page when the backend refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream(401)));

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(FAILURE);
    expect(
      res.headers.getSetCookie().some((c) => c.startsWith("garuda_session=")),
    ).toBe(false);
  });

  it("never echoes the token back into the redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream(401)));

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.headers.get("location")).not.toContain(TOKEN);
  });

  it("survives a transport failure without leaking the token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNRESET")));

    const { POST } = await import("./route");
    const res = await POST(makePost());

    expect(res.headers.get("location")).toBe(FAILURE);
  });

  it.each([
    ["success", 204, [ACCOUNT_COOKIE]],
    ["refusal", 401, []],
    ["replay with no session cookie", 204, []],
  ])(
    "expires the pending cookie on %s — no live credential left behind",
    async (_label, status, cookies) => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(upstream(status as number, cookies as string[])),
      );

      const { POST } = await import("./route");
      const res = await POST(makePost());

      expect(cleared(res)).toBe(true);
    },
  );

  it("expires the pending cookie even when the form is malformed", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const { POST } = await import("./route");
    const res = await POST(makePost({ resultId: null }));

    expect(res.headers.get("location")).toBe(FAILURE);
    expect(cleared(res)).toBe(true);
  });

  it.each([
    ["token one char too short", { token: "t".repeat(31) }],
    ["result_id one char too short", { resultId: "R".repeat(21) }],
    ["result_id with a path traversal", { resultId: "../../etc" }],
    ["result_id with an absolute URL", { resultId: "https://evil.example" }],
  ])("rejects %s without calling the backend", async (_label, over) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const res = await POST(makePost(over));

    expect(res.headers.get("location")).toBe(FAILURE);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
