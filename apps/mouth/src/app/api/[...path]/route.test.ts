/**
 * Unit tests for the [...path] catch-all proxy — Bug A regression suite.
 *
 * Scope:
 *  - POST/PUT/PATCH/DELETE with nz_csrf_token cookie → X-CSRF-Token header promoted
 *  - GET does NOT promote the header
 *  - DELETE with body still works (non-upload mutation regression guard)
 *  - No CSRF cookie present → no header added
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Minimal NextRequest shim
// next/server is not available in jsdom; we replicate only what the proxy uses.
// ---------------------------------------------------------------------------
class MockNextRequest {
  readonly url: string;
  readonly method: string;
  readonly headers: Headers;
  readonly cookies: {
    get: (name: string) => { value: string } | undefined;
  };
  private _body: ArrayBuffer | FormData | undefined;

  constructor(
    url: string,
    init: {
      method?: string;
      headers?: HeadersInit;
      cookies?: Record<string, string>;
      body?: ArrayBuffer | FormData;
    } = {},
  ) {
    this.url = url;
    this.method = init.method ?? "GET";
    this.headers = new Headers(init.headers ?? {});
    const cookieMap = init.cookies ?? {};
    this.cookies = {
      get: (name: string) =>
        name in cookieMap ? { value: cookieMap[name] } : undefined,
    };
    this._body = init.body;
  }

  async arrayBuffer(): Promise<ArrayBuffer> {
    return this._body instanceof ArrayBuffer ? this._body : new ArrayBuffer(0);
  }
  async formData(): Promise<FormData> {
    return this._body instanceof FormData ? this._body : new FormData();
  }
}

vi.mock("next/server", () => ({
  NextResponse: { json: vi.fn() },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Capture the headers the proxy actually sent to the upstream fetch
// ---------------------------------------------------------------------------
function capturedHeaders(fetchMock: ReturnType<typeof vi.fn>): Headers {
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return init.headers as Headers;
}

function capturedTargetUrl(fetchMock: ReturnType<typeof vi.fn>): string {
  const [targetUrl] = fetchMock.mock.calls[0] as [string, RequestInit];
  return targetUrl;
}

// ---------------------------------------------------------------------------
// Import the handlers AFTER mocking next/server
// ---------------------------------------------------------------------------
import { logger } from "@/lib/logger";
import { DELETE, GET, PATCH, POST, PUT } from "./route";

describe("proxy catch-all route — CSRF header promotion (Bug A)", () => {
  const CSRF_TOKEN = "test-csrf-token-abc123";

  beforeEach(() => {
    // Provide a stubbed upstream response for every test
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    process.env.NUZANTARA_API_URL = "https://nuzantara-rag.fly.dev";
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // POST (primary upload path)
  // -------------------------------------------------------------------------
  it("promotes nz_csrf_token cookie → X-CSRF-Token header on POST", async () => {
    const req = new MockNextRequest(
      "http://localhost/api/portal/documents/upload",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        cookies: { nz_csrf_token: CSRF_TOKEN, nz_access_token: "jwt-xyz" },
        body: new TextEncoder().encode(JSON.stringify({ x: 1 })).buffer,
      },
    );

    await POST(req as never);

    const sentHeaders = capturedHeaders(vi.mocked(global.fetch));
    expect(sentHeaders.get("X-CSRF-Token")).toBe(CSRF_TOKEN);
  });

  // -------------------------------------------------------------------------
  // PUT
  // -------------------------------------------------------------------------
  it("promotes nz_csrf_token cookie → X-CSRF-Token header on PUT", async () => {
    const req = new MockNextRequest("http://localhost/api/portal/documents/1", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      cookies: { nz_csrf_token: CSRF_TOKEN },
    });

    await PUT(req as never);

    expect(capturedHeaders(vi.mocked(global.fetch)).get("X-CSRF-Token")).toBe(
      CSRF_TOKEN,
    );
  });

  // -------------------------------------------------------------------------
  // PATCH
  // -------------------------------------------------------------------------
  it("promotes nz_csrf_token cookie → X-CSRF-Token header on PATCH", async () => {
    const req = new MockNextRequest("http://localhost/api/portal/documents/1", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      cookies: { nz_csrf_token: CSRF_TOKEN },
    });

    await PATCH(req as never);

    expect(capturedHeaders(vi.mocked(global.fetch)).get("X-CSRF-Token")).toBe(
      CSRF_TOKEN,
    );
  });

  // -------------------------------------------------------------------------
  // DELETE — non-upload mutation regression guard
  // -------------------------------------------------------------------------
  it("promotes nz_csrf_token cookie → X-CSRF-Token header on DELETE", async () => {
    const req = new MockNextRequest("http://localhost/api/portal/documents/5", {
      method: "DELETE",
      cookies: { nz_csrf_token: CSRF_TOKEN },
    });

    await DELETE(req as never);

    expect(capturedHeaders(vi.mocked(global.fetch)).get("X-CSRF-Token")).toBe(
      CSRF_TOKEN,
    );
  });

  // -------------------------------------------------------------------------
  // GET — must NOT add header (safe method, no CSRF needed)
  // -------------------------------------------------------------------------
  it("does NOT add X-CSRF-Token header on GET even when cookie is present", async () => {
    const req = new MockNextRequest("http://localhost/api/portal/documents", {
      method: "GET",
      cookies: { nz_csrf_token: CSRF_TOKEN },
    });

    await GET(req as never);

    expect(
      capturedHeaders(vi.mocked(global.fetch)).get("X-CSRF-Token"),
    ).toBeNull();
  });

  // -------------------------------------------------------------------------
  // No CSRF cookie → no header injected
  // -------------------------------------------------------------------------
  it("does NOT add X-CSRF-Token header when nz_csrf_token cookie is absent", async () => {
    const req = new MockNextRequest(
      "http://localhost/api/portal/documents/upload",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        cookies: { nz_access_token: "jwt-xyz" }, // only auth cookie, no CSRF
      },
    );

    await POST(req as never);

    expect(
      capturedHeaders(vi.mocked(global.fetch)).get("X-CSRF-Token"),
    ).toBeNull();
  });
});

describe("proxy catch-all route — auth failure logging", () => {
  beforeEach(() => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    process.env.NUZANTARA_API_URL = "https://nuzantara-rag.fly.dev";
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("does not emit an error log for an unauthenticated 401 without credentials", async () => {
    const req = new MockNextRequest("http://localhost/api/dashboard/summary", {
      method: "GET",
    });

    const response = await GET(req as never);

    expect(response.status).toBe(401);
    expect(logger.warn).toHaveBeenCalledWith(
      "[Proxy] Auth rejected 401 for GET /api/dashboard/summary without credentials",
      expect.objectContaining({
        action: "auth_rejected",
      }),
    );
    expect(logger.error).not.toHaveBeenCalled();
  });

  it("keeps error logging for credentialed auth failures", async () => {
    const req = new MockNextRequest("http://localhost/api/auth/profile", {
      method: "GET",
      cookies: { nz_access_token: "stale-jwt" },
    });

    const response = await GET(req as never);

    expect(response.status).toBe(401);
    expect(logger.error).toHaveBeenCalledWith(
      "[Proxy] Auth error 401 for GET /api/auth/profile",
      expect.objectContaining({
        action: "error",
      }),
      expect.any(Error),
    );
  });
});

describe("proxy catch-all route — backend URL normalization", () => {
  beforeEach(() => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("trims whitespace from the configured backend base URL before proxying", async () => {
    process.env.NUZANTARA_API_URL = "https://nuzantara-rag.fly.dev\n";
    const req = new MockNextRequest("http://localhost/api/health", {
      method: "GET",
    });

    await GET(req as never);

    expect(capturedTargetUrl(vi.mocked(global.fetch))).toBe(
      "https://nuzantara-rag.fly.dev/api/health",
    );
  });
});
