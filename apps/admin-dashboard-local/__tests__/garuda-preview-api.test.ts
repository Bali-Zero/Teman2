import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  runGarudaPreview: vi.fn(),
}));

vi.mock("@/lib/garuda-preview-adapter", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/garuda-preview-adapter")
  >("@/lib/garuda-preview-adapter");
  return { ...actual, runGarudaPreview: mocks.runGarudaPreview };
});

import { POST } from "@/app/api/garuda-voa/evaluate/route";
import { createCockpitSessionToken } from "@/lib/cockpit-session";

const SECRET =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
const AUDIENCE = "http://localhost:3100";
const SYNTHETIC_BODY = JSON.stringify({
  case_type: "extension",
  nationality: "USA",
  entry_date: "2026-08-01",
  passport_expiry_date: "2027-08-01",
  purpose: "tourism",
  travellers: 1,
  self_pay: true,
  voa_expiry_date: "2026-09-01",
  extension_already_used: false,
});

async function apiRequest(
  options: {
    host?: string;
    token?: string;
    body?: string;
    contentType?: string;
    contentLength?: number;
    origin?: string;
    secFetchSite?: string;
    cookieToken?: string;
  } = {},
): Promise<NextRequest> {
  const headers = new Headers({
    host: options.host ?? "localhost:3100",
    "content-type": options.contentType ?? "application/json",
  });
  if (options.token) {
    headers.set("authorization", `Bearer ${options.token}`);
  }
  if (options.cookieToken) {
    headers.set("cookie", `cockpit-session=${options.cookieToken}`);
  }
  if (options.contentLength !== undefined) {
    headers.set("content-length", String(options.contentLength));
  }
  if (options.origin !== undefined) headers.set("origin", options.origin);
  if (options.secFetchSite !== undefined) {
    headers.set("sec-fetch-site", options.secFetchSite);
  }
  return new NextRequest("http://localhost:3100/api/garuda-voa/evaluate", {
    method: "POST",
    headers,
    body: options.body ?? SYNTHETIC_BODY,
  });
}

describe("GARUDA internal same-origin API", () => {
  beforeEach(() => {
    process.env.COCKPIT_SESSION_KEY = SECRET;
    mocks.runGarudaPreview.mockReset();
  });

  afterEach(() => {
    delete process.env.COCKPIT_SESSION_KEY;
  });

  it("independently rejects missing and forged sessions", async () => {
    const missing = await POST(await apiRequest());
    const forged = await POST(await apiRequest({ token: "forged.value" }));
    expect(missing.status).toBe(401);
    expect(forged.status).toBe(401);
    expect(mocks.runGarudaPreview).not.toHaveBeenCalled();
  });

  it("rejects a valid token carried only by a port-agnostic cookie", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    const response = await POST(await apiRequest({ cookieToken: token }));
    expect(response.status).toBe(401);
    expect(mocks.runGarudaPreview).not.toHaveBeenCalled();
  });

  it("independently rejects a non-loopback Host header", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    const response = await POST(
      await apiRequest({ host: "garuda.example.com", token }),
    );
    expect(response.status).toBe(403);
    expect(mocks.runGarudaPreview).not.toHaveBeenCalled();
  });

  it("runs the adapter for a valid local signed session", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    mocks.runGarudaPreview.mockResolvedValue({
      decision: "ACCEPT",
      reason_codes: [],
    });
    const response = await POST(await apiRequest({ token }));
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toContain("no-store");
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
    expect(mocks.runGarudaPreview).toHaveBeenCalledWith(SYNTHETIC_BODY);
  });

  it("rejects oversized and non-JSON requests before invoking Python", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    const oversized = await POST(
      await apiRequest({ token, contentLength: 4_097 }),
    );
    const wrongType = await POST(
      await apiRequest({ token, contentType: "text/plain" }),
    );
    expect(oversized.status).toBe(413);
    expect(wrongType.status).toBe(415);
    expect(mocks.runGarudaPreview).not.toHaveBeenCalled();
  });

  it("rejects cross-port and same-site browser requests before Python", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    const crossPort = await POST(
      await apiRequest({ token, origin: "http://localhost:4100" }),
    );
    const sameSite = await POST(
      await apiRequest({ token, secFetchSite: "same-site" }),
    );
    expect(crossPort.status).toBe(403);
    expect(sameSite.status).toBe(403);
    expect(mocks.runGarudaPreview).not.toHaveBeenCalled();
  });

  it("maps schema errors to 400 without exposing engine details", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    mocks.runGarudaPreview.mockResolvedValue({
      ok: false,
      error: "invalid_request",
      details: "/private/backend/path",
    });
    const response = await POST(await apiRequest({ token }));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "invalid_request" });
  });

  it("maps the engine size boundary to a sanitized 400", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    mocks.runGarudaPreview.mockResolvedValue({
      ok: false,
      error: "request_too_large",
      details: "/private/backend/path",
    });
    const response = await POST(await apiRequest({ token }));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "request_too_large" });
  });

  it("returns a generic 503 for unexpected adapter errors", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    mocks.runGarudaPreview.mockRejectedValue(
      new Error("secret at /Users/operator/private/path"),
    );
    const response = await POST(await apiRequest({ token }));
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "preview_unavailable" });
  });
});
