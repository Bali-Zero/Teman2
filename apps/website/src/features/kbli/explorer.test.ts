// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  handleExplorerChat,
  kbliBackendOrigin,
  normalizeReply,
} from "./explorer.server";
const reply = {
  answer: "A retrieved answer.",
  detected_kbli: ["56101"],
  suggested_queries: ["Which scope should I check?"],
  sources: [
    {
      content: "Recorded source excerpt",
      metadata: { kode_kbli: "56101", judul: "Activity record" },
    },
  ],
};
function request(
  value: unknown = { query: "Explain this activity." },
  headers: Record<string, string> = {},
): Request {
  return new Request("http://localhost:3100/api/kbli/chat", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      origin: "http://localhost:3100",
      ...headers,
    },
    body: JSON.stringify(value),
  });
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
describe("KBLI assisted answer boundary", () => {
  it("accepts only an explicit HTTPS or loopback origin", () => {
    expect(kbliBackendOrigin("https://kbli.example")).toBe(
      "https://kbli.example",
    );
    expect(kbliBackendOrigin("http://127.0.0.1:8080")).toBe(
      "http://127.0.0.1:8080",
    );
    for (const value of [
      "http://remote.example",
      "https://user:pass@example.com",
      "https://example.com/a",
      "https://example.com?target=bad",
      "file:///private/data",
      "not a url",
    ])
      expect(kbliBackendOrigin(value)).toBeNull();
  });
  it("makes no request when unarmed, self-referential or cross-origin", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    vi.stubEnv("WEBSITE_KBLI_BACKEND_URL", "");
    expect((await handleExplorerChat(request())).status).toBe(503);
    vi.stubEnv("WEBSITE_KBLI_BACKEND_URL", "http://localhost:3100");
    expect((await handleExplorerChat(request())).status).toBe(503);
    expect(
      (
        await handleExplorerChat(
          request(undefined, { origin: "https://other.example" }),
        )
      ).status,
    ).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects invalid and oversized input before network access", async () => {
    vi.stubEnv("WEBSITE_KBLI_BACKEND_URL", "https://kbli.example");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect((await handleExplorerChat(request({ query: "" }))).status).toBe(400);
    expect(
      (await handleExplorerChat(request({ query: "x".repeat(4001) }))).status,
    ).toBe(400);
    expect(
      (await handleExplorerChat(request({ query: "x".repeat(20000) }))).status,
    ).toBe(413);
    expect(
      (
        await handleExplorerChat(
          request(undefined, { "content-type": "text/plain" }),
        )
      ).status,
    ).toBe(415);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("passes only the question to the configured notebook and returns real content", async () => {
    vi.stubEnv("WEBSITE_KBLI_BACKEND_URL", "https://kbli.example");
    const fetch = vi.fn().mockResolvedValue(Response.json(reply));
    vi.stubGlobal("fetch", fetch);
    const response = await handleExplorerChat(
      request(
        { query: " Explain this activity. ", target: "https://evil.example" },
        { cookie: "session=private", authorization: "Bearer private" },
      ),
    );
    expect(response.status).toBe(200);
    expect((await response.json()).answer).toBe(reply.answer);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("https://kbli.example/api/v1/kbli-notebook/chat");
    expect(JSON.parse(init.body)).toEqual({ query: "Explain this activity." });
    expect(init.headers).not.toHaveProperty("cookie");
    expect(init.headers).not.toHaveProperty("authorization");
    expect(init.redirect).toBe("manual");
    expect(init.credentials).toBe("omit");
  });
  it("fails closed on redirect, malformed content and oversized responses", async () => {
    vi.stubEnv("WEBSITE_KBLI_BACKEND_URL", "https://kbli.example");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    for (const response of [
      new Response(null, {
        status: 302,
        headers: { location: "https://other.example" },
      }),
      Response.json({ answer: "Incomplete" }),
      Response.json({ ...reply, answer: "x".repeat(210000) }),
    ]) {
      fetch.mockResolvedValueOnce(response);
      expect((await handleExplorerChat(request())).status).toBe(502);
    }
  });
  it("keeps source text but never treats arbitrary detected strings as internal links", () => {
    const normalized = normalizeReply({
      ...reply,
      detected_kbli: ["56101", "../../admin", "javascript:alert(1)"],
    });
    expect(normalized?.detected_kbli).toEqual(["56101"]);
    expect(normalized?.sources[0].content).toBe(reply.sources[0].content);
    expect(normalizeReply({ ...reply, sources: "not an array" })).toBeNull();
  });
});
