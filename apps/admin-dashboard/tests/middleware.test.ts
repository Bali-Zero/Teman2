import { SignJWT } from "jose";
import { NextRequest, NextResponse } from "next/server";
import { beforeAll, describe, expect, it } from "vitest";

import { middleware } from "@/middleware";

const SECRET_STRING = "test-secret-please-ignore-32bytes-minimum-length!!";
const secret = new TextEncoder().encode(SECRET_STRING);

async function sign(payload: Record<string, unknown>): Promise<string> {
  return await new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime(Math.floor(Date.now() / 1000) + 3600)
    .sign(secret);
}

function buildRequest(
  pathname: string,
  cookie: string | null,
  origin = "https://admin.balizero.com",
): NextRequest {
  const url = new URL(`${origin}${pathname}`);
  const headers = new Headers();
  if (cookie) {
    headers.set("cookie", `nz_access_token=${cookie}`);
  }
  return new NextRequest(url, { headers });
}

beforeAll(() => {
  process.env.JWT_SECRET_KEY = SECRET_STRING;
  delete process.env.ADMIN_EMAILS;
});

describe("admin-dashboard middleware — API routes", () => {
  it("returns 401 JSON when cookie is missing on /api/qdrant/collections", async () => {
    const req = buildRequest("/api/qdrant/collections", null);
    const res = await middleware(req);
    expect(res).toBeDefined();
    expect(res!.status).toBe(401);
    expect(res!.headers.get("www-authenticate")).toContain("Bearer");
    const body = await res!.json();
    expect(body.error).toBe("unauthenticated");
  });

  it("returns 401 JSON when token is malformed", async () => {
    const req = buildRequest("/api/postgres/users", "not-a-jwt");
    const res = await middleware(req);
    expect(res!.status).toBe(401);
  });

  it("returns 403 JSON when authenticated as role=client", async () => {
    const token = await sign({
      email: "client@example.com",
      role: "client",
      type: "access",
    });
    const req = buildRequest("/api/qdrant/collections", token);
    const res = await middleware(req);
    expect(res!.status).toBe(403);
    const body = await res!.json();
    expect(body.error).toBe("forbidden");
  });

  it("passes through (no rewrite/redirect) when role=admin on an API route", async () => {
    const token = await sign({
      email: "zero@balizero.com",
      role: "admin",
      type: "access",
    });
    const req = buildRequest("/api/qdrant/collections", token);
    const res = await middleware(req);
    expect(res).toBeDefined();
    // NextResponse.next() surfaces as a 200 with no body to the runtime; the
    // important invariant is that we don't return 401/403/redirect.
    expect(res!.status).toBe(200);
    expect(res!.headers.get("location")).toBeNull();
    expect(res!.headers.get("x-admin-email")).toBe("zero@balizero.com");
  });
});

describe("admin-dashboard middleware — HTML pages", () => {
  it("redirects to kita login when cookie missing on /qdrant", async () => {
    const req = buildRequest("/qdrant", null);
    const res = await middleware(req);
    expect(res!.status).toBeGreaterThanOrEqual(300);
    expect(res!.status).toBeLessThan(400);
    const location = res!.headers.get("location");
    expect(location).toContain("kita.balizero.com/login");
    expect(location).toContain(encodeURIComponent("/qdrant"));
  });

  it("redirects to kita login when token invalid on a page", async () => {
    const req = buildRequest("/postgres", "invalid.jwt.here");
    const res = await middleware(req);
    const location = res!.headers.get("location");
    expect(location).toContain("kita.balizero.com/login");
  });

  it("returns plain-text 403 (no redirect loop) when logged-in non-admin hits a page", async () => {
    const token = await sign({
      email: "client@example.com",
      role: "client",
      type: "access",
    });
    const req = buildRequest("/postgres", token);
    const res = await middleware(req);
    expect(res!.status).toBe(403);
    expect(res!.headers.get("location")).toBeNull();
  });

  it("passes through admin on a page", async () => {
    const token = await sign({
      email: "zero@balizero.com",
      role: "admin",
      type: "access",
    });
    const req = buildRequest("/postgres", token);
    const res = await middleware(req);
    expect(res!.status).toBe(200);
    expect(res!.headers.get("location")).toBeNull();
  });

  it("passes through local development pages without bouncing to production login", async () => {
    expect(process.env.NODE_ENV).not.toBe("production");
    const req = buildRequest("/autonomous-lab", null, "http://localhost:3311");
    const res = await middleware(req);
    expect(res!.status).toBe(200);
    expect(res!.headers.get("location")).toBeNull();
  });
});

