import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SHADOW_EVALUATE_URL, sendShadowEvaluation } from "./shadow-client";
import type { OracleFacts } from "./tree";

const FACTS: OracleFacts = {
  in_indonesia: "no",
  category: "tourism",
  tourism_duration: "short",
  review_gate: "none",
};

const TODAY = new Date("2026-07-27T12:00:00.000Z");

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

describe("sendShadowEvaluation — the ONE network call site for SHADOW mode", () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("returns void, not a Promise — there is nothing for a caller to await", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const result = sendShadowEvaluation(FACTS, TODAY);
    expect(result).toBeUndefined();
  });

  it("POSTs to the anonymous evaluate endpoint with an explicit organic label, keepalive + JSON headers", () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    global.fetch = fetchMock;

    sendShadowEvaluation(FACTS, TODAY);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [
      string,
      RequestInit & { keepalive?: boolean },
    ];
    expect(url).toBe(SHADOW_EVALUATE_URL);
    const parsedUrl = new URL(url);
    expect(parsedUrl.pathname).toBe("/api/visa-oracle/evaluate");
    expect([...parsedUrl.searchParams.entries()]).toEqual([
      ["traffic_source", "real"],
    ]);
    expect(init.method).toBe("POST");
    expect(init.keepalive).toBe(true);
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
  });

  it("the POST body is the full 45-key ApplicantFacts envelope, built from the given facts + frozen today", () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    global.fetch = fetchMock;

    sendShadowEvaluation(FACTS, TODAY);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.schema_version).toBe("1.0.0");
    expect(body.assessment_id).toMatch(UUID_RE);
    // Reuses the caller's frozen clock — never an independent `new Date()`
    // (hook-point contract, Finding #9).
    expect(body.collected_at).toBe(TODAY.toISOString());
    expect(Object.keys(body.facts)).toHaveLength(45);
    expect(body.facts["immigration.currently_in_indonesia"]).toEqual({
      status: "KNOWN",
      value: false,
    });
    expect(body.facts["intent.purposes"]).toEqual({
      status: "KNOWN",
      value: ["TOURISM"],
    });
  });

  it("never throws when fetch resolves 200", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    expect(() => sendShadowEvaluation(FACTS, TODAY)).not.toThrow();
  });

  it("never throws when fetch resolves a 404/500 — the response is never read", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("not found", { status: 404 }));
    expect(() => sendShadowEvaluation(FACTS, TODAY)).not.toThrow();

    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("boom", { status: 500 }));
    expect(() => sendShadowEvaluation(FACTS, TODAY)).not.toThrow();
  });

  it("never throws when fetch rejects, and the rejection is truly handled (no unhandledrejection)", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down"));
    expect(() => sendShadowEvaluation(FACTS, TODAY)).not.toThrow();
    // Drain the microtask queue so the internal `.catch` has actually run —
    // proves the rejection is handled, not merely "not yet observed" by
    // this synchronous assertion.
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  it("never throws when fetch itself throws synchronously", () => {
    global.fetch = vi.fn(() => {
      throw new Error("fetch is not available in this environment");
    });
    expect(() => sendShadowEvaluation(FACTS, TODAY)).not.toThrow();
  });

  it("never throws when fetch returns a non-thenable value (defensive stub-harness case)", () => {
    // Mirrors this very test suite's OWN global default before any test
    // overrides it (`src/test/setup.tsx`: `global.fetch = vi.fn()`, no
    // configured resolution) — a real symptom this module defends against.
    global.fetch = vi.fn(
      () => undefined as unknown as ReturnType<typeof fetch>,
    );
    expect(() => sendShadowEvaluation(FACTS, TODAY)).not.toThrow();
  });

  it("still builds and sends a valid payload for an all-unanswered (thin) interview — contract-valid, never rejected client-side", () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    global.fetch = fetchMock;

    expect(() => sendShadowEvaluation({}, TODAY)).not.toThrow();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(Object.keys(body.facts)).toHaveLength(45);
    expect(body.facts["person.birth_date"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});
