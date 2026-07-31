/**
 * The api client used to throw a bare `Error`, discarding `response.status`.
 * Every consumer that needed to branch on 401/403/404 therefore sniffed
 * substrings out of `error.message` — and a substring is not a status:
 * `"Practice 4012 not found".includes("401")` is TRUE.
 *
 * These tests are the corpus for that fix, in the guilt/innocence shape this
 * repo requires of any guard:
 *   GUILT     — a real 401/403/404 is recognised by status.
 *   INNOCENCE — a 404 whose message merely CONTAINS "401" is not read as auth,
 *               and a 500 whose detail mentions 404 is not read as not-found.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { ApiError } from "../error-handler";
import { ApiClientBase } from "../client";

vi.mock("@/lib/utils/storage", () => ({
  safeStorage: {
    getItem: vi.fn(() => null),
    setItem: vi.fn(() => true),
    removeItem: vi.fn(),
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

/** Minimal stand-in for the shape client.ts throws. */
function thrownByClient(
  status: number,
  detail: string,
  extra: Record<string, unknown> = {},
) {
  const body = { detail, ...extra };
  return new ApiError(detail || `HTTP ${status}`, status, body);
}

describe("ApiError carries the HTTP status", () => {
  it("GUILT: a 401 is a 401 by status, not by text", () => {
    const err = thrownByClient(401, "Session expired. Please login again.");
    expect(err).toBeInstanceOf(ApiError);
    expect(err.statusCode).toBe(401);
  });

  it("stays an Error, so pre-existing consumers do not break", () => {
    const err = thrownByClient(500, "boom");
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("boom");
    expect(err.name).toBe("ApiError");
  });

  it("lifts detail and code out of the body (what the old interface promised)", () => {
    const err = thrownByClient(429, "Rate limited", { code: "QUOTA_EXCEEDED" });
    expect(err.detail).toBe("Rate limited");
    expect(err.code).toBe("QUOTA_EXCEEDED");
    expect(err.statusCode).toBe(429);
  });

  it("keeps INVALID_METHOD's message while now also carrying 405", () => {
    const err = new ApiError("INVALID_METHOD", 405, {});
    expect(err.message).toBe("INVALID_METHOD");
    expect(err.statusCode).toBe(405);
  });
});

describe("INNOCENCE: the substring trap that motivated the fix", () => {
  const notFoundWith401InText = thrownByClient(404, "Practice 4012 not found");

  it("the old substring test WOULD have misfired — proving the trap is real", () => {
    // This asserts the defect, not the cure: if this ever stops being true the
    // test above it is no longer guarding anything meaningful.
    expect(notFoundWith401InText.message.includes("401")).toBe(true);
  });

  it("status-based branching does NOT read it as auth", () => {
    expect(notFoundWith401InText.statusCode).toBe(404);
    expect(notFoundWith401InText.statusCode === 401).toBe(false);
  });

  it("a 5xx that mentions 404 in its detail is not not-found", () => {
    const upstream = thrownByClient(502, "upstream returned 404 from OSS");
    expect(upstream.message.includes("404")).toBe(true); // the trap
    expect(upstream.statusCode).toBe(502); // the cure
    expect(upstream.statusCode === 404).toBe(false);
  });
});

describe("ApiClientBase.request throws ApiError with the real status", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  /**
   * Exercises the real client, not a hand-built ApiError, so this goes red if
   * client.ts ever reverts to `throw new Error(...)`.
   */
  it("a 404 whose detail contains '401' surfaces statusCode 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Practice 4012 not found" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    ) as unknown as typeof globalThis.fetch;

    const client = new ApiClientBase("https://api.example.com");

    let caught: unknown;
    try {
      await client.request("/api/crm/practices/4012");
    } catch (e) {
      caught = e;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).statusCode).toBe(404);
    // The trap, pinned: the old code path would have read this as auth.
    expect((caught as ApiError).message).toContain("401");
  });

  it("a 422 keeps its Validation error message AND carries 422", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [{ loc: ["body", "email"], msg: "invalid", type: "value" }],
        }),
        { status: 422, headers: { "content-type": "application/json" } },
      ),
    ) as unknown as typeof globalThis.fetch;

    const client = new ApiClientBase("https://api.example.com");

    let caught: unknown;
    try {
      await client.request("/api/crm/clients");
    } catch (e) {
      caught = e;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).statusCode).toBe(422);
    expect((caught as ApiError).message).toContain("Validation error");
  });
});
