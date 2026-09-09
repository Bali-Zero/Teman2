// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

const payload = { topic: "property", sourcePage: "/services/property" };
const upstreamHref = "https://wa.me/628213454721?text=Property%20enquiry";
function request(body: unknown = payload, origin = "https://preview.example.test"): Request {
  return new Request("https://preview.example.test/api/lead/capture", {
    method: "POST", headers: { "Content-Type": "application/json", Origin: origin },
    body: JSON.stringify(body),
  });
}
function enable(): void {
  vi.stubEnv("WEBSITE_LEAD_CAPTURE_ENABLED", "true");
  vi.stubEnv("WEBSITE_LEAD_CAPTURE_API_ORIGIN", "https://backend.example.test");
}
beforeEach(() => {
  vi.stubEnv("WEBSITE_LEAD_CAPTURE_ENABLED", "");
  vi.stubEnv("WEBSITE_LEAD_CAPTURE_API_ORIGIN", "");
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("lead capture server gate", () => {
  it("fails closed by default without reading or forwarding the body", async () => {
    const response = await POST(request());
    expect(response.status).toBe(503);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    "", "http://backend.example.test", "https://preview.example.test",
    "https://www.preview.example.test", "https://backend.example.test/path",
    "https://user:password@backend.example.test", "https://127.0.0.1", "https://service.local",
  ])("rejects missing, unsafe, or self-referential owner origin %s", async (origin) => {
    enable();
    vi.stubEnv("WEBSITE_LEAD_CAPTURE_API_ORIGIN", origin);
    expect((await POST(request())).status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("requires same-origin JSON requests before sending upstream", async () => {
    enable();
    expect((await POST(request(payload, "https://other.example.test"))).status).toBe(403);
    const wrongType = request();
    wrongType.headers.set("Content-Type", "text/plain");
    expect((await POST(wrongType)).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    { ...payload, topic: "constructor" }, { ...payload, sourcePage: "/contact?private=value" },
    { ...payload, sourcePage: "/property/arbitrary-story" }, { ...payload, message: "discarded" },
    { ...payload, client_fingerprint: "not-accepted" }, [], null,
  ])("rejects arbitrary payload fields and unrecognized context", async (body) => {
    enable();
    expect((await POST(request(body))).status).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("caps the actual body even without a content-length header", async () => {
    enable();
    expect((await POST(request({ ...payload, extra: "x".repeat(1100) }))).status).toBe(413);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("reconstructs the accepted backend contract and forwards no browser identity or headers", async () => {
    enable();
    const fetcher = vi.mocked(fetch).mockResolvedValue(Response.json({ whatsapp_url: upstreamHref, lead_intent_id: "synthetic-id", expires_at: "2026-09-10" }, { status: 201 }));
    const browserRequest = request();
    browserRequest.headers.set("Cookie", "synthetic-cookie=not-forwarded");
    browserRequest.headers.set("Authorization", "synthetic-value-not-forwarded");
    const response = await POST(browserRequest);
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ whatsapp_url: upstreamHref });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe("https://backend.example.test/api/lead/capture");
    const init = fetcher.mock.calls[0][1]!;
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(init).toMatchObject({ credentials: "omit", redirect: "error", cache: "no-store" });
    expect(JSON.parse(init.body as string)).toEqual({
      source: "cta_handoff", context: { topic: "property", source_page: "/services/property" },
      whatsapp_context: [{ label: "Topic", value: "property due diligence" }, { label: "Page", value: "/services/property" }],
    });
  });

  it.each([503, 200])("does not turn an upstream status %s into confirmed capture", async (status) => {
    enable();
    vi.mocked(fetch).mockResolvedValue(Response.json({ whatsapp_url: upstreamHref }, { status }));
    expect((await POST(request())).status).toBe(502);
  });

  it("blocks an unsafe upstream redirect even after a 201", async () => {
    enable();
    vi.mocked(fetch).mockResolvedValue(Response.json({ whatsapp_url: "https://evil.example.test" }, { status: 201 }));
    expect((await POST(request())).status).toBe(502);
  });

  it("returns unavailable on transport failure without retrying", async () => {
    enable();
    vi.mocked(fetch).mockRejectedValue(new Error("offline"));
    expect((await POST(request())).status).toBe(502);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("bounds an unresponsive upstream and aborts it without retries", async () => {
    enable();
    vi.useFakeTimers();
    const fetcher = vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
    const response = POST(request());
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(1200);
    expect((await response).status).toBe(504);
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
