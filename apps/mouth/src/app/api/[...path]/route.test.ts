import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST, GET } from "./route";

/**
 * Regression tests for the catch-all backend proxy.
 *
 * BUG A (2026-06-22 portal E2E): the proxy forwarded the CSRF token to the
 * backend ONLY as a cookie (`nz_csrf_token`), never as the `X-CSRF-Token`
 * header. The backend's double-submit check (`validate_csrf`) compares the
 * cookie value against the `X-CSRF-Token` HEADER and returns 401 when the
 * header is absent — so EVERY mutating request that went through the proxy
 * without its own X-CSRF-Token header (e.g. the vault upload XHR) got 401.
 *
 * These tests pin the proxy promoting the csrf cookie → X-CSRF-Token header
 * for mutating methods, without clobbering a header the caller already set.
 */

function headersOfLastFetch(): Headers {
  const mock = vi.mocked(global.fetch);
  const calls = mock.mock.calls;
  const call = calls[calls.length - 1];
  if (!call) throw new Error("fetch was not called");
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers);
}

function proxyRequest(
  method: string,
  cookie: string,
  extraHeaders: Record<string, string> = {},
): NextRequest {
  return new NextRequest(
    "https://my.balizero.com/api/portal/documents/upload",
    {
      method,
      headers: { cookie, ...extraHeaders },
    },
  );
}

describe("backend proxy — CSRF header promotion (BUG A)", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("promotes the nz_csrf_token cookie to an X-CSRF-Token header on POST", async () => {
    await POST(proxyRequest("POST", "nz_csrf_token=tok-abc123"));
    const forwarded = headersOfLastFetch();
    expect(forwarded.get("x-csrf-token")).toBe("tok-abc123");
  });

  it("does NOT overwrite an X-CSRF-Token header the caller already sent", async () => {
    await POST(
      proxyRequest("POST", "nz_csrf_token=cookie-val", {
        "X-CSRF-Token": "caller-supplied",
      }),
    );
    const forwarded = headersOfLastFetch();
    expect(forwarded.get("x-csrf-token")).toBe("caller-supplied");
  });

  it("does NOT add an X-CSRF-Token header on a safe GET (no csrf needed)", async () => {
    await GET(proxyRequest("GET", "nz_csrf_token=tok-abc123"));
    const forwarded = headersOfLastFetch();
    expect(forwarded.get("x-csrf-token")).toBeNull();
  });

  it("does nothing when there is no csrf cookie", async () => {
    await POST(proxyRequest("POST", "other=1"));
    const forwarded = headersOfLastFetch();
    expect(forwarded.get("x-csrf-token")).toBeNull();
  });
});
