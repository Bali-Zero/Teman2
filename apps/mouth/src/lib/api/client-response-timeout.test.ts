import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClientBase } from "./client";
import { CrmApi } from "./crm/crm.api";

vi.mock("@/lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

describe("request deadline includes the JSON body", () => {
  let client: ApiClientBase;
  let body: ReadableStreamDefaultController<Uint8Array>;
  let signal: AbortSignal;

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    client = new ApiClientBase("http://localhost");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, options: RequestInit) => {
        signal = options.signal!;
        const stream = new ReadableStream<Uint8Array>({
          start(controller): void {
            body = controller;
            signal.addEventListener("abort", () => {
              const error = new Error("Body read aborted");
              error.name = "AbortError";
              controller.error(error);
            });
          },
        });
        return new Response(stream, {
          headers: { "content-type": "application/json" },
        });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("terminates a CRM request whose headers arrived but body stalled", async () => {
    const pending = new CrmApi(client).getPractices();
    const rejected = expect(pending).rejects.toThrow("Request timeout");
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost/api/crm/practices",
      expect.any(Object),
    );
    body.enqueue(new TextEncoder().encode("["));
    await vi.advanceTimersByTimeAsync(29_999);
    expect(signal.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(signal.aborted).toBe(true);
    await rejected;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("preserves a complete body and clears the timer after consumption", async () => {
    const pending = new CrmApi(client).getPractices();
    await vi.advanceTimersByTimeAsync(0);
    body.enqueue(new TextEncoder().encode("["));
    await vi.advanceTimersByTimeAsync(20_000);
    body.enqueue(new TextEncoder().encode("]"));
    body.close();
    await expect(pending).resolves.toEqual([]);
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(signal.aborted).toBe(false);
  });

  it("honors the custom POST deadline during body consumption", async () => {
    const rejected = expect(client.post("/synthetic", {}, 40)).rejects.toThrow(
      "Request timeout",
    );
    await vi.advanceTimersByTimeAsync(40);
    expect(signal.aborted).toBe(true);
    await rejected;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps malformed JSON distinguishable from a timeout", async () => {
    const pending = client.request("/synthetic");
    const rejected = expect(pending).rejects.toBeInstanceOf(SyntaxError);
    await vi.advanceTimersByTimeAsync(0);
    body.enqueue(new TextEncoder().encode("not-json"));
    body.close();
    await rejected;
    expect(signal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });
});