/**
 * `/api/clients` decides between "the whole client book" and "only the rows
 * assigned to you" from `x-admin-email`. That header is only trustworthy
 * because middleware drops whatever the caller sent and re-stamps it from the
 * verified JWT — so both halves get pinned here.
 *
 * The forwarded value is observable through Next's request-override protocol:
 * `NextResponse.next({ request: { headers } })` emits
 * `x-middleware-override-headers` plus one `x-middleware-request-<name>` per
 * overridden header (verified empirically against next ^16.2.12, not assumed).
 */
describe("admin-dashboard middleware — x-admin-email is stamped, never accepted", () => {
  function buildRequestWithHeaders(
    pathname: string,
    cookie: string,
    extra: Record<string, string>,
  ): NextRequest {
    const headers = new Headers();
    headers.set("cookie", `nz_access_token=${cookie}`);
    for (const [k, v] of Object.entries(extra)) headers.set(k, v);
    return new NextRequest(new URL(`https://admin.balizero.com${pathname}`), {
      headers,
    });
  }

  const forwarded = (res: NextResponse | undefined): string | null =>
    res!.headers.get("x-middleware-request-x-admin-email");

  it("GUILT: a caller-supplied x-admin-email is replaced by the verified one", async () => {
    const token = await sign({
      email: "ari@balizero.com",
      role: "admin",
      type: "access",
    });
    const req = buildRequestWithHeaders("/api/clients", token, {
      // ari is a legitimate admin, but not one of the three full-access users;
      // this is the escalation attempt.
      "x-admin-email": "zero@balizero.com",
    });
    const res = await middleware(req);
    expect(res!.status).toBe(200);
    expect(forwarded(res)).toBe("ari@balizero.com");
    expect(forwarded(res)).not.toBe("zero@balizero.com");
  });

  it("GUILT: capitalised header name cannot smuggle a second value", async () => {
    const token = await sign({
      email: "ari@balizero.com",
      role: "admin",
      type: "access",
    });
    const req = buildRequestWithHeaders("/api/clients", token, {
      "X-Admin-Email": "zero@balizero.com",
    });
    const res = await middleware(req);
    expect(forwarded(res)).toBe("ari@balizero.com");
  });

  it("INNOCENCE: an ordinary admin request carries their own verified email", async () => {
    const token = await sign({
      email: "ari@balizero.com",
      role: "admin",
      type: "access",
    });
    const req = buildRequestWithHeaders("/api/clients", token, {});
    const res = await middleware(req);
    expect(res!.headers.get("x-middleware-override-headers")).toContain(
      "x-admin-email",
    );
    expect(forwarded(res)).toBe("ari@balizero.com");
  });

  it("INNOCENCE: a full-access owner still reaches the handler as themselves", async () => {
    const token = await sign({
      email: "zero@balizero.com",
      role: "owner",
      type: "access",
    });
    const req = buildRequestWithHeaders("/api/clients", token, {});
    const res = await middleware(req);
    expect(forwarded(res)).toBe("zero@balizero.com");
  });

  it("a rejected request forwards no email at all", async () => {
    const req = buildRequestWithHeaders("/api/clients", "not-a-jwt", {
      "x-admin-email": "zero@balizero.com",
    });
    const res = await middleware(req);
    expect(res!.status).toBe(401);
    expect(forwarded(res)).toBeNull();
  });
});

describe("admin-dashboard middleware — asset bypass", () => {
  it("lets /_next/static assets through even without cookie", async () => {
    const req = buildRequest("/_next/static/chunks/main.js", null);
    const res = await middleware(req);
    expect(res!.status).toBe(200);
    expect(res!.headers.get("location")).toBeNull();
  });

  it("lets /favicon.ico through", async () => {
    const req = buildRequest("/favicon.ico", null);
    const res = await middleware(req);
    expect(res!.status).toBe(200);
  });
});
