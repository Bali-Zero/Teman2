import { describe, expect, it, vi } from "vitest";
import {
  evaluateVisaOracle,
  VisaOracleClientError,
  VISA_ORACLE_MAX_REQUEST_BYTES,
} from "./evaluation-client";
import { VISA_ORACLE_MAX_RESPONSE_BYTES } from "./strict-json";
import { makeVisaOracleResponse } from "./visa-oracle-test-fixture";
import type { VisaOracleEvaluateRequest } from "./visa-oracle-contract";

const IDEMPOTENCY_KEY = "11111111-1111-4111-8111-111111111111";

const REQUEST = {
  schema_version: "1.0.0",
  assessment_id: "22222222-2222-4222-8222-222222222222",
  collected_at: "2026-08-03T04:00:00.000Z",
  facts: {},
  disclosed_review_flags: [],
} as unknown as VisaOracleEvaluateRequest;

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
  });
}

describe("Visa Oracle evaluation HTTP client", () => {
  it("uses the generated endpoint contract without semantic query data", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      jsonResponse(makeVisaOracleResponse()),
    );
    const result = await evaluateVisaOracle({
      request: REQUEST,
      idempotencyKey: IDEMPOTENCY_KEY,
      fetchImpl,
      maxRetries: 0,
    });

    expect(result.mode).toBe("ENGINE");
    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("/api/visa-oracle/evaluate");
    expect(init).toMatchObject({
      method: "POST",
      body: JSON.stringify(REQUEST),
      cache: "no-store",
      credentials: "same-origin",
    });
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      IDEMPOTENCY_KEY,
    );
  });

  it("retries only a bounded retryable failure with identical body and key", async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ error: "busy" }, { status: 503 }))
      .mockResolvedValueOnce(jsonResponse(makeVisaOracleResponse()));
    await evaluateVisaOracle({
      request: REQUEST,
      idempotencyKey: IDEMPOTENCY_KEY,
      fetchImpl,
      maxRetries: 1,
      waitBeforeRetry: async () => undefined,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const calls = fetchImpl.mock.calls;
    expect(calls[1][1]?.body).toBe(calls[0][1]?.body);
    expect(new Headers(calls[1][1]?.headers).get("Idempotency-Key")).toBe(
      new Headers(calls[0][1]?.headers).get("Idempotency-Key"),
    );
  });

  it("does not retry a replay conflict or malformed response", async () => {
    const conflictFetch = vi.fn(async () =>
      jsonResponse({ code: "IDEMPOTENCY_CONFLICT" }, { status: 409 }),
    );
    await expect(
      evaluateVisaOracle({
        request: REQUEST,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl: conflictFetch,
        maxRetries: 2,
      }),
    ).rejects.toEqual(
      expect.objectContaining({ code: "HTTP_ERROR", status: 409 }),
    );
    expect(conflictFetch).toHaveBeenCalledOnce();

    const duplicateJsonFetch = vi.fn(
      async () =>
        new Response('{"mode":"ENGINE","mode":"CURATED"}', {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    await expect(
      evaluateVisaOracle({
        request: REQUEST,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl: duplicateJsonFetch,
        maxRetries: 2,
      }),
    ).rejects.toEqual(expect.objectContaining({ code: "MALFORMED_RESPONSE" }));
    expect(duplicateJsonFetch).toHaveBeenCalledOnce();
  });

  it("classifies an elapsed request deadline as a timeout", async () => {
    const fetchImpl = vi.fn<typeof fetch>(
      async (_input, init) =>
        await new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("timed out", "AbortError")),
            { once: true },
          );
        }),
    );

    await expect(
      evaluateVisaOracle({
        request: REQUEST,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl,
        timeoutMs: 5,
        maxRetries: 0,
      }),
    ).rejects.toEqual(expect.objectContaining({ code: "TIMEOUT" }));
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it("fails closed on unsafe sizes, content types and caller abort", async () => {
    const oversizedRequest = {
      ...REQUEST,
      disclosed_review_flags: ["x".repeat(VISA_ORACLE_MAX_REQUEST_BYTES)],
    } as unknown as VisaOracleEvaluateRequest;
    await expect(
      evaluateVisaOracle({
        request: oversizedRequest,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl: vi.fn(),
      }),
    ).rejects.toBeInstanceOf(VisaOracleClientError);

    const oversizedResponse = vi.fn(
      async () =>
        new Response("{}", {
          status: 200,
          headers: {
            "content-type": "application/json",
            "content-length": String(VISA_ORACLE_MAX_RESPONSE_BYTES + 1),
          },
        }),
    );
    await expect(
      evaluateVisaOracle({
        request: REQUEST,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl: oversizedResponse,
        maxRetries: 0,
      }),
    ).rejects.toEqual(expect.objectContaining({ code: "MALFORMED_RESPONSE" }));

    const htmlFetch = vi.fn(
      async () =>
        new Response("<html />", {
          status: 200,
          headers: { "content-type": "text/html" },
        }),
    );
    await expect(
      evaluateVisaOracle({
        request: REQUEST,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl: htmlFetch,
        maxRetries: 0,
      }),
    ).rejects.toEqual(expect.objectContaining({ code: "MALFORMED_RESPONSE" }));

    const controller = new AbortController();
    controller.abort();
    const abortedFetch = vi.fn();
    await expect(
      evaluateVisaOracle({
        request: REQUEST,
        idempotencyKey: IDEMPOTENCY_KEY,
        fetchImpl: abortedFetch,
        signal: controller.signal,
      }),
    ).rejects.toEqual(expect.objectContaining({ code: "ABORTED" }));
    expect(abortedFetch).not.toHaveBeenCalled();
  });
});
