import { describe, expect, it, vi } from "vitest";
import {
  CONSULTANT_ASSIGNMENT_URL,
  requestConsultantAssignment,
} from "./consultant-assignment-client";

const EVALUATION_ID = "11111111-1111-4111-8111-111111111111";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 202,
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
  });
}

describe("requestConsultantAssignment", () => {
  it("POSTs the exact C3 wire shape with only the required fields", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      jsonResponse({ accepted: true, request_id: "x" }),
    );

    await requestConsultantAssignment({
      evaluationId: EVALUATION_ID,
      originScreen: "verdict",
      tier: "T2",
      locale: "en",
      fetchImpl,
    });

    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(CONSULTANT_ASSIGNMENT_URL);
    expect(init?.method).toBe("POST");
    expect(init?.cache).toBe("no-store");
    expect(init?.credentials).toBe("same-origin");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(JSON.parse(String(init?.body))).toEqual({
      evaluation_id: EVALUATION_ID,
      origin_screen: "verdict",
      tier: "T2",
      locale: "en",
    });
  });

  it("includes client_id and product_version_id only when present", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      jsonResponse({ accepted: true, request_id: "x" }),
    );

    await requestConsultantAssignment({
      evaluationId: EVALUATION_ID,
      clientId: "22222222-2222-4222-8222-222222222222",
      productVersionId: "33333333-3333-4333-8333-333333333333",
      originScreen: "checkout",
      tier: "T3",
      locale: "id",
      fetchImpl,
    });

    const [, init] = fetchImpl.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      evaluation_id: EVALUATION_ID,
      client_id: "22222222-2222-4222-8222-222222222222",
      product_version_id: "33333333-3333-4333-8333-333333333333",
      origin_screen: "checkout",
      tier: "T3",
      locale: "id",
    });
  });

  it("omits null client_id/product_version_id rather than serializing null", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      jsonResponse({ accepted: true, request_id: "x" }),
    );

    await requestConsultantAssignment({
      evaluationId: EVALUATION_ID,
      clientId: null,
      productVersionId: null,
      originScreen: "wizard",
      tier: "T3",
      locale: "en",
      fetchImpl,
    });

    const [, init] = fetchImpl.mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body).not.toHaveProperty("client_id");
    expect(body).not.toHaveProperty("product_version_id");
  });

  it("never rejects on a network failure", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => {
      throw new TypeError("network down");
    });

    await expect(
      requestConsultantAssignment({
        evaluationId: EVALUATION_ID,
        originScreen: "verdict",
        tier: "T2",
        locale: "en",
        fetchImpl,
      }),
    ).resolves.toBeUndefined();
  });

  it("never rejects on a non-2xx HTTP response", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "boom" }, { status: 500 }),
    );

    await expect(
      requestConsultantAssignment({
        evaluationId: EVALUATION_ID,
        originScreen: "verdict",
        tier: "T2",
        locale: "en",
        fetchImpl,
      }),
    ).resolves.toBeUndefined();
  });

  it("never rejects when fetch is unavailable in this environment", async () => {
    await expect(
      requestConsultantAssignment({
        evaluationId: EVALUATION_ID,
        originScreen: "verdict",
        tier: "T2",
        locale: "en",
        fetchImpl: undefined,
      }),
    ).resolves.toBeUndefined();
  });

  it("aborts and resolves once the bounded timeout elapses", async () => {
    const fetchImpl = vi.fn<typeof fetch>(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          const signal = init?.signal;
          signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    );

    await expect(
      requestConsultantAssignment({
        evaluationId: EVALUATION_ID,
        originScreen: "verdict",
        tier: "T2",
        locale: "en",
        fetchImpl,
        timeoutMs: 5,
      }),
    ).resolves.toBeUndefined();
  });
});
