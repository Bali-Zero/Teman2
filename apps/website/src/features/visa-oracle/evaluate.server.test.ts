// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { forwardOracleEvaluation, oracleBackendUrl } from "./evaluate.server";

function request(body = "{}", extra: Record<string, string> = {}): Request {
  return new Request("http://localhost:3100/api/visa-oracle/evaluate?traffic_source=canary&ignored=private", {
    method: "POST", body, headers: { "Content-Type": "application/json", "Idempotency-Key": "same-payload-1", ...extra },
  });
}
describe("native evaluation transport", () => {
  it("requires explicit server configuration and rejects self loops and unsafe origins", async () => {
    const fetcher = vi.fn();
    for (const config of ["", "http://example.com", "https://a:b@example.com", "https://example.com/base", "http://localhost:3100"]) {
      expect((await forwardOracleEvaluation(request(), config, fetcher)).status).toBe(503);
    }
    expect(fetcher).not.toHaveBeenCalled();
    expect(oracleBackendUrl("http://127.0.0.1:3191")?.port).toBe("3191");
  });
  it("forwards exact bytes and retry key, strips credentials, refuses redirects and caching", async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response('{"mode":"CURATED"}', { headers: { "Content-Type": "application/json", "Set-Cookie": "unsafe=1" } }));
    const body = '{"facts": {}}';
    const response = await forwardOracleEvaluation(request(body, { Authorization: "Bearer TEST-ONLY", Cookie: "test=1", "X-Api-Key": "TEST-ONLY" }), "http://127.0.0.1:3191", fetcher);
    const [url, init] = fetcher.mock.calls[0];
    expect(String(url)).toBe("http://127.0.0.1:3191/api/visa-oracle/evaluate?traffic_source=real");
    expect(init).toMatchObject({ body, cache: "no-store", redirect: "manual", credentials: "omit" });
    expect(Object.keys(init!.headers!)).toEqual(["Content-Type", "Accept", "Idempotency-Key"]);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.has("set-cookie")).toBe(false);
    expect(await response.text()).toBe('{"mode":"CURATED"}');
  });
  it.each([["{\"facts\":1,\"facts\":2}",400], ["x".repeat(32769),413], ["[]",400]])("rejects invalid/oversized requests before forwarding", async (body, status) => {
    const fetcher = vi.fn();
    expect((await forwardOracleEvaluation(request(String(body)), "http://127.0.0.1:3191", fetcher)).status).toBe(status);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("blocks cross-origin requests", async () => {
    expect((await forwardOracleEvaluation(request("{}", { Origin: "https://other.example" }), "http://127.0.0.1:3191")).status).toBe(403);
  });
  it("uses the browser Host when Next reconstructs an internal listener URL", async () => {
    const fetcher = vi.fn(async () => new Response("{}"));
    const headers = { Host: "127.0.0.1:3100", Origin: "http://127.0.0.1:3100" };
    expect((await forwardOracleEvaluation(request("{}", headers), "http://127.0.0.1:3191", fetcher)).status).toBe(200);
    for (const Origin of ["http://localhost:3100", "https://127.0.0.1:3100", "null", "http://127.0.0.1:3100/path"]) {
      expect((await forwardOracleEvaluation(request("{}", { ...headers, Origin, "X-Forwarded-Host": new URL("https://other.example").host }), "http://127.0.0.1:3191", fetcher)).status).toBe(403);
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect((await forwardOracleEvaluation(request("{}", headers), "http://127.0.0.1:3100", fetcher)).status).toBe(503);
  });
  it.each([422, 429, 503])("retains HTTP %s without exposing upstream details", async (status) => {
    const response = await forwardOracleEvaluation(request(), "http://127.0.0.1:3191", vi.fn(async () => new Response("sensitive diagnostic", { status })));
    expect(response.status).toBe(status);
    expect(await response.text()).not.toContain("sensitive");
  });
  it("never replays a redirect and bounds response bodies", async () => {
    const redirect = vi.fn(async () => new Response(null, { status: 307, headers: { Location: "https://example.com" } }));
    expect((await forwardOracleEvaluation(request(), "http://127.0.0.1:3191", redirect)).status).toBe(502);
    expect(redirect).toHaveBeenCalledTimes(1);
    expect((await forwardOracleEvaluation(request(), "http://127.0.0.1:3191", vi.fn(async () => new Response("x".repeat(262145))))).status).toBe(502);
  });
});

describe("explicit unsigned proposal transport", () => {
  const proposal = () => new Response("{}", { headers: { "Content-Type": "application/json", "X-Visa-Local-Proof": "unsigned-proposal-no-db-test-seal" } });
  it("rejects unsigned responses in the reference lane and reference responses in the proposal lane", async () => {
    expect((await forwardOracleEvaluation(request(), "http://127.0.0.1:3192", vi.fn(async () => proposal()), "")).status).toBe(502);
    expect((await forwardOracleEvaluation(request(), "http://127.0.0.1:3191", vi.fn(async () => new Response("{}")), "unsigned-proposal")).status).toBe(502);
  });
  it("accepts only explicitly selected loopback proposals and preserves the proof label", async () => {
    const response = await forwardOracleEvaluation(request(), "http://127.0.0.1:3192", vi.fn(async () => proposal()), "unsigned-proposal");
    expect(response.status).toBe(200);
    expect(response.headers.get("X-Visa-Local-Proof")).toBe("unsigned-proposal-no-db-test-seal");
    const fetcher = vi.fn(async () => proposal());
    expect((await forwardOracleEvaluation(request(), "https://example.test", fetcher, "unsigned-proposal")).status).toBe(503);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
