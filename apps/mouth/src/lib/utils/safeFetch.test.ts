import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { safeFetch } from "./safeFetch";

// Mock the logger to avoid Sentry dependency in tests
vi.mock("@/lib/logger", () => ({
  logger: {
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

describe("safeFetch", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns data on successful JSON response", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ items: [1, 2, 3] }),
    });

    const result = await safeFetch<{ items: number[] }>("/api/test");

    expect(result.data).toEqual({ items: [1, 2, 3] });
    expect(result.error).toBeNull();
    expect(result.status).toBe(200);
  });

  it("returns empty object for 204 No Content", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
    });

    const result = await safeFetch("/api/test");

    expect(result.data).toEqual({});
    expect(result.error).toBeNull();
    expect(result.status).toBe(204);
  });

  it("returns error for non-ok response with JSON detail", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: async () => JSON.stringify({ detail: "Resource not found" }),
    });

    const result = await safeFetch("/api/missing");

    expect(result.data).toBeNull();
    expect(result.error).toBe("Resource not found");
    expect(result.status).toBe(404);
  });

  it("returns error for non-ok response with plain text body", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: async () => "Something went wrong",
    });

    const result = await safeFetch("/api/broken");

    expect(result.data).toBeNull();
    expect(result.error).toBe("Something went wrong");
    expect(result.status).toBe(500);
  });

  it("returns timeout error on AbortError", async () => {
    // In jsdom, DOMException may not have `.name` equal to 'AbortError' on the Error prototype check.
    // Create a proper Error with name set to 'AbortError' to match the code's check.
    const abortError = new Error("signal is aborted");
    abortError.name = "AbortError";
    mockFetch.mockRejectedValue(abortError);

    const result = await safeFetch("/api/slow", { timeoutMs: 100 });

    expect(result.data).toBeNull();
    expect(result.error).toBe("Request timeout");
    expect(result.status).toBe(0);
  });

  it("returns error message for network errors", async () => {
    mockFetch.mockRejectedValue(new Error("Failed to fetch"));

    const result = await safeFetch("/api/unreachable");

    expect(result.data).toBeNull();
    expect(result.error).toBe("Failed to fetch");
    expect(result.status).toBe(0);
  });

  it("passes through custom fetch options", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ success: true }),
    });

    await safeFetch("/api/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "value" }),
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: '{"key":"value"}',
      }),
    );
  });
});
