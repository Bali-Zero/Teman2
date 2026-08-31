import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PENDING_COOKIE } from "./contract";

/**
 * `GET /visa/voa/auth` — the emailed link's landing. Its whole job is to get
 * the token OUT of the URL before any document renders, because every page in
 * this app inherits Google Analytics from the root layout and GA reads
 * `window.location.href`.
 */

const TOKEN = "t".repeat(40);
const RESULT_ID = "R".repeat(24);
const FAILURE = "/visa/voa/auth/continue?error=invalid";

function makeGet(
  query: string = `?magic_token=${TOKEN}&result_id=${RESULT_ID}`,
  origin = "https://balizero.com",
): NextRequest {
  return new NextRequest(`${origin}/visa/voa/auth${query}`, { method: "GET" });
}

function pendingCookie(res: Response): string | undefined {
  return res.headers
    .getSetCookie()
    .find((c) => c.startsWith(`${PENDING_COOKIE}=`));
}

describe("GET /visa/voa/auth", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;

  beforeEach(() => {
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    // Nothing here may reach the network: redemption happens on the POST.
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
    vi.unstubAllGlobals();
  });

  it("404s when the dark-launch flag is off", async () => {
    delete process.env.GARUDA_PUBLIC_ENABLED;
    const { GET } = await import("./route");
    const res = await GET(makeGet());
    expect(res.status).toBe(404);
    expect(res.headers.getSetCookie()).toEqual([]);
  });

  it('404s when the flag is the string "false"', async () => {
    process.env.GARUDA_PUBLIC_ENABLED = "false";
    const { GET } = await import("./route");
    expect((await GET(makeGet())).status).toBe(404);
  });

  it("redeems NOTHING — it never calls the backend", async () => {
    const { GET } = await import("./route");
    await GET(makeGet());
    expect(fetch).not.toHaveBeenCalled();
  });

  it("moves the token into an HttpOnly cookie and out of the URL", async () => {
    const { GET } = await import("./route");
    const res = await GET(makeGet());

    expect(res.status).toBe(303);
    const location = res.headers.get("location") ?? "";
    // THE point of this route: the next URL the browser renders — the one GA
    // will report as page_location — carries no credential.
    expect(location).not.toContain(TOKEN);
    // And NOTHING else either: the result id moved into the cookie too, bound
    // to the token it was issued with (council finding, 2026-08-28).
    expect(location).toBe("/visa/voa/auth/continue");
    expect(location).not.toContain(RESULT_ID);

    const cookie = pendingCookie(res);
    expect(cookie).toContain(TOKEN);
    expect(cookie).toContain(`${PENDING_COOKIE}=${RESULT_ID}.${TOKEN}`);
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("Secure");
    expect(cookie).toContain("SameSite=Lax");
    // Scoped: the credential must not ride along on every other request to
    // balizero.com.
    expect(cookie).toContain("Path=/visa/voa/auth");
    expect(cookie).toMatch(/Max-Age=\d+/);
  });

  // ONLY the `localhost` entry of LOOPBACK_HOSTS is exercised here, and the
  // single case is deliberate. `NextRequest` rewrites the hostname of every
  // other spelling of loopback to `localhost` before the route ever reads it
  // — measured 2026-08-29: `new NextRequest("http://127.0.0.1:3000/x")` gives
  // `new URL(request.url).hostname === "localhost"`, while a plain
  // `new URL("http://127.0.0.1:3000/x")` keeps `127.0.0.1`. So a
  // `127.0.0.1` (or `[::1]`) row passes through the `localhost` entry and
  // cannot fail if its own entry is deleted: dropping `127.0.0.1` from the set
  // leaves this whole file GREEN, while dropping `localhost` turns the test
  // directly below RED — which is why the two-row `it.each` this replaced was
  // never two independent assertions. Stated as a direction, not a count, so
  // it cannot quietly disagree with the file: re-derive it by deleting an
  // entry and re-running this file. The other three entries stay in the set as
  // defensive parity with the backend's `_LOOPBACK_HOSTS` and carry no test,
  // because a test that cannot fail is worse than no test.
  it("omits Secure on localhost so local dev can accept the cookie", async () => {
    const { GET } = await import("./route");
    const res = await GET(makeGet(undefined, "http://localhost:3000"));
    expect(pendingCookie(res)).not.toContain("Secure");
  });

  it("still sets Secure on a real host", async () => {
    const { GET } = await import("./route");
    expect(pendingCookie(await GET(makeGet()))).toContain("Secure");
  });

  it("asks the browser not to pass this URL on as a referrer", async () => {
    const { GET } = await import("./route");
    const res = await GET(makeGet());
    expect(res.headers.get("referrer-policy")).toBe("no-referrer");
  });

  it("does not leak the token via cache or referrer on the flag-off 404", async () => {
    process.env.GARUDA_PUBLIC_ENABLED = "false";
    const { GET } = await import("./route");
    const res = await GET(makeGet());

    expect(res.status).toBe(404);
    // The request URL holds a token even on this path; a bare 404 with no
    // headers would let it reach a cache or the next page's Referer.
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(res.headers.get("referrer-policy")).toBe("no-referrer");
  });

  it.each([
    [
      "token one char too short",
      `?magic_token=${"t".repeat(31)}&result_id=${RESULT_ID}`,
    ],
    [
      "result_id one char too short",
      `?magic_token=${TOKEN}&result_id=${"R".repeat(21)}`,
    ],
    [
      "result_id with a path traversal",
      `?magic_token=${TOKEN}&result_id=..%2F..%2Fetc`,
    ],
    ["no parameters at all", ""],
    ["token only", `?magic_token=${TOKEN}`],
    ["result_id only", `?result_id=${RESULT_ID}`],
  ])("rejects %s and sets no pending cookie", async (_label, query) => {
    const { GET } = await import("./route");
    const res = await GET(makeGet(query));

    expect(res.headers.get("location")).toBe(FAILURE);
    expect(pendingCookie(res)).toBeUndefined();
    expect(res.headers.get("location")).not.toContain(TOKEN);
  });
});
