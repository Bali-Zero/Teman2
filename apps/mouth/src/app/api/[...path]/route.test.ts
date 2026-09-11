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
  readonly body: ReadableStream<Uint8Array> | null;
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
      bodyChunks?: Uint8Array[];
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
    const chunks =
      init.bodyChunks ??
      (init.body instanceof ArrayBuffer ? [new Uint8Array(init.body)] : []);
    this.body =
      chunks.length > 0
        ? new ReadableStream<Uint8Array>({
            start(controller) {
              for (const chunk of chunks) controller.enqueue(chunk);
              controller.close();
            },
          })
        : null;
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

  it("logs credentialed auth failures as warnings, not runtime errors", async () => {
    const req = new MockNextRequest("http://localhost/api/auth/profile", {
      method: "GET",
      cookies: { nz_access_token: "stale-jwt" },
    });

    const response = await GET(req as never);

    expect(response.status).toBe(401);
    expect(logger.warn).toHaveBeenCalledWith(
      "[Proxy] Auth rejected 401 for GET /api/auth/profile with credentials",
      expect.objectContaining({
        action: "auth_rejected",
      }),
    );
    expect(logger.error).not.toHaveBeenCalled();
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

describe("proxy catch-all route — public error redaction", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("does not expose upstream errors or internal target URLs", async () => {
    process.env.NUZANTARA_API_URL =
      "https://private-backend.example.internal:8000";
    vi.mocked(global.fetch).mockRejectedValue(
      new Error("connect ECONNREFUSED 10.0.0.42:8000"),
    );
    const req = new MockNextRequest("http://localhost/api/portal/dashboard", {
      method: "GET",
    });

    const response = await GET(req as never);
    const payload = await response.json();

    expect(response.status).toBe(500);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(payload).toEqual({
      error: "Proxy error",
      message: "Service temporarily unavailable",
    });
    expect(JSON.stringify(payload)).not.toContain("private-backend");
    expect(JSON.stringify(payload)).not.toContain("10.0.0.42");
    expect(JSON.stringify(payload)).not.toContain("ECONNREFUSED");
  });
});

describe("proxy catch-all route — public Visa Oracle boundary", () => {
  beforeEach(() => {
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

  it("strips portal credentials while preserving anonymous contract headers", async () => {
    const req = new MockNextRequest(
      "http://localhost/api/visa-oracle/evaluate?traffic_source=real&request_category=family",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer portal-session",
          Cookie: "nz_access_token=portal-session; nz_csrf_token=csrf-secret",
          "Content-Type": "application/json",
          "Idempotency-Key": "opaque-idempotency-key",
          "Transfer-Encoding": "chunked",
          "X-API-Key": "portal-api-key",
          "X-CSRF-Token": "csrf-secret",
        },
        cookies: {
          nz_access_token: "portal-session",
          nz_csrf_token: "csrf-secret",
        },
        body: new TextEncoder().encode("{}").buffer,
      },
    );

    await POST(req as never);

    const [, init] = vi.mocked(global.fetch).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const sentHeaders = init.headers as Headers;
    expect(capturedTargetUrl(vi.mocked(global.fetch))).toBe(
      "https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate?traffic_source=real&request_category=family",
    );
    expect(sentHeaders.get("authorization")).toBeNull();
    expect(sentHeaders.get("cookie")).toBeNull();
    expect(sentHeaders.get("x-api-key")).toBeNull();
    expect(sentHeaders.get("x-csrf-token")).toBeNull();
    expect(sentHeaders.get("transfer-encoding")).toBeNull();
    expect(sentHeaders.get("idempotency-key")).toBe("opaque-idempotency-key");
    expect(sentHeaders.get("content-type")).toBe("application/json");
    expect(init.credentials).toBe("omit");
  });

  it("rejects a declared oversized body before reading or calling upstream", async () => {
    const req = new MockNextRequest(
      "http://localhost/api/visa-oracle/evaluate",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": String(32 * 1024 + 1),
        },
        body: new ArrayBuffer(1),
      },
    );
    const arrayBufferSpy = vi.spyOn(req, "arrayBuffer");

    const response = await POST(req as never);

    expect(response.status).toBe(413);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(arrayBufferSpy).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("stops an oversized chunked stream at the proxy boundary", async () => {
    const req = new MockNextRequest(
      "http://localhost/api/visa-oracle/evaluate",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Transfer-Encoding": "chunked",
        },
        bodyChunks: [new Uint8Array(20 * 1024), new Uint8Array(20 * 1024)],
      },
    );

    const response = await POST(req as never);

    expect(response.status).toBe(413);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it.each(["multipart/form-data; boundary=attack", "application/jsonp"])(
    "rejects unsupported media type %s before parsing or calling upstream",
    async (contentType) => {
      const req = new MockNextRequest(
        "http://localhost/api/visa-oracle/evaluate",
        {
          method: "POST",
          headers: { "Content-Type": contentType },
          body: new FormData(),
        },
      );
      const formDataSpy = vi.spyOn(req, "formData");
      const arrayBufferSpy = vi.spyOn(req, "arrayBuffer");

      const response = await POST(req as never);

      expect(response.status).toBe(415);
      expect(formDataSpy).not.toHaveBeenCalled();
      expect(arrayBufferSpy).not.toHaveBeenCalled();
      expect(global.fetch).not.toHaveBeenCalled();
    },
  );

  it("accepts a body at the exact 32 KiB limit", async () => {
    const req = new MockNextRequest(
      "http://localhost/api/visa-oracle/evaluate",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": String(32 * 1024),
        },
        body: new ArrayBuffer(32 * 1024),
      },
    );

    const response = await POST(req as never);

    expect(response.status).toBe(200);
    const [, init] = vi.mocked(global.fetch).mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect((init.body as ArrayBuffer).byteLength).toBe(32 * 1024);
  });

  it("redacts request_category from all proxy logs", async () => {
    const makeRequest = () =>
      new MockNextRequest(
        "http://localhost/api/visa-oracle/evaluate?request_category=family",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: new TextEncoder().encode("{}").buffer,
        },
      );

    await POST(makeRequest() as never);
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response("unavailable", { status: 503 }),
    );
    await POST(makeRequest() as never);
    vi.mocked(global.fetch).mockRejectedValueOnce(new Error("network down"));
    await POST(makeRequest() as never);

    const serializedLogs = JSON.stringify({
      debug: vi.mocked(logger.debug).mock.calls,
      error: vi.mocked(logger.error).mock.calls,
      warn: vi.mocked(logger.warn).mock.calls,
    });
    expect(serializedLogs).not.toContain("request_category");
    expect(serializedLogs).not.toContain("family");
  });

  it("does not log identifying request context for an upstream auth rejection", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response("rejected", { status: 401 }),
    );
    const req = new MockNextRequest(
      "http://localhost/api/visa-oracle/evaluate",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer identifying-session",
          Cookie: "nz_access_token=identifying-session",
          "Content-Type": "application/json",
          "User-Agent": "identifying-browser-profile",
          "X-Correlation-ID": "identifying-correlation",
        },
        cookies: { nz_access_token: "identifying-session" },
        body: new TextEncoder().encode("{}").buffer,
      },
    );

    const response = await POST(req as never);

    expect(response.status).toBe(401);
    const serializedLogs = JSON.stringify({
      debug: vi.mocked(logger.debug).mock.calls,
      error: vi.mocked(logger.error).mock.calls,
      warn: vi.mocked(logger.warn).mock.calls,
    });
    expect(serializedLogs).not.toContain("identifying-session");
    expect(serializedLogs).not.toContain("identifying-browser-profile");
    expect(serializedLogs).not.toContain("identifying-correlation");
    expect(logger.warn).toHaveBeenCalledWith(
      "[Proxy] Anonymous Visa Oracle upstream rejected request",
      expect.objectContaining({ action: "upstream_rejected" }),
    );
  });

  it("refuses upstream redirects without replaying the applicant body", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(null, {
        status: 307,
        headers: { Location: "https://attacker.invalid/collect" },
      }),
    );
    const req = new MockNextRequest(
      "http://localhost/api/visa-oracle/evaluate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: new TextEncoder().encode('{"sensitive":"facts"}').buffer,
      },
    );

    const response = await POST(req as never);

    expect(response.status).toBe(502);
    expect(response.headers.get("location")).toBeNull();
    expect(global.fetch).toHaveBeenCalledOnce();
    expect(capturedTargetUrl(vi.mocked(global.fetch))).toBe(
      "https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate",
    );
  });
});

describe("proxy catch-all route — bodyless upstream statuses (204/205/304)", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // Regression: `new Response(buf, { status })` throws a TypeError when `buf`
  // is passed for a "null body status" (204/205/304) — even an empty
  // ArrayBuffer counts as a body under the Fetch spec. Before the fix, that
  // thrown TypeError was caught by the proxy's outer catch block and
  // surfaced as a fabricated 500 "Proxy error", even though the upstream
  // mutation (e.g. a DELETE) had already succeeded.
  it.each([204, 205, 304])(
    "passes through a bodyless upstream %d instead of throwing Proxy error",
    async (status) => {
      process.env.NUZANTARA_API_URL = "https://nuzantara-rag.fly.dev";
      vi.mocked(global.fetch).mockResolvedValue(
        new Response(null, {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );

      const req = new MockNextRequest(
        "http://localhost/api/portal/documents/5",
        { method: "DELETE" },
      );

      const response = await DELETE(req as never);

      expect(response.status).toBe(status);
      const rawBody = await response.arrayBuffer();
      expect(rawBody.byteLength).toBe(0);
    },
  );
});
